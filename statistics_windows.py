"""
Janelas "Traffic Statistics" e "Application Timeline" (menu Tools).

Não existem no GraphicalDebugger em Java: implementam métricas usadas no
artigo do Memphis (Ruaro et al., DAES 2019) — vazão em Mbps, taxa de
injeção e latência (Seção 6.2/6.3) e a admissão de aplicações (Seção 3.4).
A lógica está em analysis.py.
"""

import os

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QScrollArea, QSpinBox, QSplitter, QTableView, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolTip, QVBoxLayout, QWidget)

import analysis
import export
import path_view
from overview_windows import _LiveOverview, _router_label
from util.MPSoCConfig import MPSoCConfig


def _ticks_to_us(mpsoc_config, ticks):
    return ticks * mpsoc_config.clock_period_in_ns / 1000.0


class _NumericItem(QTableWidgetItem):
    """Célula que ordena pelo valor numérico (UserRole), não pelo texto."""

    def __init__(self, text, value):
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, value)
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        return self.data(Qt.ItemDataRole.UserRole) < other.data(Qt.ItemDataRole.UserRole)


def _row_id(table, row):
    item = table.item(row, 0)
    return None if item is None else item.data(ROW_ID_ROLE)


def _sortable_table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    # O QTableWidget começa com o indicador em ordem decrescente
    table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
    return table


# Guarda, na primeira coluna, o índice da linha na lista original (a ordenação muda as linhas)
ROW_ID_ROLE = Qt.ItemDataRole.UserRole + 1


def _fill_table(table, rows, row_ids=None):
    """
    rows: listas de (texto, valor numérico ou None). row_ids (padrão: o
    índice da linha em `rows`) fica no ROW_ID_ROLE da primeira coluna.
    """
    table.setSortingEnabled(False)
    table.setRowCount(len(rows))
    for row, cells in enumerate(rows):
        for column, (text, value) in enumerate(cells):
            item = QTableWidgetItem(text) if value is None else _NumericItem(text, value)
            if column == 0:
                item.setData(ROW_ID_ROLE, row if row_ids is None else row_ids[row])
            table.setItem(row, column, item)
    # Reordena pela coluna escolhida pelo usuário
    table.setSortingEnabled(True)


# ==========================================
# TRAFFIC STATISTICS
# ==========================================
class _MessageModel(QAbstractTableModel):
    HEADERS = ("Injected (tick)", "Source", "Target", "Service", "Flits", "Hops", "Latency (cycles)", "Application")

    def __init__(self, mpsoc_config):
        super().__init__()
        self.mpsoc_config = mpsoc_config
        self.messages = []

    def set_messages(self, messages):
        self.beginResetModel()
        self.messages = messages
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.messages)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        message = self.messages[index.row()]
        column = index.column()
        config = self.mpsoc_config

        if role == Qt.ItemDataRole.UserRole:  # valor usado para ordenar
            return (message.injected, message.source, message.target, message.service, message.flits,
                    message.hops, message.latency, min(message.apps, default=-1))[column]
        if role == Qt.ItemDataRole.TextAlignmentRole and column in (0, 4, 5, 6):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if column == 0:
            return str(message.injected)
        if column == 1:
            label = _router_label(config, message.source)
            return f"Periph. @ {label}" if message.from_peripheral else label
        if column == 2:
            return _router_label(config, message.target)
        if column == 3:
            return config.get_string_service_name(message.service)
        if column == 4:
            return str(message.flits)
        if column == 5:
            return str(message.hops) if message.delivered >= 0 else "-"
        if column == 6:
            return str(message.latency) if message.delivered >= 0 else "not delivered"
        return ", ".join(analysis.app_label(config, app) for app in sorted(message.apps)) or "kernel"


class _MessageFilter(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.app = None
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def set_app(self, app):
        if hasattr(self, "beginFilterChange"):     # Qt 6.10+
            self.beginFilterChange()
            self.app = app
            self.endFilterChange()
        else:
            self.app = app
            self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        message = self.sourceModel().messages[row]
        if self.app is not None and self.app not in message.apps:
            return False
        return True


class TrafficStatisticsWindow(_LiveOverview):
    """
    Vazão por enlace (Mbps e % da capacidade), métricas por aplicação, a
    latência de cada mensagem, a validação do roteamento XY e os pacotes
    parados (possível deadlock), até o tempo atual da simulação.
    """

    # Sem avançar por este número de ciclos, o pacote é considerado parado
    DEFAULT_BLOCKED_THRESHOLD = 10000

    def __init__(self, mpsoc_config, mpsoc_information, simulation=None):
        self.tracker = analysis.TrafficTracker(mpsoc_config)
        super().__init__(mpsoc_config, mpsoc_information, simulation)
        self.setWindowTitle("Traffic Statistics")
        self.resize(820, 560)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.links_table = _sortable_table(["Router", "Input port", "Volume (flits)",
                                            "Throughput (Mbps)", "Link usage (%)"])
        self.links_table.setToolTip("Average since the beginning of the simulation, per router input port.\n"
                                    "Follows the Service/PE/Application filter.")

        self.apps_table = _sortable_table(["Application", "Messages", "Flits", "Throughput (Mbps)",
                                           "Injection rate (%)", "Avg latency", "Median latency",
                                           "Max latency", "Avg hops"])
        self.apps_table.setToolTip("Throughput = flits of the delivered messages of the application over the\n"
                                   "interval between its first injection and its last delivery.\n"
                                   "Injection rate = throughput / link capacity. Latencies in clock cycles.")

        self.message_model = _MessageModel(mpsoc_config)
        self.message_filter = _MessageFilter()
        self.message_filter.setSourceModel(self.message_model)
        self.messages_view = QTableView()
        self.messages_view.setModel(self.message_filter)
        self.messages_view.setSortingEnabled(True)
        self.messages_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.messages_view.verticalHeader().setVisible(False)
        self.messages_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.messages_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.messages_view.horizontalHeader().setStretchLastSection(True)
        self.messages_view.doubleClicked.connect(self._show_message_path)
        self.messages_view.setToolTip("Double click a packet to show its path on the main window mesh")
        self.message_app_combo = QComboBox()
        self.message_app_combo.currentIndexChanged.connect(
            lambda _index: self.message_filter.set_app(self.message_app_combo.currentData()))
        messages_tab = QWidget()
        messages_layout = QVBoxLayout(messages_tab)
        app_row = QHBoxLayout()
        app_row.addWidget(QLabel("Application:"))
        app_row.addWidget(self.message_app_combo, 1)
        messages_layout.addLayout(app_row)
        messages_layout.addWidget(self.messages_view)
        latency_note = QLabel("Latency = from the header entering the NoC (local port or peripheral) until the "
                              "last flit leaves the target router (network only, without the kernel time). "
                              "traffic_router.txt has no packet ID, so each packet is followed hop by hop by "
                              "service, size, neighbor router and time.")
        latency_note.setWordWrap(True)
        messages_layout.addWidget(latency_note)

        routing_tab = self._build_routing_tab()
        blocked_tab = self._build_blocked_tab()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.links_table, "Links")
        self.tabs.addTab(self.apps_table, "Applications")
        self.tabs.addTab(messages_tab, "Messages")
        self.tabs.addTab(routing_tab, "Routing")
        self.tabs.addTab(blocked_tab, "Blocked")
        self.tabs.currentChanged.connect(lambda _index: self.refresh())

        # Tabela exportada por aba (mesma ordem das abas)
        self.tab_tables = [(self.links_table, "links"), (self.apps_table, "applications"),
                           (self.messages_view, "messages"), (self.violations_table, "routing_violations"),
                           (self.blocked_table, "blocked_packets")]
        for table, name in self.tab_tables:
            export.install_export_actions(table, name, csv_view=table)

        csv_button = QPushButton("Export CSV…")
        csv_button.setToolTip("Save the table of the current tab (as filtered and sorted)")
        csv_button.clicked.connect(self._export_current_table)
        png_button = QPushButton("Save PNG…")
        png_button.clicked.connect(lambda: export.export_png(self, self, "traffic_statistics"))
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(csv_button)
        buttons.addWidget(png_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.tabs)
        layout.addLayout(buttons)

        self._fill_app_combo()
        self.refresh()

    def _build_routing_tab(self):
        tab = QWidget()
        self.routing_summary = QLabel()
        self.routing_summary.setWordWrap(True)
        self.violations_table = _sortable_table(["Time (tick)", "Router", "Input port", "Target", "Service",
                                                 "Moving", "Tasks"])
        self.violations_table.setToolTip("Hop records whose input port is not compatible with XY routing\n"
                                         "(X first, then Y) towards the target in the header.\n"
                                         "Double click to show the packet path on the main window mesh.")
        self.violations_table.cellDoubleClicked.connect(self._show_violation_path)
        self._violation_rows = []
        layout = QVBoxLayout(tab)
        layout.addWidget(self.routing_summary)
        layout.addWidget(self.violations_table)
        return tab

    def _build_blocked_tab(self):
        tab = QWidget()
        self.blocked_threshold = QSpinBox()
        self.blocked_threshold.setRange(1, 1_000_000_000)
        self.blocked_threshold.setSingleStep(1000)
        self.blocked_threshold.setValue(self.DEFAULT_BLOCKED_THRESHOLD)
        self.blocked_threshold.setSuffix(" cycles")
        self.blocked_threshold.valueChanged.connect(lambda _value: self.refresh())
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Packets in flight without progress for at least"))
        threshold_row.addWidget(self.blocked_threshold)
        threshold_row.addStretch()

        self.deadlock_label = QLabel()
        self.deadlock_label.setWordWrap(True)
        self.blocked_table = _sortable_table(["Injected (tick)", "Last seen (tick)", "Stopped for (cycles)",
                                              "Source", "Target", "Service", "Last router", "Hops seen",
                                              "Next XY hop", "Status"])
        self.blocked_table.setToolTip("Double click to show where the packet stopped on the main window mesh")
        self.blocked_table.cellDoubleClicked.connect(self._show_blocked_path)
        self._blocked_rows = []
        note = QLabel("A packet with no record after its injection may also be a gap in traffic_router.txt. "
                      "A circular wait (each packet waiting for the link held by the next one) indicates a "
                      "deadlock, which XY routing should never produce.")
        note.setWordWrap(True)
        layout = QVBoxLayout(tab)
        layout.addLayout(threshold_row)
        layout.addWidget(self.deadlock_label)
        layout.addWidget(self.blocked_table)
        layout.addWidget(note)
        return tab

    def _show_message_path(self, index):
        message = self.message_model.messages[self.message_filter.mapToSource(index).row()]
        service = self.mpsoc_config.get_string_service_name(message.service)
        path_view.show_message(message, description=f"Path of {service} injected at {message.injected}")

    def _show_violation_path(self, row, _column):
        index = _row_id(self.violations_table, row)
        if index is None or index >= len(self._violation_rows):
            return
        violation = self._violation_rows[index]
        description = f"XY violation at {_router_label(self.mpsoc_config, violation.router)}, tick {violation.time}"
        if violation.message is not None:
            path_view.show_message(violation.message, highlight=violation.router, description=description)
        else:
            path_view.show_record(violation.router, violation.port, violation.target, description)

    def _show_blocked_path(self, row, _column):
        index = _row_id(self.blocked_table, row)
        if index is not None and index < len(self._blocked_rows):
            message = self._blocked_rows[index]
            path_view.show_message(message, description=f"Packet stopped at "
                                                        f"{_router_label(self.mpsoc_config, message.last_router)}")

    def _export_current_table(self):
        table, name = self.tab_tables[self.tabs.currentIndex()]
        export.export_csv(self, table, name)

    def _fill_app_combo(self):
        self.message_app_combo.blockSignals(True)
        self.message_app_combo.clear()
        self.message_app_combo.addItem("All", None)
        for app in sorted(analysis.known_app_ids(self.mpsoc_config)):
            self.message_app_combo.addItem(analysis.app_label(self.mpsoc_config, app), app)
        self.message_app_combo.blockSignals(False)
        self.message_filter.set_app(None)

    def rebuild(self):
        self.tracker = analysis.TrafficTracker(self.mpsoc_config)
        self.message_model.mpsoc_config = self.mpsoc_config
        self._fill_app_combo()
        self.refresh()

    # ------------------------------------------
    def _update_tracker(self):
        """Analisa os pacotes já processados pela simulação (recomeça ao voltar no tempo)."""
        reader = self.mpsoc_information.read_traffic
        consumed = reader.packet_read_control
        if consumed < self.tracker.consumed:
            self.tracker.reset()
        for packet in reader.all_packets[self.tracker.consumed:consumed]:
            self.tracker.consume(packet)
        return reader.all_packets[consumed - 1].time if consumed else 0

    def refresh(self):
        self._dirty = False
        if not hasattr(self, "tabs"):
            return  # chamado pela base antes da interface existir

        config = self.mpsoc_config
        now = self._update_tracker()
        capacity = analysis.link_capacity_mbps(config)
        delivered = self.tracker.delivered()

        frequency = 1000.0 / config.clock_period_in_ns if config.clock_period_in_ns else 0
        self.summary.setText(
            f"<b>Simulated time:</b> {now} ticks ({_ticks_to_us(config, now) / 1000:.5f} ms) &nbsp; "
            f"<b>Link capacity:</b> {capacity:.0f} Mbps ({config.flit_size}-bit flits @ {frequency:.0f} MHz)<br>"
            f"<b>Messages:</b> {len(self.tracker.messages)} injected, {len(delivered)} delivered, "
            f"{self.tracker.pending_count()} in flight, {self.tracker.lost} without recorded delivery")

        current = self.tabs.currentIndex()
        if current == 0:
            self._update_links(now, capacity)
        elif current == 1:
            self._update_apps(delivered, capacity)
        elif current == 2:
            self.message_model.set_messages(list(self.tracker.messages))
        elif current == 3:
            self._update_routing()
        else:
            self._update_blocked(now)

    def _update_routing(self):
        config = self.mpsoc_config
        tracker = self.tracker
        non_xy, anomalies = analysis.routing_summary(tracker)
        checked = sum(tracker.hop_records.values())
        excluded = sum(total for _count, total in non_xy.values())

        if anomalies:
            status = (f"<b style='color:#d55e00'>⚠ {len(anomalies)} hop record(s) outside XY routing</b> "
                      f"in {checked - excluded} checked records.")
        else:
            status = f"<b style='color:#009e73'>✓ No XY routing violation</b> in {checked - excluded} checked hop records."
        if non_xy:
            services = ", ".join(f"{config.get_string_service_name(service)} ({count}/{total})"
                                 for service, (count, total) in sorted(non_xy.items()))
            status += (f"<br>Not checked — services that do not follow XY at all, most likely broadcast "
                       f"(e.g. the Memphis-V management network on the LOW channel): {services}.")
        self.routing_summary.setText(status)

        rows = []
        self._violation_rows = anomalies
        for violation in anomalies:
            # Lado de onde o pacote veio -> sentido em que ele andava
            side = analysis._PORT_SIDE.get(violation.port, (0, 0))
            direction = {(-1, 0): "east", (1, 0): "west", (0, -1): "north", (0, 1): "south"}.get(side, "-")
            tasks = f"{violation.task_source} → {violation.task_target}" if violation.task_source >= 0 else "-"
            rows.append([(str(violation.time), violation.time),
                         (_router_label(config, violation.router), None),
                         (MPSoCConfig.get_port_string(violation.port), None),
                         (_router_label(config, violation.target), None),
                         (config.get_string_service_name(violation.service), None),
                         (direction, None), (tasks, None)])
        _fill_table(self.violations_table, rows)

    def _update_blocked(self, now):
        config = self.mpsoc_config
        blocked = analysis.blocked_messages(self.tracker, now, self.blocked_threshold.value())
        cycles = analysis.find_wait_cycles(config, blocked)
        in_cycle = {id(message) for cycle in cycles for message in cycle}

        if cycles:
            descriptions = ["  →  ".join(f"{_router_label(config, m.last_router)} "
                                          f"({config.get_string_service_name(m.service)})" for m in cycle)
                            for cycle in cycles]
            self.deadlock_label.setText("<b style='color:#d55e00'>⚠ Circular wait found (possible deadlock):"
                                        "</b><br>" + "<br>".join(descriptions))
        elif blocked:
            self.deadlock_label.setText(f"{len(blocked)} packet(s) stopped. "
                                        "<b style='color:#009e73'>No circular wait among them.</b>")
        else:
            self.deadlock_label.setText("<b style='color:#009e73'>✓ No packet stopped for this long.</b>")

        rows = []
        self._blocked_rows = blocked
        for message in blocked:
            following = analysis.next_hop(config, message.last_router, message.target)
            expected = analysis.hops(config, message.source, message.target)
            if id(message) in in_cycle:
                status = "in circular wait"
            elif message.hops_seen == 0:
                status = "no record after injection"
            else:
                status = "stopped mid-path"
            stopped = now - message.last_time
            rows.append([(str(message.injected), message.injected),
                         (str(message.last_time), message.last_time),
                         (str(stopped), stopped),
                         (_router_label(config, message.source), None),
                         (_router_label(config, message.target), None),
                         (config.get_string_service_name(message.service), None),
                         (_router_label(config, message.last_router), None),
                         (f"{message.hops_seen}/{expected}", message.hops_seen),
                         (_router_label(config, following) if following is not None else "local", None),
                         (status, None)])
        _fill_table(self.blocked_table, rows)

    def _update_links(self, now, capacity):
        config = self.mpsoc_config
        rows = []
        for address in range(config.get_pe_number()):
            router = self.mpsoc_information.get_router_information(address)
            for port in range(MPSoCConfig.NPORT):
                flits = router.get_port_total_volume_in_flits(port)
                if not flits:
                    continue
                throughput = analysis.mbps(config, flits, now)
                usage = throughput * 100.0 / capacity if capacity else 0.0
                rows.append([(_router_label(config, address), None),
                             (MPSoCConfig.get_port_string(port), None),
                             (str(flits), flits),
                             (f"{throughput:.2f}", throughput),
                             (f"{usage:.3f}", usage)])
        _fill_table(self.links_table, rows)

    def _update_apps(self, delivered, capacity):
        config = self.mpsoc_config
        rows = []
        for app, stats in sorted(analysis.traffic_by_app(delivered).items()):
            throughput = analysis.mbps(config, stats.flits, stats.active_cycles)
            rate = throughput * 100.0 / capacity if capacity else 0.0
            rows.append([(analysis.app_label(config, app), None),
                         (str(stats.messages), stats.messages),
                         (str(stats.flits), stats.flits),
                         (f"{throughput:.2f}", throughput),
                         (f"{rate:.3f}", rate),
                         (f"{stats.average_latency:.1f}", stats.average_latency),
                         (f"{stats.median_latency:g}", stats.median_latency),
                         (str(stats.latency_max), stats.latency_max),
                         (f"{stats.average_hops:.2f}", stats.average_hops)])
        _fill_table(self.apps_table, rows)


# ==========================================
# APPLICATION TIMELINE
# ==========================================
_PHASES = (
    # (nome, cor, início, fim)
    ("Mapping", QColor(230, 159, 0), lambda t: t.received, lambda t: t.mapped),
    ("Task allocation / release", QColor(170, 90, 200), lambda t: t.mapped if t.mapped >= 0 else t.received,
     lambda t: t.start),
    ("Execution", QColor(0, 114, 178), lambda t: t.start, lambda t: t.end),
)
_ALLOCATION_COLOR = QColor(0, 158, 115)
_TERMINATION_COLOR = QColor(213, 94, 0)


class TimelineChart(QWidget):
    """Uma linha por aplicação com as fases da admissão e da execução."""

    ROW_HEIGHT = 34
    TOP = 34
    LEFT = 170
    RIGHT = 20

    def __init__(self, mpsoc_config, parent=None):
        super().__init__(parent)
        self.mpsoc_config = mpsoc_config
        self.timelines = []
        self.range = (0, 1)
        self.current_time = -1
        self.setMouseTracking(True)

    def set_timelines(self, timelines, time_range):
        self.timelines = timelines
        self.set_range(*time_range)
        self.setMinimumHeight(self.TOP + len(timelines) * self.ROW_HEIGHT + 60)

    def set_range(self, start, end):
        self.range = (start, max(end, start + 1))
        self.update()

    def set_current_time(self, ticks):
        self.current_time = ticks
        self.update()

    def _x(self, ticks):
        start, end = self.range
        width = max(1, self.width() - self.LEFT - self.RIGHT)
        return self.LEFT + (ticks - start) * width / (end - start)

    def _row_rect(self, row):
        return QRect(self.LEFT, self.TOP + row * self.ROW_HEIGHT + 8, self.width() - self.LEFT - self.RIGHT,
                     self.ROW_HEIGHT - 16)

    def _phase_rects(self, row, timeline):
        rect = self._row_rect(row)
        for name, color, begin, end in _PHASES:
            start, finish = begin(timeline), end(timeline)
            if start < 0 or finish < 0 or finish < start:
                continue
            x1, x2 = self._x(start), self._x(finish)
            yield name, color, start, finish, QRect(int(x1), rect.top(), max(2, int(x2 - x1)), rect.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.base().color())
        text = palette.text().color()
        grid = QColor(text)
        grid.setAlpha(60)

        if not self.timelines:
            painter.setPen(text)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No application found in the trace")
            return

        bottom = self.TOP + len(self.timelines) * self.ROW_HEIGHT

        # Régua de tempo
        start, end = self.range
        painter.setPen(text)
        step = self._ruler_step(end - start)
        tick = (start // step + 1) * step
        while tick < end:
            x = int(self._x(tick))
            painter.setPen(grid)
            painter.drawLine(x, self.TOP, x, bottom)
            painter.setPen(text)
            painter.drawText(QRect(x - 60, bottom + 4, 120, 16), Qt.AlignmentFlag.AlignHCenter,
                             self._format_ticks(tick))
            tick += step
        painter.drawText(QRect(self.LEFT, bottom + 22, self.width() - self.LEFT - self.RIGHT, 16),
                         Qt.AlignmentFlag.AlignHCenter, "time")

        # Legenda
        x = self.LEFT
        for name, color, _begin, _end in _PHASES:
            painter.fillRect(QRect(x, 10, 12, 12), color)
            painter.drawText(x + 16, 21, name)
            x += 26 + painter.fontMetrics().horizontalAdvance(name)
        painter.setPen(QPen(_ALLOCATION_COLOR, 2))
        painter.drawLine(x, 10, x, 22)
        painter.setPen(text)
        painter.drawText(x + 6, 21, "task code arrived")
        x += 20 + painter.fontMetrics().horizontalAdvance("task code arrived")
        painter.setPen(QPen(_TERMINATION_COLOR, 2))
        painter.drawLine(x, 10, x, 22)
        painter.setPen(text)
        painter.drawText(x + 6, 21, "task terminated")

        for row, timeline in enumerate(self.timelines):
            rect = self._row_rect(row)
            painter.setPen(text)
            label = analysis.app_label(self.mpsoc_config, timeline.app)
            painter.drawText(QRect(6, rect.top(), self.LEFT - 12, rect.height()),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
            painter.setPen(grid)
            painter.drawLine(self.LEFT, rect.bottom() + 8, self.width() - self.RIGHT, rect.bottom() + 8)

            painter.setClipRect(QRect(self.LEFT, 0, self.width() - self.LEFT - self.RIGHT, self.height()))
            for _name, color, _start, _finish, phase_rect in self._phase_rects(row, timeline):
                painter.fillRect(phase_rect, color)
            for time, _pe in timeline.task_allocated.values():
                x = int(self._x(time))
                painter.setPen(QPen(_ALLOCATION_COLOR, 2))
                painter.drawLine(x, rect.top() - 5, x, rect.top() + 4)
            for time in timeline.task_terminated.values():
                x = int(self._x(time))
                painter.setPen(QPen(_TERMINATION_COLOR, 2))
                painter.drawLine(x, rect.bottom() - 4, x, rect.bottom() + 5)
            painter.setClipping(False)

        if self.current_time >= start and self.current_time <= end:
            x = int(self._x(self.current_time))
            painter.setPen(QPen(QColor(Qt.GlobalColor.red), 1, Qt.PenStyle.DashLine))
            painter.drawLine(x, self.TOP, x, bottom)

    def _format_ticks(self, ticks):
        us = _ticks_to_us(self.mpsoc_config, ticks)
        return f"{us / 1000:g} ms" if us >= 1000 else f"{us:g} µs"

    def _ruler_step(self, span):
        """Passo 1-2-5 em ticks que dá ~8 marcas na régua."""
        target = max(1, span / 8)
        power = 1
        while power * 10 <= target:
            power *= 10
        for factor in (1, 2, 5, 10):
            if power * factor >= target:
                return power * factor
        return power * 10

    def mouseMoveEvent(self, event):
        point = event.position().toPoint()
        for row, timeline in enumerate(self.timelines):
            for name, _color, start, finish, rect in self._phase_rects(row, timeline):
                if rect.adjusted(-2, 0, 2, 0).contains(point):
                    cycles = finish - start
                    QToolTip.showText(event.globalPosition().toPoint(),
                                      f"{analysis.app_label(self.mpsoc_config, timeline.app)}\n{name}\n"
                                      f"{start} → {finish} ticks\n{cycles} cycles "
                                      f"({_ticks_to_us(self.mpsoc_config, cycles):.2f} µs)", self)
                    return
        QToolTip.hideText()

    def wheelEvent(self, event):
        """Ctrl + roda: zoom em torno do mouse."""
        if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.ignore()
            return
        start, end = self.range
        width = max(1, self.width() - self.LEFT - self.RIGHT)
        anchor = start + (event.position().x() - self.LEFT) * (end - start) / width
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        new_start = anchor - (anchor - start) * factor
        new_end = anchor + (end - anchor) * factor
        self.set_range(max(0, int(new_start)), int(new_end))
        event.accept()


class ApplicationTimelineWindow(QWidget):
    """
    Linha do tempo da admissão de cada aplicação (protocolo da Seção 3.4 do
    artigo): pedido recebido pelo mapper, mapeamento, chegada do código de
    cada tarefa, liberação (TASK_RELEASE) e execução até o término.

    Analisa o traffic_router.txt inteiro (não só até o tempo atual) e o log
    do mapper_task (log/log<X>x<Y>.txt do cenário).
    """

    def __init__(self, mpsoc_config, simulation=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.mpsoc_config = mpsoc_config
        self.simulation = None
        self.timelines = []
        self.setWindowTitle("Application Timeline")
        self.resize(1000, 620)

        self.chart = TimelineChart(mpsoc_config)
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["Whole run", "Admission only"])
        self.zoom_combo.currentIndexChanged.connect(self._apply_zoom)
        reload_button = QPushButton("Reload")
        reload_button.clicked.connect(self.load)
        csv_button = QPushButton("Export CSV…")
        csv_button.clicked.connect(lambda: export.export_csv(self, self.table, "application_timeline"))
        png_button = QPushButton("Save PNG…")
        png_button.setToolTip("Save the chart as it is shown (with the current zoom)")
        png_button.clicked.connect(lambda: export.export_png(self, self.chart, "application_timeline"))
        self.source_label = QLabel()
        self.source_label.setWordWrap(True)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Zoom:"))
        controls.addWidget(self.zoom_combo)
        controls.addWidget(QLabel("(Ctrl + mouse wheel zooms around the cursor)"))
        controls.addStretch()
        controls.addWidget(csv_button)
        controls.addWidget(png_button)
        controls.addWidget(reload_button)

        chart_scroll = QScrollArea()
        chart_scroll.setWidgetResizable(True)
        chart_scroll.setWidget(self.chart)

        self.table = _sortable_table(["Application", "Tasks", "Request (tick)", "Mapped (tick)",
                                      "Released (tick)", "Terminated (tick)", "Mapping (cycles)",
                                      "Admission (cycles)", "Admission (µs)", "Execution (ms)"])
        self.table.setToolTip("Admission = from the request received by the mapper until TASK_RELEASE.\n"
                              "Double click a row to zoom the chart on that application's admission.")
        self.table.cellDoubleClicked.connect(self._zoom_on_row)
        export.install_export_actions(self.table, "application_timeline", csv_view=self.table)
        export.install_export_actions(self.chart, "application_timeline", png_widget=self.chart)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(chart_scroll)
        splitter.addWidget(self.table)
        splitter.setSizes([360, 220])

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.source_label)
        layout.addWidget(splitter)

        self.set_simulation(simulation)
        self.load()

    def set_simulation(self, simulation):
        if self.simulation is not None:
            try:
                self.simulation.time_changed.disconnect(self.chart.set_current_time)
            except (RuntimeError, TypeError):
                pass
        self.simulation = simulation
        if simulation is not None:
            simulation.time_changed.connect(self.chart.set_current_time)

    def set_information(self, mpsoc_config, simulation=None):
        self.mpsoc_config = mpsoc_config
        self.chart.mpsoc_config = mpsoc_config
        self.set_simulation(simulation)
        self.load()

    def closeEvent(self, event):
        self.set_simulation(None)
        super().closeEvent(event)

    def load(self):
        """Relê o traffic_router.txt inteiro com um leitor próprio (não mexe na simulação)."""
        config = self.mpsoc_config
        packets = analysis.read_all_packets(config)

        self.timelines, log_path = analysis.build_timelines(config, packets)
        self.trace_end = max((packet.time + packet.bandwidth_cycles for packet in packets), default=1)
        if log_path:
            self.source_label.setText(f"Request, mapping, release and termination from the mapper log: "
                                      f"{os.path.relpath(log_path, os.path.dirname(config.debug_file_path))}. "
                                      f"Task code arrival and task termination from traffic_router.txt.")
        else:
            self.source_label.setText("Mapper log not found (log/ folder of the scenario): showing only task "
                                      "code arrival and termination from traffic_router.txt.")

        self.chart.set_timelines(self.timelines, (0, self.trace_end))
        self._apply_zoom()
        self._fill_table()

    def _apply_zoom(self, *_):
        if self.zoom_combo.currentIndex() == 0 or not self.timelines:
            self.chart.set_range(0, self.trace_end)
            return
        firsts = [t.first_event for t in self.timelines if t.first_event >= 0]
        starts = [t.start for t in self.timelines if t.start >= 0]
        if not firsts or not starts:
            self.chart.set_range(0, self.trace_end)
            return
        start, end = min(firsts), max(starts)
        margin = max(1, (end - start) // 20)
        self.chart.set_range(max(0, start - margin), end + margin)

    def _zoom_on_row(self, row, _column):
        item = self.table.item(row, 0)
        if item is None:
            return
        timeline = next((t for t in self.timelines if t.app == item.data(ROW_ID_ROLE)), None)
        if timeline is None or timeline.first_event < 0 or timeline.start < 0:
            return
        start, end = timeline.first_event, timeline.start
        margin = max(1, (end - start) // 10)
        self.chart.set_range(max(0, start - margin), end + margin)

    def _fill_table(self):
        config = self.mpsoc_config

        def tick(value):
            return (str(value), value) if value >= 0 else ("-", -1)

        rows = []
        for timeline in self.timelines:
            admission = timeline.admission_cycles
            execution = timeline.execution_cycles
            label = analysis.app_label(config, timeline.app)
            rows.append([(label, None),
                         (str(timeline.task_count), timeline.task_count),
                         tick(timeline.received), tick(timeline.mapped), tick(timeline.start),
                         tick(timeline.end), tick(timeline.mapping_cycles), tick(admission),
                         (f"{_ticks_to_us(config, admission):.2f}", admission) if admission >= 0 else ("-", -1),
                         (f"{_ticks_to_us(config, execution) / 1000:.3f}", execution)
                         if execution >= 0 else ("-", -1)])
        # O ID da aplicação fica na primeira coluna, para o duplo clique
        _fill_table(self.table, rows, [timeline.app for timeline in self.timelines])
