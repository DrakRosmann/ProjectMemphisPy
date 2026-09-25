"""
Janelas "Communication Overview", "Task Mapping Overview" e "Message Log".

Refatoração de CommunicationOverview.java, TaskMappingFrame.java e da
janela de Message Log (MainFrame.showMessageList) do GraphicalDebugger
original. As duas janelas leem o estado dos roteadores
(MPSoCInformation) e se atualizam sozinhas enquanto a simulação da janela
principal avança.
"""

import os
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLabel, QListWidget, QMessageBox, QTableWidgetItem, QVBoxLayout,
                               QWidget)

import analysis
import export
from commsUi import Ui_Form as Ui_CommunicationOverview
from pe_matrix import PEMatrixWidget
from slave_matrix import SlaveMatrixWidget
from taskmap import Ui_TaskMap
from util.MPSoCConfig import MPSoCConfig

IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

# Intervalo mínimo entre duas atualizações da janela durante a simulação
REFRESH_INTERVAL_MS = 500

_PE_TYPE_NAMES = {
    MPSoCConfig.GLOBAL_MASTER: "Global M",
    MPSoCConfig.CLUSTER_MASTER: "Cluster M",
    MPSoCConfig.SLAVE: "Slave",
}


def _router_label(mpsoc_config, address):
    if mpsoc_config.router_addressing == MPSoCConfig.HAMILTONIAN:
        return str(address)
    return mpsoc_config.ham_address_to_xy_label(address)


class _LiveOverview(QWidget):
    """
    Base das janelas que acompanham a simulação.

    Em vez de redesenhar a cada pacote (o que travaria o modo rápido), a
    janela só marca que os dados mudaram; um QTimer redesenha no máximo a
    cada REFRESH_INTERVAL_MS, e apenas se a janela estiver visível.
    """

    def __init__(self, mpsoc_config, mpsoc_information, simulation=None):
        super().__init__()
        self.mpsoc_config = mpsoc_config
        self.mpsoc_information = mpsoc_information
        self.simulation = None
        self.matrix = None
        self.live_update = True
        self._dirty = True

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_if_dirty)
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

        self._connect_simulation(simulation)

    def _connect_simulation(self, simulation):
        if self.simulation is not None:
            try:
                self.simulation.time_changed.disconnect(self.mark_dirty)
            except (RuntimeError, TypeError):
                pass  # controlador antigo já destruído
        self.simulation = simulation
        if simulation is not None:
            simulation.time_changed.connect(self.mark_dirty)

    def set_information(self, mpsoc_config, mpsoc_information, simulation=None):
        """Troca a fonte de dados (novo debug ou Reset Simulation)."""
        self.mpsoc_config = mpsoc_config
        self.mpsoc_information = mpsoc_information
        self._connect_simulation(simulation)
        self.rebuild()

    def mark_dirty(self, *_):
        self._dirty = True

    def _refresh_if_dirty(self):
        if self._dirty and self.live_update and self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        self._connect_simulation(None)
        super().closeEvent(event)

    def _set_matrix(self, matrix):
        """Coloca a grade dentro do scrollArea gerado pelo .ui, trocando a anterior."""
        layout = self.scrollAreaWidgetContents.layout()
        if layout is None:
            layout = QVBoxLayout(self.scrollAreaWidgetContents)
            layout.setContentsMargins(0, 0, 0, 0)
        while layout.count():
            old = layout.takeAt(0).widget()
            if old is not None:
                old.deleteLater()
        layout.addWidget(matrix)

    def rebuild(self):
        raise NotImplementedError

    def refresh(self):
        raise NotImplementedError


class CommunicationOverviewWindow(_LiveOverview, Ui_CommunicationOverview):
    """
    Mapa de calor do tráfego: cada célula mostra a porcentagem do volume
    (flits) ou da banda (ciclos) que passou pelo roteador.

    Filtros (iguais ao Java):
      - All Services: todo o tráfego; senão, só o serviço escolhido, com a
        porcentagem calculada sobre
          Global      -> tráfego desse serviço em toda a NoC
          All traffic -> todo o tráfego da NoC
          Router      -> todo o tráfego do próprio roteador
      - Volume / Bandwidth: flits ou ciclos de enlace
    """

    def __init__(self, mpsoc_config, mpsoc_information, simulation=None):
        super().__init__(mpsoc_config, mpsoc_information, simulation)
        self.setupUi(self)
        self.setWindowTitle("Communication Overview")

        # O .ui usa um caminho relativo que só funciona rodando da pasta do projeto
        self.label.setPixmap(QPixmap(os.path.join(IMAGES_DIR, "color_spectrum.png")))
        self.label_3.setText("high")
        self.label_3.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Estatísticas: uma linha, colunas Bigger / Average / Small
        self.tableWidget.setRowCount(1)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Largura do original (379 px) para caber "R. 2x2: 19.472%" sem cortar
        self.groupBox_3.setMinimumWidth(380)

        # Estado inicial igual ao Java: todos os serviços, "Global", volume
        self.checkBox.setChecked(True)
        self.radioButton_2.setChecked(True)
        self.radioButton_4.setChecked(True)

        export.install_export_actions(self, "communication_overview", png_widget=self)
        export.install_export_actions(self.tableWidget, "communication_statistics", csv_view=self.tableWidget,
                                      png_widget=self)

        self.checkBox.toggled.connect(self._on_filter_changed)
        self.comboBox.currentIndexChanged.connect(self._on_filter_changed)
        for radio in (self.radioButton, self.radioButton_2, self.radioButton_3,
                      self.radioButton_4, self.radioButton_5):
            radio.toggled.connect(self._on_radio_toggled)

        self.rebuild()

    def rebuild(self):
        """Recria a grade e a lista de serviços para a configuração atual."""
        config = self.mpsoc_config

        self.comboBox.blockSignals(True)
        self.comboBox.clear()
        for service in config.service_reference:
            self.comboBox.addItem(config.get_string_service_name(service), service)
        self.comboBox.blockSignals(False)

        self.matrix = SlaveMatrixWidget(config.mpsoc_x, config.mpsoc_y)
        self._set_matrix(self.matrix)
        self._update_filter_state()
        self.refresh()

    def _on_radio_toggled(self, checked):
        # Cada troca dispara dois toggled (um desmarca, outro marca); basta um
        if checked:
            self.refresh()

    def _on_filter_changed(self, *_):
        self._update_filter_state()
        self.refresh()

    def _update_filter_state(self):
        filter_by_service = not self.checkBox.isChecked()
        for widget in (self.comboBox, self.radioButton, self.radioButton_2, self.radioButton_3):
            widget.setEnabled(filter_by_service)
        if not filter_by_service:
            self.radioButton_2.setChecked(True)

    def selected_services(self):
        """Lista de serviços filtrados; vazia = todos."""
        if self.checkBox.isChecked() or self.comboBox.currentIndex() < 0:
            return []
        return [self.comboBox.currentData()]

    def refresh(self):
        self._dirty = False
        if self.matrix is None:
            return

        config = self.mpsoc_config
        info = self.mpsoc_information
        services = self.selected_services()
        use_volume = self.radioButton_4.isChecked()
        unit = "flits" if use_volume else "cycles"

        def router_total(router):
            if use_volume:
                return router.get_router_total_volume_in_flits()
            return router.get_router_total_bandwidth_in_cycles()

        def router_value(router):
            if not services:
                return router_total(router)
            if use_volume:
                return router.get_router_total_services_volume_in_flits(services)
            return router.get_router_total_services_bandwidth_in_cycles(services)

        addresses = range(config.get_pe_number())
        values = {address: router_value(info.get_router_information(address)) for address in addresses}

        # Base da porcentagem
        if self.radioButton.isChecked() and services:        # All traffic
            noc_total = info.get_total_noc_volume() if use_volume else info.get_total_noc_bandwidth()
        else:                                                 # Global
            noc_total = sum(values.values())

        percents = {}
        for address in addresses:
            if self.radioButton_3.isChecked() and services:  # Router
                total = router_total(info.get_router_information(address))
            else:
                total = noc_total
            percents[address] = values[address] * 100.0 / total if total else 0.0

        for (x, y), cell in self.matrix.slaves.items():
            address = config.xy_to_ham_addr((x << 8) | y)
            percent = percents[address]

            # Mesma escala do Java: azul (0%) até vermelho (100%)
            hue = 0.65 - percent * 0.65 / 100.0
            color = QColor.fromHsvF(max(0.0, hue), 1.0, 0.8)

            title = f"{_PE_TYPE_NAMES[config.get_pe_type(address)]} {_router_label(config, address)}"
            cell.set_values(title, f"{percent:.3f}%", unit, color)

        self._update_statistics(percents)

    def _update_statistics(self, percents):
        if not percents:
            return
        config = self.mpsoc_config

        # Em empate, fica o primeiro roteador na ordem de endereço
        bigger = max(percents, key=lambda address: percents[address])
        smaller = min(percents, key=lambda address: percents[address])
        average = sum(percents.values()) / len(percents)

        values = (
            f"R. {_router_label(config, bigger)}: {percents[bigger]:.3f}%",
            f"{average:.3f}%",
            f"R. {_router_label(config, smaller)}: {percents[smaller]:.3f}%",
        )
        for column, value in enumerate(values):
            self.tableWidget.setItem(0, column, QTableWidgetItem(value))


class TaskMappingWindow(_LiveOverview, Ui_TaskMap):
    """
    Mostra em cada PE as tarefas alocadas (RUN) e terminadas (TER) até o
    tempo atual da simulação, com uma cor por aplicação.
    """

    # Semente fixa: cada aplicação mantém a mesma cor entre execuções
    COLOR_SEED = 20

    def __init__(self, mpsoc_config, mpsoc_information, simulation=None):
        super().__init__(mpsoc_config, mpsoc_information, simulation)
        self.setupUi(self)

        export.install_export_actions(self, "task_mapping", png_widget=self)

        # O .ui repete "All tasks status" no terceiro botão
        self.radioButton_3.setText("Only Terminated")

        # "Only Running" é o filtro inicial, como no Java
        self.radioButton_2.setChecked(True)
        for radio in (self.radioButton, self.radioButton_2, self.radioButton_3):
            radio.toggled.connect(self._on_radio_toggled)
        self.checkBox.toggled.connect(self.refresh)

        # Botão alterna entre atualização automática e manual
        self.pushButton.setCheckable(True)
        self.pushButton.setChecked(True)
        self.pushButton.toggled.connect(self._on_update_toggled)
        self._on_update_toggled(True)

        self._warned_missing_names = False
        self.rebuild()

    def rebuild(self):
        config = self.mpsoc_config
        self.setWindowTitle(f"Task Mapping Overview: {config.get_testcase_path() or config.debug_file_path}")

        self.app_colors = {}
        self.color_generator = random.Random(self.COLOR_SEED)

        self.matrix = PEMatrixWidget(config.mpsoc_x, config.mpsoc_y)
        self._set_matrix(self.matrix)
        self.refresh()

    def _on_radio_toggled(self, checked):
        if checked:
            self.refresh()

    def _on_update_toggled(self, checked):
        self.live_update = checked
        self.pushButton.setText("Updating" if checked else "Update")
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.mpsoc_config.task_name_hash and not self._warned_missing_names:
            self._warned_missing_names = True
            QMessageBox.warning(self, "Warning", "Task name representation not informed\n"
                                "The task ID will be represented by numbers")

    def _app_color(self, app_id):
        if app_id not in self.app_colors:
            self.app_colors[app_id] = QColor.fromRgb(self.color_generator.randrange(0xFFFFFF))
        return self.app_colors[app_id]

    def refresh(self):
        self._dirty = False
        if self.matrix is None:
            return

        config = self.mpsoc_config
        task_names = config.task_name_hash
        only_running = self.radioButton_2.isChecked()
        only_terminated = self.radioButton_3.isChecked()
        without_id = self.checkBox.isChecked()

        for (x, y), cell in self.matrix.pes.items():
            address = config.xy_to_ham_addr((x << 8) | y)
            router = self.mpsoc_information.get_router_information(address)

            # Último estado de cada tarefa neste PE
            status = {}
            for task in router.get_tasks_information():
                if task.service == "ALLOCATED":
                    status[task.id] = "RUN"
                elif task.service == "TERMINATED":
                    status[task.id] = "TER"

            tasks = []
            for task_id in sorted(status):
                if only_running and status[task_id] == "TER":
                    continue
                if only_terminated and status[task_id] == "RUN":
                    continue

                name = task_names.get(task_id, f"{task_id >> 8}  {task_id & 0xFF}")
                text = f"{name}  {status[task_id]}" if without_id else f"{name}  {task_id}  {status[task_id]}"
                tasks.append((text, self._app_color(task_id >> 8)))

            cell.set_tasks(f"PE {_router_label(config, address)}", tasks)


class MessageLogWindow(_LiveOverview):
    """
    Lista as mensagens trocadas entre os PEs, na ordem em que aparecem no
    traffic_router.txt:

      ---->>> origem send message to destino service SERVIÇO
          (pacote entrando na NoC pela porta local do PE de origem)
      <<<---- destino receive message with service SERVIÇO
          (pacote chegando ao roteador de destino)

    Mostra todos os pacotes já lidos e acrescenta os novos conforme a
    simulação avança. A caixa "Application" mostra só as mensagens de uma
    aplicação (pelas tarefas de origem/destino do pacote).
    """

    def __init__(self, mpsoc_config, mpsoc_information, simulation=None):
        super().__init__(mpsoc_config, mpsoc_information, simulation)
        self.setWindowTitle("Message Log")
        self.resize(500, 600)

        self.app_combo = QComboBox()
        self.app_combo.currentIndexChanged.connect(lambda _index: self.rebuild())
        app_row = QHBoxLayout()
        app_row.setContentsMargins(6, 6, 6, 0)
        app_row.addWidget(QLabel("Application:"))
        app_row.addWidget(self.app_combo, 1)

        self.list_widget = QListWidget(self)
        self.list_widget.setUniformItemSizes(True)  # listas longas continuam rápidas
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(app_row)
        layout.addWidget(self.list_widget)

        self._fill_app_combo()

        self._packets_listed = 0
        self.rebuild()

    def _fill_app_combo(self):
        self.known_apps = analysis.known_app_ids(self.mpsoc_config)
        self.app_combo.blockSignals(True)
        self.app_combo.clear()
        self.app_combo.addItem("All", None)
        for app in sorted(self.known_apps):
            self.app_combo.addItem(analysis.app_label(self.mpsoc_config, app), app)
        self.app_combo.blockSignals(False)

    def set_information(self, mpsoc_config, mpsoc_information, simulation=None):
        self.mpsoc_config = mpsoc_config
        self._fill_app_combo()
        super().set_information(mpsoc_config, mpsoc_information, simulation)

    def rebuild(self):
        self.list_widget.clear()
        self._packets_listed = 0
        self.refresh()

    def _message(self, packet):
        config = self.mpsoc_config
        service = config.get_string_service_name(packet.service)
        router = _router_label(config, packet.router_address)
        message = None

        if packet.input_port in (MPSoCConfig.LOCAL0, MPSoCConfig.LOCAL1):
            target = _router_label(config, packet.target_router)
            message = f"---->>> {router} send message to {target} service {service}"

        if packet.router_address == packet.target_router:
            message = f"<<<---- {router} receive message with service  {service}"

        return message

    def refresh(self):
        self._dirty = False

        # all_packets só cresce (voltar no tempo reaproveita os pacotes já lidos),
        # então basta acrescentar os pacotes novos desde a última atualização
        packets = self.mpsoc_information.read_traffic.all_packets
        new_packets = packets[self._packets_listed:]
        if not new_packets:
            return
        self._packets_listed = len(packets)

        scrollbar = self.list_widget.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()

        app = self.app_combo.currentData()
        if app is not None:
            new_packets = [packet for packet in new_packets if app in analysis.packet_apps(packet, self.known_apps)]
        messages = [message for message in map(self._message, new_packets) if message is not None]
        self.list_widget.addItems(messages)

        # Acompanha o fim da lista, a menos que o usuário tenha rolado para cima
        if at_bottom:
            self.list_widget.scrollToBottom()
