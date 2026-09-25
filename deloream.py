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
from collections import defaultdict
from dataclasses import dataclass

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMainWindow, QMenu, QMessageBox, QSplitter, QStackedWidget, QTableView,
                               QTabWidget, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
                               QVBoxLayout, QWidget)

ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon", "delorean.png")

# Marca das mensagens de depuração das tarefas nos logs
MESSAGE_MARK = "$$$"

# $$$_<proc>_<app>_<task>_<mensagem>; a mensagem pode conter "_"
_MESSAGE_PATTERN = re.compile(r"^\$\$\$_(?P<proc>[^_]+)_(?P<app>\d+)_(?P<task>\d+)_(?P<message>.*)$")

# Papéis dos itens da árvore: tipo ("app"/"task") e ID da aplicação/tarefa
_KIND_ROLE = Qt.ItemDataRole.UserRole
_ID_ROLE = Qt.ItemDataRole.UserRole + 1


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


def read_all_messages(log_dir):
    """
    Todas as mensagens "$$$" dos logs do cenário, agrupadas por
    (aplicação, tarefa local), na ordem dos arquivos (por nome) e das linhas.
    """
    messages = defaultdict(list)
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
                if message is not None:
                    messages[(message.app_id, message.task_id)].append(message)

    return dict(messages)


def read_task_messages(log_dir, app_id, task_id):
    """Mensagens de uma tarefa em todos os logs do cenário."""
    return read_all_messages(log_dir).get((app_id, task_id), [])


class MessagesTab(QWidget):
    """
    Aba com as mensagens de uma tarefa (ou de todas as tarefas de uma
    aplicação): cabeçalho com o resumo, campo de busca e tabela
    #, processador, [tarefa,] mensagem.
    """

    def __init__(self, kind, item_id, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.item_id = item_id

        self.header = QLabel()
        self.header.setTextFormat(Qt.TextFormat.RichText)
        self.header.setWordWrap(True)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter messages…")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(260)

        self.model = QStandardItemModel(0, 4, self)
        self.model.setHorizontalHeaderLabels(["#", "Processor", "Task", "Message"])
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search.textChanged.connect(self._filter)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(22)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        font = QFont("DejaVu Sans Mono")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(font)
        # Coluna "Task" só faz sentido na aba de uma aplicação
        self.table.setColumnHidden(2, kind == "task")

        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty)

        top = QHBoxLayout()
        top.addWidget(self.header, 1)
        top.addWidget(self.search)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(top)
        layout.addWidget(self.stack, 1)

    def set_messages(self, title, subtitle, messages, empty_text):
        """`messages` é uma lista de (nome da tarefa, TaskMessage)."""
        self.model.removeRows(0, self.model.rowCount())
        for number, (task_name, message) in enumerate(messages, start=1):
            index_item = QStandardItem()
            index_item.setData(number, Qt.ItemDataRole.DisplayRole)
            row = [index_item, QStandardItem(message.proc), QStandardItem(task_name),
                   QStandardItem(message.message)]
            for item in row:
                item.setToolTip(message.message)
            self.model.appendRow(row)

        procs = list(dict.fromkeys(message.proc for _task, message in messages))
        details = [html.escape(subtitle), f"{len(messages)} message{'s' if len(messages) != 1 else ''}"]
        if procs:
            label = "processor" if len(procs) == 1 else "processors"
            details.append(f"{label}: {html.escape(', '.join(procs))}")
        self.header.setText(f"<span style='font-size:14pt; font-weight:bold'>{html.escape(title)}</span>"
                            f"<br><span>{' · '.join(details)}</span>")

        self.empty.setText(empty_text)
        self.stack.setCurrentWidget(self.table if messages else self.empty)
        self.search.setEnabled(bool(messages))

    def _filter(self, text):
        self.proxy.setFilterFixedString(text)


class DeloreamWindow(QMainWindow):
    """
    Árvore Aplicações -> Tarefas à esquerda; um clique numa tarefa (ou
    aplicação) abre as mensagens dela numa aba à direita, ou volta para a aba
    já aberta.
    """

    def __init__(self, testcase_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deloream - Debug Log Reader for MPSoCs")
        if os.path.isfile(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(1000, 700)

        self.task_names, self.app_names, self.messages = {}, {}, {}
        self._error = None

        self.tree_filter = QLineEdit()
        self.tree_filter.setPlaceholderText("Search tasks…")
        self.tree_filter.setClearButtonEnabled(True)
        self.tree_filter.textChanged.connect(self._filter_tree)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Task", "Messages"])
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        # Um clique abre a aba; Enter também (navegar com as setas não abre)
        self.tree.itemClicked.connect(self._on_item_activated)
        self.tree.itemActivated.connect(self._on_item_activated)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 6, 0, 6)
        left_layout.addWidget(self.tree_filter)
        left_layout.addWidget(self.tree)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._sync_tree_selection)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._tab_menu)
        self.tabs.tabBar().installEventFilter(self)

        self.placeholder = QLabel()
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.right = QStackedWidget()
        self.right.addWidget(self.placeholder)
        self.right.addWidget(self.tabs)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 720])
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

        options.addSeparator()
        close_tab = QAction("Close tab", self)
        close_tab.setShortcut(QKeySequence("Ctrl+W"))
        close_tab.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        options.addAction(close_tab)

        close_all = QAction("Close all tabs", self)
        close_all.setShortcut(QKeySequence("Ctrl+Shift+W"))
        close_all.triggered.connect(self.close_all_tabs)
        options.addAction(close_all)

        options.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+E"))
        exit_action.triggered.connect(self.close)
        options.addAction(exit_action)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(
            self, "Deloream",
            "Deloream - Debug Log Reader for MPSoCs\n\n"
            "Click a task to read its debug messages ($$$) from the processor logs "
            "of the testcase in a new tab; click an application to see the messages "
            "of all its tasks."))
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
            if path != self.testcase_path:
                self.close_all_tabs()
            self.load_testcase(path)

    def load_testcase(self, testcase_path):
        """
        Lê os nomes do platform.cfg e as mensagens dos logs, monta a árvore
        de aplicações e atualiza as abas abertas.
        """
        self.testcase_path = testcase_path
        self.setWindowTitle(f"Deloream - {testcase_path}")
        self.tree.clear()
        self._error = None

        try:
            self.task_names, self.app_names = read_name_relations(self.platform_path)
        except OSError:
            self.task_names, self.app_names, self.messages = {}, {}, {}
            self._error = f"platform.cfg not found in {self.platform_path}"
            self.close_all_tabs()
            self._update_placeholder()
            return

        try:
            self.messages = read_all_messages(self.log_dir)
        except OSError:
            self.messages = {}

        # Aplicações do BEGIN_app_name_relation; tarefas sem aplicação conhecida
        # também aparecem, com o ID da aplicação no lugar do nome
        app_ids = sorted(set(self.app_names) | {task_id >> 8 for task_id in self.task_names})
        for app_id in app_ids:
            app_item = QTreeWidgetItem(self.tree, [self._app_title(app_id)])
            app_item.setData(0, _KIND_ROLE, "app")
            app_item.setData(0, _ID_ROLE, app_id)
            bold = app_item.font(0)
            bold.setBold(True)
            app_item.setFont(0, bold)

            app_total = 0
            for task_id in sorted(self.task_names):
                if task_id >> 8 != app_id:
                    continue
                count = len(self._task_messages(task_id))
                app_total += count
                task_item = QTreeWidgetItem(app_item, [self._task_title(task_id), str(count) if count else "—"])
                task_item.setData(0, _KIND_ROLE, "task")
                task_item.setData(0, _ID_ROLE, task_id)
                task_item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if not count:
                    task_item.setForeground(0, self.palette().placeholderText())
                    task_item.setForeground(1, self.palette().placeholderText())
                    task_item.setToolTip(0, "No debug message found in the logs")

            app_item.setText(1, str(app_total) if app_total else "—")
            app_item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            app_item.setToolTip(0, "Click to see the messages of all tasks of this application")

        self.tree.expandAll()
        self._filter_tree(self.tree_filter.text())

        # Abas abertas passam a mostrar os logs recarregados
        for index in range(self.tabs.count()):
            self._fill_tab(self.tabs.widget(index))
        self._update_placeholder()

    def _app_title(self, app_id):
        return f"{self.app_names.get(app_id, 'app')}[{app_id}]"

    def _task_title(self, task_id):
        return f"{self.task_names.get(task_id, 'task')}[{task_id}]"

    def _task_messages(self, task_id):
        return self.messages.get((task_id >> 8, task_id & 0xFF), [])

    def _filter_tree(self, text):
        """Mostra só as tarefas (e aplicações) cujo nome contém o texto."""
        text = text.strip().lower()
        for app_index in range(self.tree.topLevelItemCount()):
            app_item = self.tree.topLevelItem(app_index)
            app_matches = text in app_item.text(0).lower()
            any_task = False
            for task_index in range(app_item.childCount()):
                task_item = app_item.child(task_index)
                visible = app_matches or text in task_item.text(0).lower()
                task_item.setHidden(not visible)
                any_task |= visible
            app_item.setHidden(not (app_matches or any_task))

    # ==========================================
    # ABAS
    # ==========================================
    def _on_item_activated(self, item, _column=0):
        kind = item.data(0, _KIND_ROLE)
        if kind is not None:
            self.open_tab(kind, item.data(0, _ID_ROLE))

    def show_task_messages(self, task_id):
        """Abre (ou mostra) a aba com as mensagens da tarefa."""
        return self.open_tab("task", task_id)

    def find_tab(self, kind, item_id):
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if tab.kind == kind and tab.item_id == item_id:
                return index
        return -1

    def open_tab(self, kind, item_id):
        index = self.find_tab(kind, item_id)
        if index < 0:
            tab = MessagesTab(kind, item_id)
            self._fill_tab(tab)
            index = self.tabs.addTab(tab, "")
            self._update_tab_title(index)
        self.tabs.setCurrentIndex(index)
        self._update_placeholder()
        return self.tabs.widget(index)

    def _fill_tab(self, tab):
        if tab.kind == "task":
            task_id = tab.item_id
            title = self._task_title(task_id)
            subtitle = f"application {self._app_title(task_id >> 8)}"
            name = self.task_names.get(task_id, str(task_id))
            messages = [(name, message) for message in self._task_messages(task_id)]
            empty = "Log file not created yet or no message found for this task."
        else:
            app_id = tab.item_id
            title = self._app_title(app_id)
            task_ids = [task_id for task_id in sorted(self.task_names) if task_id >> 8 == app_id]
            subtitle = f"{len(task_ids)} task{'s' if len(task_ids) != 1 else ''}"
            messages = [(self.task_names[task_id], message)
                        for task_id in task_ids for message in self._task_messages(task_id)]
            empty = "Log file not created yet or no message found for this application."
        tab.set_messages(title, subtitle, messages, empty)

    def _update_tab_title(self, index):
        tab = self.tabs.widget(index)
        if tab.kind == "task":
            title = self._task_title(tab.item_id)
            tooltip = f"{title} - application {self._app_title(tab.item_id >> 8)}"
        else:
            title = self._app_title(tab.item_id)
            tooltip = f"All tasks of {title}"
        self.tabs.setTabText(index, title)
        self.tabs.setTabToolTip(index, tooltip)

    def close_tab(self, index):
        if index < 0:
            return
        tab = self.tabs.widget(index)
        self.tabs.removeTab(index)
        tab.deleteLater()
        self._update_placeholder()

    def close_all_tabs(self, keep=None):
        for index in reversed(range(self.tabs.count())):
            if self.tabs.widget(index) is not keep:
                self.close_tab(index)

    def _tab_menu(self, position):
        index = self.tabs.tabBar().tabAt(position)
        if index < 0:
            return
        tab = self.tabs.widget(index)
        menu = QMenu(self)
        menu.addAction("Close", lambda: self.close_tab(self.tabs.indexOf(tab)))
        menu.addAction("Close other tabs", lambda: self.close_all_tabs(keep=tab))
        menu.addAction("Close all tabs", self.close_all_tabs)
        menu.exec(self.tabs.tabBar().mapToGlobal(position))

    def eventFilter(self, obj, event):
        # Botão do meio fecha a aba, como nos navegadores
        if obj is self.tabs.tabBar() and event.type() == event.Type.MouseButtonRelease \
                and event.button() == Qt.MouseButton.MiddleButton:
            self.close_tab(obj.tabAt(event.position().toPoint()))
            return True
        return super().eventFilter(obj, event)

    def _sync_tree_selection(self, index):
        """Seleciona na árvore o item da aba atual."""
        if index < 0:
            return
        tab = self.tabs.widget(index)
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, _KIND_ROLE) == tab.kind and item.data(0, _ID_ROLE) == tab.item_id:
                self.tree.setCurrentItem(item)
                return
            iterator += 1

    def _update_placeholder(self):
        if self._error:
            self.placeholder.setText(f"<b><span style='color:#e00000'>{html.escape(self._error)}</span></b>")
        elif not self.task_names:
            self.placeholder.setText("No task found in platform.cfg.")
        else:
            self.placeholder.setText("<span style='font-size:13pt'>Click a task to read its debug messages</span>"
                                     "<br>Click an application to see the messages of all its tasks.")
        self.right.setCurrentWidget(self.tabs if self.tabs.count() and not self._error else self.placeholder)
