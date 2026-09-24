"""
Deloream — leitor dos logs de depuração das tarefas (Debug Log Reader for MPSoCs).

Refatoração do pacote "deloream" (DeloreamMainFrame.java e TaskMessage.java)
do GraphicalDebugger original.

Estrutura esperada de um cenário (testcase) do Memphis-V:

    <cenário>/
     ├─ debug/platform.cfg   nomes das tarefas e das aplicações
     └─ log/log<X>x<Y>.txt   saída de cada processador

As mensagens de depuração das tarefas nos logs têm o formato

    $$$_<processador>_<app>_<tarefa>_<mensagem>

ex.: "$$$_1x1_3_1_Inicio da aplicacao prod" (tarefa 1 da aplicação 3 no PE 1x1).
"""

import html
import os
import re
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QMainWindow, QMessageBox, QSplitter, QTextBrowser,
                               QTreeWidget, QTreeWidgetItem)

ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon", "delorean.png")

# Marca das mensagens de depuração das tarefas nos logs
MESSAGE_MARK = "$$$"

# $$$_<proc>_<app>_<task>_<mensagem>; a mensagem pode conter "_"
_MESSAGE_PATTERN = re.compile(r"^\$\$\$_(?P<proc>[^_]+)_(?P<app>\d+)_(?P<task>\d+)_(?P<message>.*)$")

# Papel dos itens da árvore que guarda o ID da aplicação/tarefa
_ID_ROLE = Qt.ItemDataRole.UserRole


@dataclass(frozen=True)
class TaskMessage:
    """Uma linha "$$$" de um log de processador."""

    proc: str
    app_id: int
    task_id: int
    message: str

    @classmethod
    def parse(cls, line):
        match = _MESSAGE_PATTERN.match(line.rstrip("\r\n"))
        if match is None:
            return None
        return cls(match["proc"], int(match["app"]), int(match["task"]), match["message"])

    @property
    def proc_number(self):
        """Endereço XY do processador (x << 8 | y)."""
        x, y = (int(value) for value in self.proc.split("x"))
        return (x << 8) | y


def read_name_relations(platform_path):
    """
    Lê do platform.cfg as relações ID -> nome das tarefas e das aplicações.
    Retorna (tarefas, aplicações).
    """
    tasks, apps = {}, {}
    section = None

    with open(platform_path, "r", encoding="utf-8") as platform_file:
        for line in platform_file:
            fields = line.split()
            if not fields:
                continue

            match fields[0]:
                case "BEGIN_task_name_relation":
                    section = tasks
                case "BEGIN_app_name_relation":
                    section = apps
                case "END_task_name_relation" | "END_app_name_relation":
                    section = None
                case name if section is not None and len(fields) >= 2:
                    try:
                        section[int(fields[1])] = name
                    except ValueError:
                        continue

    return tasks, apps


def read_task_messages(log_dir, app_id, task_id):
    """
    Mensagens de uma tarefa em todos os logs do cenário, na ordem dos
    arquivos (ordenados por nome) e das linhas.
    """
    messages = []
    for file_name in sorted(os.listdir(log_dir)):
        if "log" not in file_name:
            continue
        path = os.path.join(log_dir, file_name)
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="replace") as log_file:
            for line in log_file:
                if not line.startswith(MESSAGE_MARK):
                    continue
                message = TaskMessage.parse(line)
                if message is not None and message.app_id == app_id and message.task_id == task_id:
                    messages.append(message)

    return messages


class DeloreamWindow(QMainWindow):
    """Árvore Aplicações -> Tarefas e, ao ativar uma tarefa, as mensagens dela nos logs."""

    def __init__(self, testcase_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deloream - Debug Log Reader for MPSoCs")
        if os.path.isfile(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(800, 700)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        # Duplo clique ou Enter, como o duplo clique do original
        self.tree.itemActivated.connect(self._on_item_activated)

        self.text = QTextBrowser()
        self.text.setOpenLinks(False)
        font = QFont("DejaVu Sans Mono")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.text.setFont(font)

        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(self.text)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 550])
        self.setCentralWidget(splitter)

        self._build_menu()
        self.load_testcase(testcase_path)

    def _build_menu(self):
        options = self.menuBar().addMenu("Options")

        new_testcase = QAction("New testcase", self)
        new_testcase.setShortcut(QKeySequence("Ctrl+N"))
        new_testcase.triggered.connect(self._choose_testcase)
        options.addAction(new_testcase)

        reload_action = QAction("Reload", self)
        reload_action.setShortcut(QKeySequence("F5"))
        reload_action.triggered.connect(lambda: self.load_testcase(self.testcase_path))
        options.addAction(reload_action)

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+E"))
        exit_action.triggered.connect(self.close)
        options.addAction(exit_action)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(
            self, "Deloream",
            "Deloream - Debug Log Reader for MPSoCs\n\n"
            "Double-click a task to read its debug messages ($$$) "
            "from the processor logs of the testcase."))
        help_menu.addAction(about)

    # ==========================================
    # CARREGAMENTO
    # ==========================================
    @property
    def platform_path(self):
        return os.path.join(self.testcase_path, "debug", "platform.cfg")

    @property
    def log_dir(self):
        return os.path.join(self.testcase_path, "log")

    def _choose_testcase(self):
        path = QFileDialog.getExistingDirectory(self, "Open testcase (folder with debug/ and log/)",
                                                self.testcase_path)
        if path:
            self.load_testcase(path)

    def load_testcase(self, testcase_path):
        """Lê os nomes do platform.cfg e monta a árvore de aplicações."""
        self.testcase_path = testcase_path
        self.setWindowTitle(f"Deloream - {testcase_path}")
        self.tree.clear()
        self.text.clear()

        try:
            self.task_names, self.app_names = read_name_relations(self.platform_path)
        except OSError:
            self.task_names, self.app_names = {}, {}
            self._show_error(f"platform.cfg not found in {html.escape(self.platform_path)}")
            return

        root = QTreeWidgetItem(self.tree, ["Applications"])

        # Aplicações do BEGIN_app_name_relation; tarefas sem aplicação conhecida
        # também aparecem, com o ID da aplicação no lugar do nome
        app_ids = sorted(set(self.app_names) | {task_id >> 8 for task_id in self.task_names})
        for app_id in app_ids:
            app_name = self.app_names.get(app_id, "app")
            app_item = QTreeWidgetItem(root, [f"{app_name}[{app_id}]"])
            app_item.setData(0, _ID_ROLE, app_id)

            for task_id in sorted(self.task_names):
                if task_id >> 8 == app_id:
                    task_item = QTreeWidgetItem(app_item, [f"{self.task_names[task_id]}[{task_id}]"])
                    task_item.setData(0, _ID_ROLE, task_id)

        self.tree.expandAll()

    # ==========================================
    # MENSAGENS
    # ==========================================
    def _on_item_activated(self, item, _column):
        # Só as folhas (tarefas) mostram mensagens
        if item.parent() is None or item.parent().parent() is None:
            return
        self.show_task_messages(item.data(0, _ID_ROLE))

    def show_task_messages(self, task_id):
        app_id, local_task_id = task_id >> 8, task_id & 0xFF

        try:
            messages = read_task_messages(self.log_dir, app_id, local_task_id)
        except OSError:
            messages = []

        if not messages:
            self._show_error("Log file not created yet or no message found!")
            return

        name = html.escape(self.task_names.get(task_id, str(task_id)))
        parts = [f"<h3>{name}[{task_id}]</h3>"]
        current_proc = None
        for message in messages:
            # Cabeçalho a cada troca de processador (a tarefa pode ter migrado)
            if message.proc != current_proc:
                current_proc = message.proc
                parts.append(f"<p style='margin-bottom:0'><b>-- Processor: {html.escape(current_proc)}</b></p>")
            parts.append(f"<p style='margin:0'>{html.escape(message.message)}</p>")

        self.text.setHtml("".join(parts))

    def _show_error(self, text):
        self.text.setHtml(f"<b><span style='color:#ff0000'>{text}</span></b>")
