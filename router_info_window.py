"""
Janela "Router Information", aberta ao clicar em um roteador da malha.

Refatoração de RouterInfoFrame.java, PETextLog.java, SchedulingTab.java,
scheduling/SchedulingPanel.java, TaskInfoFrame.java e dos renderizadores
RouterInfoTableCellRender/CellRenderer do GraphicalDebugger original.

Abas da janela (mesma ordem do Java):
  - Log:          log do processador (log/log<X>x<Y>.txt do cenário)
  - Applications: tarefas alocadas/terminadas no PE; duplo clique abre a
                  janela "Task Information"
  - Scheduling:   gráfico de escalonamento do PE (debug/scheduling_report.txt)
  - Traffic:      volume por porta de entrada, com filtro de serviços
"""

import bisect
import os
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGridLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

import analysis
import export
import path_view
from overview_windows import _LiveOverview, _router_label
from util.MPSoCConfig import MPSoCConfig

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon")

# Intervalo do "Continuous Read" do log e da atualização da Task Information
LOG_READ_INTERVAL_MS = 1000
TASK_INFO_REFRESH_MS = 500

# Eventos de CPU usados quando o debug/cpu.cfg não existe (padrão do Java)
DEFAULT_CPU_EVENTS = {65536: "Interruption", 262144: "Scheduler", 524288: "Idle"}

# Marcas da régua do gráfico de escalonamento: a cada 1, 2, 5, 10... unidades
_RULER_STEPS = [base * 10 ** power for power in range(7) for base in (1, 2, 5)]

# Cores das células destacadas (mesmas do Java)
RUNNING_BACKGROUND = QColor(Qt.GlobalColor.blue)
CHECKED_BACKGROUND = QColor(Qt.GlobalColor.blue)
PENDING_BACKGROUND = QColor(Qt.GlobalColor.red)


def _read_only_table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    return table


def _highlight(item, background):
    item.setBackground(background)
    item.setForeground(QColor(Qt.GlobalColor.white))


def _task_name(mpsoc_config, task_id):
    return mpsoc_config.task_name_hash.get(task_id, str(task_id))


def _slice_task(mpsoc_config, task_id):
    if task_id < 0:
        return "-"
    if task_id >= analysis.KERNEL_TASK_ID:
        return "kernel"
    return _task_name(mpsoc_config, task_id)


def _pe_xy_address(mpsoc_config, router_address):
    """Endereço (x << 8) | y do PE, usado nos nomes dos arquivos de log."""
    return mpsoc_config.ham_to_xy_addr(router_address)


def _pe_report_address(mpsoc_config, router_address):
    """Endereço do PE como aparece no scheduling_report.txt (XY ou hamiltoniano)."""
    if mpsoc_config.router_addressing == MPSoCConfig.XY:
        return _pe_xy_address(mpsoc_config, router_address)
    return router_address


def _task_lifetime(tasks, task_id):
    """(tempo de alocação, tempo de término ou None) da última execução da tarefa."""
    allocated, terminated = 0, None
    for task in tasks:
        if task.id != task_id:
            continue
        if task.service == "ALLOCATED":
            allocated, terminated = task.time, None
        elif task.service == "TERMINATED":
            terminated = task.time
    return allocated, terminated


# ==========================================
# JANELA PRINCIPAL DO ROTEADOR
# ==========================================
class RouterInfoWindow(_LiveOverview):
    """
    Informações de um roteador/PE. Diferente do Java (que mostrava uma foto
    do momento em que a janela foi aberta), as tabelas acompanham a
    simulação, igual às demais janelas de visão geral.
    """

    def __init__(self, mpsoc_config, mpsoc_information, router_address, simulation=None):
        self.router_address = router_address
        self.task_windows = []
        super().__init__(mpsoc_config, mpsoc_information, simulation)

        self.setWindowTitle(f"Router {_router_label(mpsoc_config, router_address)} Information")
        self.setMinimumSize(440, 365)
        self.resize(560, 540)

        self.tabs = QTabWidget(self)
        self.log_tab = PELogTab(mpsoc_config, router_address)
        self.applications_tab = self._build_applications_tab()
        self.scheduling_tab = SchedulingTab(mpsoc_config, router_address)
        self.traffic_tab = self._build_traffic_tab()

        self.tabs.addTab(self.log_tab, "Log")
        self.tabs.addTab(self.applications_tab, "Applications")
        self.tabs.addTab(self.scheduling_tab, "Scheduling")
        self.tabs.addTab(self.traffic_tab, "Traffic")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

        self.refresh()

    @property
    def router_info(self):
        # Buscado a cada uso: o "Go" da simulação recria os RouterInformation
        return self.mpsoc_information.get_router_information(self.router_address)

    def rebuild(self):
        self.refresh()

    def refresh(self):
        self._dirty = False
        if not hasattr(self, "traffic_table"):
            return  # chamado pela base antes da interface existir
        self._update_task_table()
        self._update_traffic_table()

    def closeEvent(self, event):
        self.log_tab.stop_continuous_read()
        for window in self.task_windows:
            window.close()
        super().closeEvent(event)

    # ------------------------------------------
    # Aba Applications
    # ------------------------------------------
    def _build_applications_tab(self):
        self.task_table = _read_only_table(["Task Name", "Task", "Service", "Time"])
        self.task_table.setToolTip("Double click a task to see its messages.\n"
                                   "ALLOCATED* = task still running")
        self.task_table.cellDoubleClicked.connect(self._open_task_info)
        export.install_export_actions(self.task_table, f"router_{self.router_address}_applications",
                                      csv_view=self.task_table)
        return self.task_table

    def _update_task_table(self):
        tasks = self.router_info.get_tasks_information()
        terminated = {task.id for task in tasks if task.service == "TERMINATED"}

        # Primeiro as alocações, depois os términos (mesma ordem do Java)
        rows = []
        for task in tasks:
            if task.service == "ALLOCATED":
                running = task.id not in terminated
                rows.append((task, "ALLOCATED*" if running else "ALLOCATED", running))
        rows.extend((task, "TERMINATED", False) for task in tasks if task.service == "TERMINATED")

        table = self.task_table
        table.setRowCount(len(rows))
        for row, (task, service, running) in enumerate(rows):
            values = (_task_name(self.mpsoc_config, task.id), str(task.id), service, str(task.time))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, task.id)
                if running and column == 2:
                    _highlight(item, RUNNING_BACKGROUND)
                table.setItem(row, column, item)

    def _open_task_info(self, row, _column):
        item = self.task_table.item(row, 0)
        if item is None:
            return
        window = TaskInfoWindow(self.mpsoc_config, self, item.data(Qt.ItemDataRole.UserRole))
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.destroyed.connect(lambda *_, w=window: self._forget_task_window(w))
        self.task_windows.append(window)
        window.show()

    def _forget_task_window(self, window):
        if window in self.task_windows:
            self.task_windows.remove(window)

    # ------------------------------------------
    # Aba Traffic
    # ------------------------------------------
    def _build_traffic_tab(self):
        tab = QWidget()

        filter_box = QGroupBox("Service Filter", tab)
        self.services_to_add = QComboBox()
        self.services_to_add.addItem("None")
        for service_name in self.mpsoc_config.get_services_hash().values():
            self.services_to_add.addItem(service_name)

        self.services_added = QComboBox()
        self.services_added.addItem("Show all")
        self.services_added.currentIndexChanged.connect(self._update_traffic_table)

        add_button = QPushButton("Add >>")
        remove_button = QPushButton("Remove <<")
        add_button.clicked.connect(self._add_service)
        remove_button.clicked.connect(self._remove_service)

        filter_layout = QGridLayout(filter_box)
        filter_layout.addWidget(QLabel("Services to add"), 0, 0)
        filter_layout.addWidget(QLabel("Added services"), 0, 2)
        filter_layout.addWidget(self.services_to_add, 1, 0)
        filter_layout.addWidget(add_button, 0, 1)
        filter_layout.addWidget(remove_button, 1, 1)
        filter_layout.addWidget(self.services_added, 1, 2)
        filter_layout.setColumnStretch(0, 1)
        filter_layout.setColumnStretch(2, 1)

        self.traffic_table = _read_only_table(["Input Port", "Total Volume", "Service Volume", "Percentual"])
        self.traffic_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        export.install_export_actions(self.traffic_table, f"router_{self.router_address}_traffic",
                                      csv_view=self.traffic_table)

        layout = QVBoxLayout(tab)
        layout.addWidget(filter_box)
        layout.addWidget(self.traffic_table)
        return tab

    def selected_services(self):
        """Serviço escolhido em "Added services"; em "Show all", todos os adicionados."""
        combo = self.services_added
        if combo.currentIndex() > 0:
            names = [combo.currentText()]
        else:
            names = [combo.itemText(index) for index in range(1, combo.count())]
        return [self.mpsoc_config.get_service_value(name) for name in names]

    def _add_service(self):
        if self.services_to_add.currentIndex() == 0:
            return
        name = self.services_to_add.currentText()
        if self.services_added.findText(name) == -1:
            self.services_added.addItem(name)
        # Volta para "Show all" (o sinal atualiza a tabela)
        self.services_added.setCurrentIndex(0)
        self._update_traffic_table()

    def _remove_service(self):
        index = self.services_added.currentIndex()
        if index > 0:
            self.services_added.removeItem(index)
            self._update_traffic_table()

    def _update_traffic_table(self, *_):
        router = self.router_info
        services = self.selected_services()

        def percent(part, total):
            return f"{part * 100 // total}%" if total else "0%"

        rows = []
        router_total = router_services = 0
        for port in range(MPSoCConfig.NPORT):
            total = router.get_port_total_volume_in_flits(port)
            service = router.get_port_volume_in_flits(port, services) if services else 0
            router_total += total
            router_services += service
            rows.append((MPSoCConfig.get_port_string(port), total, service))
        rows.append(("TOTAL", router_total, router_services))

        table = self.traffic_table
        table.setRowCount(len(rows))
        bold = QFont()
        bold.setBold(True)
        for row, (port, total, service) in enumerate(rows):
            values = (port, f"{total} flits", f"{service} flits", percent(service, total))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if port == "TOTAL":
                    item.setFont(bold)
                table.setItem(row, column, item)


# ==========================================
# ABA LOG
# ==========================================
class PELogTab(QWidget):
    """Mostra o log do processador (log/log<X>x<Y>.txt), lido uma vez ou continuamente."""

    def __init__(self, mpsoc_config, router_address, parent=None):
        super().__init__(parent)
        xy = _pe_xy_address(mpsoc_config, router_address)
        testcase = mpsoc_config.get_testcase_path() or os.path.dirname(
            os.path.normpath(mpsoc_config.debug_file_path))
        self.log_path = os.path.join(testcase, "log", f"log{xy >> 8}x{xy & 0xFF}.txt")

        self.read_once_button = QPushButton("Read Log Once")
        self.continuous_button = QPushButton("Continuous Read")
        self.continuous_button.setCheckable(True)
        self.read_once_button.clicked.connect(self.update_log)
        self.continuous_button.toggled.connect(self._on_continuous_toggled)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.text.setFont(font)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_log)

        buttons = QHBoxLayout()
        buttons.addWidget(self.read_once_button)
        buttons.addWidget(self.continuous_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.text)

    def _on_continuous_toggled(self, checked):
        font = self.continuous_button.font()
        font.setBold(checked)
        self.continuous_button.setFont(font)
        self.continuous_button.setText("Reading..." if checked else "Continuous Read")
        if checked:
            self.update_log()
            self.timer.start(LOG_READ_INTERVAL_MS)
        else:
            self.timer.stop()

    def stop_continuous_read(self):
        self.continuous_button.setChecked(False)

    def update_log(self):
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as log_file:
                content = log_file.read()
        except OSError:
            content = f"Log file not found:\n{self.log_path}"

        if content == self.text.toPlainText():
            return  # evita perder a rolagem/seleção sem necessidade
        self.text.setPlainText(content)
        # Mantém a rolagem no fim, como no Java
        scroll = self.text.verticalScrollBar()
        scroll.setValue(scroll.maximum())


# ==========================================
# ABA SCHEDULING
# ==========================================
class SchedulingTab(QWidget):
    """Botões que abrem o gráfico de escalonamento do PE ou de uma aplicação."""

    def __init__(self, mpsoc_config, router_address, parent=None):
        super().__init__(parent)
        self.mpsoc_config = mpsoc_config
        self.router_address = router_address
        self.graph_windows = []

        pe_button = QPushButton("Open Scheduling Graph")
        app_button = QPushButton("Open Application Scheduling")
        for button in (pe_button, app_button):
            button.setMinimumWidth(220)
        pe_button.clicked.connect(lambda: self._open_graph(only_app=False))
        app_button.clicked.connect(lambda: self._open_graph(only_app=True))

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(pe_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(app_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(3)

    def _open_graph(self, only_app):
        app_id = -1
        if only_app:
            app_id, ok = QInputDialog.getInt(self, "Application Scheduling",
                                             "Please, inform the application ID:", 0, 0, 0xFF)
            if not ok:
                return

        report = os.path.join(self.mpsoc_config.debug_file_path, "scheduling_report.txt")
        if not os.path.isfile(report):
            QMessageBox.warning(self, "Scheduling", f"File not found:\n{report}")
            return

        window = SchedulingGraphWindow(self.mpsoc_config, self.router_address, app_id)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.destroyed.connect(lambda *_, w=window: self.graph_windows.remove(w))
        self.graph_windows.append(window)
        window.show()


@dataclass
class SchedulingEvent:
    code: int
    name: str
    start: int
    finish: int
    rect: QRect = None  # posição no último desenho, para o clique
    pe: int = -1        # endereço hamiltoniano do PE que executou o trecho


def read_cpu_events(debug_dir):
    """Nomes dos eventos de CPU (debug/cpu.cfg: nome<TAB>código)."""
    events = {}
    try:
        with open(os.path.join(debug_dir, "cpu.cfg"), "r", encoding="utf-8") as cpu_file:
            for line in cpu_file:
                fields = line.split()
                if len(fields) >= 2:
                    events[int(fields[1])] = fields[0]
    except (OSError, ValueError):
        events = {}
    return events or dict(DEFAULT_CPU_EVENTS)


def read_scheduling_report(path, pe_filter=None):
    """
    Lê o scheduling_report.txt (PE<TAB>código<TAB>tempo). Cada linha marca
    o início de um trecho que termina na próxima linha do mesmo PE; o último
    trecho de cada PE ganha 10 ticks, como no Java.

    Retorna {PE: [(código, início, fim), ...]}.
    """
    slices = {}
    current = {}
    with open(path, "r", encoding="utf-8") as report:
        for line in report:
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            try:
                pe, code, time = int(fields[0]), int(fields[1]), int(fields[2])
            except ValueError:
                continue
            if pe_filter is not None and pe != pe_filter:
                continue

            if pe in current:
                last_code, last_start = current[pe]
                slices.setdefault(pe, []).append((last_code, last_start, time))
            current[pe] = (code, time)

    for pe, (code, start) in current.items():
        slices.setdefault(pe, []).append((code, start, start + 10))
    return slices


class SchedulingGraph(QWidget):
    """
    Gráfico de Gantt do escalonamento (SchedulingPanel.java).

      - clique num trecho: mostra os dados dele em "Execution Slice"
      - linha vermelha segue o mouse e mostra o tempo em ticks
      - Ctrl + roda do mouse: zoom horizontal
    """

    # Trecho clicado (SchedulingEvent) ou None
    selection_changed = Signal(object)

    TOP = 50           # INITI_Y
    ROW_HEIGHT = 26    # NAME_SPACE
    CPU_COLOR = QColor(21, 119, 40)
    TASK_COLOR = QColor(Qt.GlobalColor.blue)

    def __init__(self, mpsoc_config, router_address, app_filter=-1, parent=None):
        super().__init__(parent)
        self.mpsoc_config = mpsoc_config
        self.router_address = router_address
        self.app_filter = app_filter
        self.cpu_events = read_cpu_events(mpsoc_config.debug_file_path)

        self.events = self._load_events()
        self.last_time = max((event.finish for event in self.events), default=0)

        # Uma linha por código, na ordem em que aparecem
        self.rows = {}
        usage = {}
        for event in self.events:
            if event.code not in self.rows:
                self.rows[event.code] = (len(self.rows) + 1) * self.ROW_HEIGHT
            usage[event.code] = usage.get(event.code, 0) + event.finish - event.start
        self.usage = usage
        self.total_cpu_time = sum(usage.values())
        self.names = {event.code: event.name for event in self.events}

        # Início de cada trecho, para achar o trecho clicado com bisect
        self.events.sort(key=lambda event: event.start)
        self.starts = [event.start for event in self.events]

        self.selected = None
        self.mouse_x = None
        self._cache = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.time_line = len(self.rows) * self.ROW_HEIGHT + self.TOP + self.ROW_HEIGHT // 2
        self.report_top = self.time_line + 50
        report_lines = len(self.rows) + 3 if app_filter == -1 else 6
        self.setMinimumHeight(self.report_top + report_lines * 15 + 20)

    def _load_events(self):
        config = self.mpsoc_config
        path = os.path.join(config.debug_file_path, "scheduling_report.txt")

        if self.app_filter == -1:
            pe = _pe_report_address(config, self.router_address)
            slices = [(self.router_address, *piece) for piece in read_scheduling_report(path, pe).get(pe, [])]
        else:
            # Tarefas da aplicação em todos os PEs (os eventos de CPU têm bits acima do 16)
            def ham(report_pe):
                return config.xy_to_ham_addr(report_pe) if config.router_addressing == MPSoCConfig.XY else report_pe
            slices = [(ham(report_pe), *piece) for report_pe, pe_slices in read_scheduling_report(path).items()
                      for piece in pe_slices
                      if piece[0] >> 16 == 0 and piece[0] >> 8 == self.app_filter]

        return [SchedulingEvent(code, self._event_name(code), start, finish, pe=pe)
                for pe, code, start, finish in slices]

    def _event_name(self, code):
        if code in self.cpu_events:
            return self.cpu_events[code]
        return self.mpsoc_config.task_name_hash.get(code, "Undefined")

    # ------------------------------------------
    # Geometria
    # ------------------------------------------
    def _name_width(self):
        longest = max((len(name) for name in self.names.values()), default=0)
        return max(longest * 10, 60)

    def _proportion(self):
        if not self.last_time:
            return 0.0
        return (self.width() - self._name_width()) / self.last_time

    def _time_scale(self):
        """(ticks por unidade, nome da unidade) para a régua de tempo."""
        period = self.mpsoc_config.clock_period_in_ns or 10
        units = ((1_000_000, "ms"), (1_000, "us"), (period, "ns"))
        for unit_ns, name in units:
            ticks = max(1, round(unit_ns / period))
            if self.last_time >= ticks or name == "ns":
                return ticks, name
        return 1, "ns"

    # ------------------------------------------
    # Desenho
    # ------------------------------------------
    def resizeEvent(self, event):
        self._cache = None
        super().resizeEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.PaletteChange:
            self._cache = None  # troca de tema
        super().changeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._cache is None:
            self._cache = self._render_static()
        painter.drawPixmap(0, 0, self._cache)

        text_color = self.palette().text().color()
        if self.events:
            self._draw_mouse_line(painter)
            self._draw_report(painter, text_color)
        else:
            painter.setPen(text_color)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No scheduling events for this PE")

    def _render_static(self):
        """Nomes, trechos e régua (só muda com tamanho, zoom ou tema)."""
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(self.size() * ratio)
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(self.palette().base().color())
        if not self.events:
            return pixmap

        painter = QPainter(pixmap)
        width = self.width()
        name_width = self._name_width()
        proportion = self._proportion()
        text_color = self.palette().text().color()
        grid_color = QColor(Qt.GlobalColor.gray)

        painter.setPen(text_color)
        if self.app_filter == -1:
            painter.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            title = f"PE {_router_label(self.mpsoc_config, self.router_address)} Scheduling Graph"
            painter.drawText(QRect(0, 0, width, 30), Qt.AlignmentFlag.AlignCenter, title)
        painter.setFont(QFont("Arial", 9))

        for code, y in self.rows.items():
            painter.drawText(10, self.TOP + y + 5, self.names[code])

        # Linhas horizontais de cada instância
        painter.setPen(grid_color)
        for y in self.rows.values():
            top = self.TOP + y - self.ROW_HEIGHT // 2
            painter.drawLine(name_width, top, width, top)

        # Trechos: verde para eventos da CPU, azul para tarefas
        painter.setPen(Qt.PenStyle.NoPen)
        for event in self.events:
            x = int(event.start * proportion) + name_width
            y = self.TOP + self.rows[event.code] - self.ROW_HEIGHT // 2
            slice_width = max(1, int((event.finish - event.start) * proportion))
            event.rect = QRect(x, y, slice_width, self.ROW_HEIGHT)
            painter.fillRect(event.rect, self.CPU_COLOR if event.code in self.cpu_events else self.TASK_COLOR)

        # Eixos
        painter.setPen(QPen(text_color, 2))
        painter.drawLine(name_width, self.TOP, name_width, self.time_line + 10)
        painter.drawLine(name_width, self.time_line, width, self.time_line)

        # Régua: uma marca por unidade, pulando marcas que ficariam coladas
        painter.setPen(text_color)
        tick_scale, scale_name = self._time_scale()
        step_px = tick_scale * proportion
        skip = next(step for step in _RULER_STEPS if step * step_px >= 45 or step == _RULER_STEPS[-1])
        mark = skip
        while mark * step_px <= width - name_width:
            x = int(mark * step_px) + name_width
            painter.drawLine(x, self.time_line, x, self.time_line + 10)
            painter.drawText(QRect(x - 50, self.time_line + 10, 100, 16),
                             Qt.AlignmentFlag.AlignHCenter, f"{mark} {scale_name}")
            mark += skip

        painter.end()
        return pixmap

    def _draw_mouse_line(self, painter):
        if self.mouse_x is None:
            return
        proportion = self._proportion()
        ticks = int((self.mouse_x - self._name_width()) / proportion) if proportion else 0
        painter.setPen(QColor(Qt.GlobalColor.red))
        painter.drawLine(self.mouse_x, self.TOP, self.mouse_x, self.time_line)
        label = f"{ticks} ticks"
        x = self.mouse_x - 6 * len(label) if self.mouse_x >= self.width() - 100 else self.mouse_x - 2 * len(label)
        painter.drawText(x, self.TOP - 10, label)

    def _draw_report(self, painter, text_color):
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 9))
        top = self.report_top
        value_x = 200

        if self.app_filter == -1:
            painter.drawText(10, top, "----------------------- CPU utilization ------------------------")
            painter.drawText(10, top + 15, "Total CPU time: ")
            painter.drawText(value_x, top + 15, f"{self.total_cpu_time} ticks")
            for line, code in enumerate(self.rows, start=2):
                percent = self.usage[code] * 100.0 / self.total_cpu_time if self.total_cpu_time else 0.0
                painter.drawText(10, top + 15 * line, f"{self.names[code]} : ")
                painter.drawText(value_x, top + 15 * line, f"{percent:.3f}%")

        if self.selected is None:
            return
        event = self.selected
        x = 400 if self.app_filter == -1 else 10
        if self.mouse_x is not None and self.mouse_x > x:
            x = self.mouse_x - 300 if self.mouse_x >= self.width() - 300 else self.mouse_x
        lines = (("Name : ", event.name),
                 ("Start time : ", f"{event.start} ticks"),
                 ("Finish time : ", f"{event.finish} ticks"),
                 ("Slice Time : ", f"{event.finish - event.start} ticks"))
        painter.drawText(x, top, "----------------------- Execution Slice------------------------")
        for line, (label, value) in enumerate(lines, start=1):
            painter.drawText(x, top + 15 * line, label)
            painter.drawText(x + 200, top + 15 * line, value)

    # ------------------------------------------
    # Mouse
    # ------------------------------------------
    def _event_at(self, point):
        proportion = self._proportion()
        if not proportion:
            return None
        # Trechos com início até a posição do mouse (com 1 px de tolerância)
        tick = (point.x() + 1 - self._name_width()) / proportion
        index = bisect.bisect_right(self.starts, tick)
        for event in reversed(self.events[max(0, index - 64):index]):
            if event.rect is not None and event.rect.adjusted(0, 0, 1, 1).contains(point):
                return event
        return None

    def mouseMoveEvent(self, event):
        point = event.position().toPoint()
        hit = self._event_at(point)
        self.setCursor(Qt.CursorShape.PointingHandCursor if hit else Qt.CursorShape.ArrowCursor)
        inside = point.x() >= self._name_width() and self.TOP <= point.y() <= self.time_line
        self.mouse_x = point.x() if inside else None
        self.update()

    def leaveEvent(self, event):
        self.mouse_x = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected = self._event_at(event.position().toPoint())
            self.update()
            self.selection_changed.emit(self.selected)

    def wheelEvent(self, event):
        if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.ignore()  # rolagem normal do QScrollArea
            return
        factor = 1.1 if event.angleDelta().y() > 0 else 1 / 1.1
        self.setMinimumWidth(max(400, int(self.width() * factor)))
        self.resize(self.minimumWidth(), self.height())
        event.accept()


class SchedulingGraphWindow(QWidget):
    def __init__(self, mpsoc_config, router_address, app_filter=-1):
        super().__init__()
        self.graph = SchedulingGraph(mpsoc_config, router_address, app_filter)
        name = f"scheduling_{router_address}" if app_filter == -1 else f"scheduling_app_{app_filter}"
        export.install_export_actions(self.graph, name, png_widget=self.graph)

        if app_filter == -1:
            self.setWindowTitle(f"Scheduling Graph {_router_label(mpsoc_config, router_address)}")
        else:
            self.setWindowTitle(f"Application {app_filter} Scheduling Graph")
        self.setWindowIcon(QPixmap(os.path.join(ICON_DIR, "scheduling_icon.png")))

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.graph)
        scroll.horizontalScrollBar().setSingleStep(200)

        # Pacotes do PE durante o trecho clicado (depuração hardware + software)
        self.mpsoc_config = mpsoc_config
        self._tracker = None
        self._slice_messages = []
        self.slice_label = QLabel("Click a slice of the graph to see the packets the PE received and sent "
                                  "during it (e.g. the packet that caused an interruption).")
        self.slice_label.setWordWrap(True)
        self.slice_table = _read_only_table(["Time (tick)", "Direction", "From", "To", "Service", "Flits",
                                             "Latency (cycles)", "Tasks"])
        self.slice_table.setToolTip("Double click a packet to show its path on the main window mesh")
        self.slice_table.cellDoubleClicked.connect(self._show_slice_message)
        export.install_export_actions(self.slice_table, f"{name}_slice_packets", csv_view=self.slice_table)
        packets_panel = QWidget()
        packets_layout = QVBoxLayout(packets_panel)
        packets_layout.addWidget(self.slice_label)
        packets_layout.addWidget(self.slice_table)
        self.graph.selection_changed.connect(self._show_slice_packets)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(scroll)
        splitter.addWidget(packets_panel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        screen = self.screen().availableGeometry()
        graph_height = min(screen.height() - 240, self.graph.minimumHeight() + 30)
        splitter.setSizes([graph_height, 220])
        self.resize(screen.width(), min(screen.height(), graph_height + 240))
        self.move(screen.topLeft())

    def _all_messages(self):
        # O trace inteiro é analisado uma vez, no primeiro clique
        if self._tracker is None:
            self._tracker = analysis.track_all(self.mpsoc_config, analysis.read_all_packets(self.mpsoc_config))
        return self._tracker.messages

    def _show_slice_packets(self, event):
        config = self.mpsoc_config
        if event is None:
            self._slice_messages = []
            self.slice_table.setRowCount(0)
            return

        self._slice_messages = analysis.messages_in_slice(self._all_messages(), event.pe, event.start, event.finish)
        self.slice_label.setText(
            f"<b>{event.name}</b> on PE {_router_label(config, event.pe)}, {event.start} → {event.finish} ticks: "
            f"{len(self._slice_messages)} packet(s). Received = delivered to the PE up to "
            f"{analysis.SLICE_LOOKBACK} cycles before the slice or during it; sent = injected during it.")

        table = self.slice_table
        table.setRowCount(len(self._slice_messages))
        for row, (message, direction) in enumerate(self._slice_messages):
            time = message.delivered if direction == "received" else message.injected
            source = _router_label(config, message.source)
            if message.from_peripheral:
                source = f"Periph. @ {source}"
            tasks = (f"{_slice_task(config, message.task_source)} → {_slice_task(config, message.task_target)}"
                     if message.task_source >= 0 or message.task_target >= 0 else "-")
            values = (str(time), direction, source, _router_label(config, message.target),
                      config.get_string_service_name(message.service), str(message.flits),
                      str(message.latency) if message.delivered >= 0 else "not delivered", tasks)
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))

    def _show_slice_message(self, row, _column):
        if 0 <= row < len(self._slice_messages):
            message, _direction = self._slice_messages[row]
            path_view.show_message(message, description=f"Packet {self.mpsoc_config.get_string_service_name(message.service)} "
                                                        f"from the scheduling graph")


# ==========================================
# TASK INFORMATION
# ==========================================
class TaskInfoWindow(QWidget):
    """
    Estado de uma tarefa do PE e as mensagens que ela pediu (TaskInfoFrame.java).
    Cada MESSAGE_REQUEST fica "pending" até chegar o MESSAGE_DELIVERY da
    mesma tarefa remota, quando passa a "checked".
    """

    def __init__(self, mpsoc_config, router_window, task_id):
        super().__init__()
        self.mpsoc_config = mpsoc_config
        self.router_window = router_window
        self.task_id = task_id
        name = _task_name(mpsoc_config, task_id)
        self.setWindowTitle(f"Task {name} Information")
        self.resize(560, 420)

        bold = QFont()
        bold.setBold(True)

        def caption(text):
            label = QLabel(text)
            label.setFont(bold)
            return label

        self.name_label = QLabel(name)
        self.id_label = QLabel(str(task_id))
        self.status_label = QLabel()
        self.time_label = QLabel()

        info = QGridLayout()
        info.addWidget(caption("Task Name:"), 0, 0)
        info.addWidget(self.name_label, 0, 1)
        info.addWidget(caption("Task ID:"), 1, 0)
        info.addWidget(self.id_label, 1, 1)
        info.addWidget(caption("Task Status:"), 0, 2)
        info.addWidget(self.status_label, 0, 3)
        info.addWidget(caption("Executed Time:"), 1, 2)
        info.addWidget(self.time_label, 1, 3)
        info.setColumnStretch(1, 1)
        info.setColumnStretch(3, 1)

        pipe_button = QPushButton("View PIPE")
        request_button = QPushButton("Requested")
        pipe_button.clicked.connect(lambda: self._show_comm_table("pipe", "Stored PIPE Messages"))
        request_button.clicked.connect(lambda: self._show_comm_table("request", "Stored Message Requests"))
        buttons = QHBoxLayout()
        buttons.addWidget(pipe_button)
        buttons.addWidget(request_button)
        buttons.addStretch()

        self.message_table = _read_only_table(["Time: Requested / Delivered", "Remote task", "Delivered", "Num"])
        export.install_export_actions(self.message_table, f"task_{task_id}_messages", csv_view=self.message_table)
        header = self.message_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        layout = QVBoxLayout(self)
        layout.addLayout(info)
        layout.addLayout(buttons)
        layout.addWidget(caption("Sent Message Requests:"))
        layout.addWidget(self.message_table)

        self.comm_windows = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(TASK_INFO_REFRESH_MS)
        self.refresh()

    def refresh(self):
        try:
            tasks = self.router_window.router_info.get_tasks_information()
        except RuntimeError:
            self.timer.stop()  # janela do roteador já destruída
            return
        self._update_labels(tasks)
        self._update_message_table(tasks)

    def _update_labels(self, tasks):
        allocated, terminated = _task_lifetime(tasks, self.task_id)
        if terminated is None:
            self.status_label.setText("Running")
            self.time_label.setText("-")
        else:
            self.status_label.setText("Terminated")
            self.time_label.setText(str(terminated - allocated))

    def _update_message_table(self, tasks):
        pending = []
        rows = []
        for task in tasks:
            if task.id != self.task_id:
                continue
            if task.service == "MESSAGE_REQUEST":
                pending.append(task)
            elif task.service == "MESSAGE_DELIVERY":
                # A entrega responde o pedido mais antigo para a mesma tarefa remota
                for index, request in enumerate(pending):
                    if request.remote_task_id == task.remote_task_id:
                        del pending[index]
                        rows.append((f"Requested: {request.time}  Delivered: {task.time}",
                                     task.remote_task_id, "checked"))
                        break
        rows.extend((f"Requested: {request.time}  Delivered: -", request.remote_task_id, "pending")
                    for request in pending)

        table = self.message_table
        table.setRowCount(len(rows))
        counter = {}
        for row, (times, remote, status) in enumerate(rows):
            counter[remote] = counter.get(remote, 0) + 1
            values = (times, _task_name(self.mpsoc_config, remote), status, str(counter[remote]))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 2:
                    _highlight(item, CHECKED_BACKGROUND if status == "checked" else PENDING_BACKGROUND)
                table.setItem(row, column, item)

    def _comm_file(self, folder):
        """debug/<pasta>/<PE>.txt; os arquivos usam o endereço hamiltoniano."""
        config = self.mpsoc_config
        address = self.router_window.router_address
        candidates = [address]
        if config.router_addressing == MPSoCConfig.XY:
            candidates.append(_pe_xy_address(config, address))  # nome usado pelo Java
        for candidate in candidates:
            path = os.path.join(config.debug_file_path, folder, f"{candidate}.txt")
            if os.path.isfile(path):
                return path
        return None

    def _show_comm_table(self, folder, title):
        path = self._comm_file(folder)
        rows = read_comm_debug(path) if path else None
        if not rows:
            what = "PIPE" if folder == "pipe" else "request"
            QMessageBox.information(self, title, f"No {what} information")
            return

        window = QWidget()
        window.setWindowTitle(title)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.resize(320, 300)
        table = _read_only_table(["Prod Task", "Cons Task", "Time"])
        table.setRowCount(len(rows))
        for row, (producer, consumer, time) in enumerate(rows):
            values = (_task_name(self.mpsoc_config, producer), _task_name(self.mpsoc_config, consumer), time)
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        layout = QVBoxLayout(window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table)

        window.destroyed.connect(lambda *_, w=window: self.comm_windows.remove(w))
        self.comm_windows.append(window)
        window.move(self.geometry().center() - window.rect().center())
        window.show()

    def closeEvent(self, event):
        self.timer.stop()
        for window in list(self.comm_windows):
            window.close()
        super().closeEvent(event)


def read_comm_debug(path):
    """
    Lê debug/pipe/<PE>.txt ou debug/request/<PE>.txt (add|rem<TAB>prod<TAB>cons<TAB>tempo)
    e retorna as mensagens que continuam armazenadas: [(prod, cons, tempo), ...].
    """
    stored = []
    try:
        with open(path, "r", encoding="utf-8") as comm_file:
            for line in comm_file:
                fields = line.strip().split("\t")
                if len(fields) < 4:
                    continue
                try:
                    producer, consumer = int(fields[1]), int(fields[2])
                except ValueError:
                    continue
                if fields[0] == "add":
                    stored.append((producer, consumer, fields[3]))
                else:
                    # Remove a primeira mensagem com o mesmo produtor e consumidor
                    for index, (prod, cons, _time) in enumerate(stored):
                        if (prod, cons) == (producer, consumer):
                            del stored[index]
                            break
    except OSError:
        return None
    return stored
