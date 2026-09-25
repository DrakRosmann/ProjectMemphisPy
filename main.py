import os
import sys

from PySide6.QtGui import Qt, QPalette, QColor, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, QWidget, QInputDialog,
                               QVBoxLayout, QHBoxLayout, QScrollArea, QTableWidgetItem, QTableWidget, QLabel,
                               QHeaderView)

import theme
from ui_mainwindow import MainWindow
from util import MPSoCConfig
from information import MPSoCInformation
from router_matrix import RouterMatrixWidget
from simulation import SimulationController, MAX_REPAINT_SPEED, ticks_to_ms
from overview_windows import CommunicationOverviewWindow, MessageLogWindow, TaskMappingWindow
from deloream import DeloreamWindow
from router_info_window import RouterInfoWindow
from platform_setup import PlatformSetupDialog
from filter_window import FilterWindow
from help_dialogs import AboutDialog, show_packet_format
import projects


class MinhaJanela(QMainWindow, MainWindow):
    filePath = ""
    mpconfig = None
    mpsoc_information = None
    router_matrix_widget = None
    frame_scroll_area = None
    simulation = None
    communication_window = None
    task_mapping_window = None
    message_log_window = None
    deloream_window = None
    router_info_windows = None
    simulation_ticks = 0
    filter_window = None

    WINDOW_TITLE = "Memphis-V Graphical Debugger"

    # Arquivos obrigatórios em um diretório de debug
    REQUIRED_FILES = ("platform.cfg", "services.cfg", "traffic_router.txt")

    # Variável de controle do tema
    is_dark_mode = False

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(self.WINDOW_TITLE)

        # ---------------------------------------------------------
        # SISTEMA DE TEMA (DARK/LIGHT MODE)
        # ---------------------------------------------------------
        # Limpa a paleta fixa gerada pelo arquivo .ui para herdar a do App
        self.setPalette(QPalette())

        # Ação marcável no menu "Edit"; o último tema escolhido é restaurado
        self.actionToggle_Theme = QAction("Dark Mode", self)
        self.actionToggle_Theme.setCheckable(True)
        self.actionToggle_Theme.setShortcut(QKeySequence("Ctrl+T"))
        self.menuEdit.addAction(self.actionToggle_Theme)
        self.actionToggle_Theme.toggled.connect(self.set_dark_mode)

        self.set_dark_mode(theme.load_dark_mode())
        # ---------------------------------------------------------

        self.actionCommunication_Overview.setEnabled(False)
        self.actionDeloream.setEnabled(False)
        self.actionTask_Mapping_Overview.setEnabled(False)
        self.actionServices_List.setEnabled(False)
        self.actionMessage_Log.setEnabled(False)
        self.actionTask_List.setEnabled(False)

        # Atalhos do menu File iguais aos do Java (o .ui só define Ctrl+N e Ctrl+S)
        self.actionRest_Graphical_Path.setText("Reset Graphical Path")
        for action, shortcut in ((self.actionOpen_Project, "Ctrl+O"), (self.actionDelete_Project, "Ctrl+D"),
                                 (self.actionReset_Simulation, "Ctrl+R"), (self.actionRest_Graphical_Path, "Ctrl+G"),
                                 (self.actionExit, "Ctrl+Q")):
            action.setShortcut(QKeySequence(shortcut))

        self.actionSave_Project.triggered.connect(self.save_project)
        self.actionOpen_Project.triggered.connect(self.open_project)
        self.actionDelete_Project.triggered.connect(self.delete_project)
        self.actionAbout.triggered.connect(lambda: AboutDialog(self).exec())
        self.actionPacket_Format.triggered.connect(lambda: show_packet_format(self))

        self.actionPrint_Link_Usage = QAction("Print Router Total Link Usage", self)
        self.menuEdit.addAction(self.actionPrint_Link_Usage)
        self.actionPrint_Link_Usage.triggered.connect(self.configure_link_usage_print)

        self.actionExit.triggered.connect(self.close)
        self.actionNew_Debugging.triggered.connect(self.open_file)
        self.horizontalSlider.valueChanged.connect(self.update_slide)
        self.label_2.setText(f"{self.horizontalSlider.value()}")
        self.actionCommunication_Overview.triggered.connect(self.open_communication)
        self.actionTask_Mapping_Overview.triggered.connect(self.open_taskmap)
        self.actionTask_List.triggered.connect(self.taskList)
        self.actionServices_List.triggered.connect(self.servicesList)
        self.actionMessage_Log.triggered.connect(self.open_message_log)
        self.actionDeloream.triggered.connect(self.open_deloream)
        self.actionPlatform_Setup.triggered.connect(self.open_platform_setup)
        self.actionService_and_PE_Filter.setShortcut(QKeySequence("Ctrl+F"))
        self.actionService_and_PE_Filter.triggered.connect(self.open_filter)

        # ---------------------------------------------------------
        # CONTROLE DA SIMULAÇÃO
        # ---------------------------------------------------------
        self.horizontalSlider.setRange(0, 100)
        self.horizontalSlider.setValue(MAX_REPAINT_SPEED)

        self.pushButton_2.clicked.connect(self.next_packet)       # >||
        self.pushButton.clicked.connect(self.play_simulation)     # >
        self.pushButton_3.clicked.connect(self.stop_simulation)   # STOP
        self.toolButton.setText("Go")
        self.toolButton.clicked.connect(self.go_to_time)
        self.lineEdit.setPlaceholderText("Time in ticks")
        self.lineEdit.returnPressed.connect(self.go_to_time)
        self.actionReset_Simulation.triggered.connect(self.reset_simulation)
        self.actionRest_Graphical_Path.triggered.connect(self.reset_graphical_path)

        # Tabela "Current Packet Information" com uma única linha
        self.tableWidget.setRowCount(1)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.reset_current_packet_table()

        # Tempo de simulação exibido na caixa "Speed Control"
        self.build_speed_control()
        self.update_simulation_time(0)

        self.set_simulation_buttons(loaded=False)
        self.actionReset_Simulation.setEnabled(False)
        self.actionRest_Graphical_Path.setEnabled(False)

    # ==========================================
    # LÓGICA DE MUDANÇA DE TEMA
    # ==========================================
    def toggle_theme(self):
        self.set_dark_mode(not self.is_dark_mode)

    def set_dark_mode(self, dark):
        """Aplica o tema na aplicação inteira e na grade de roteadores."""
        self.is_dark_mode = dark
        theme.apply_theme(dark)
        theme.save_dark_mode(dark)

        # Mantém a marcação do menu em sincronia sem disparar o sinal de novo
        self.actionToggle_Theme.blockSignals(True)
        self.actionToggle_Theme.setChecked(dark)
        self.actionToggle_Theme.blockSignals(False)

        if self.router_matrix_widget is not None:
            self.router_matrix_widget.apply_theme(dark)

    # ==========================================

    def open_communication(self):
        if self.filePath == "":
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        # Reaproveita a janela se já estiver aberta
        if self.communication_window is None or not self.communication_window.isVisible():
            self.communication_window = CommunicationOverviewWindow(
                self.mpconfig, self.mpsoc_information, self.simulation)
        self.communication_window.show()
        self.communication_window.raise_()
        self.communication_window.activateWindow()

    def open_deloream(self):
        if self.filePath == "":
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return

        testcase_path = self.mpconfig.get_testcase_path()
        if testcase_path is None:
            QMessageBox.warning(self, "Deloream",
                                "The debug directory must be named \"debug\" and be inside the "
                                "testcase folder (the one that contains the log/ folder).")
            return

        # Mesma janela enquanto estiver aberta; outro cenário recarrega a árvore
        if self.deloream_window is None or not self.deloream_window.isVisible():
            self.deloream_window = DeloreamWindow(testcase_path)
        elif self.deloream_window.testcase_path != testcase_path:
            self.deloream_window.load_testcase(testcase_path)
        self.deloream_window.show()
        self.deloream_window.raise_()
        self.deloream_window.activateWindow()

    def open_platform_setup(self):
        if self.simulation is None:
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        if PlatformSetupDialog(self.mpconfig, self.simulation.checkpoint, self).exec():
            # O tempo em ms depende do período de clock
            self.update_simulation_time(self.simulation_ticks)

    def open_filter(self):
        if self.simulation is None:
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        # Como no Java, apaga o caminho desenhado antes de trocar o filtro
        self.simulation.reset_graphical_path()
        self.filter_window.show()
        self.filter_window.raise_()
        self.filter_window.activateWindow()

    def open_message_log(self):
        if self.filePath == "":
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        if self.message_log_window is None or not self.message_log_window.isVisible():
            self.message_log_window = MessageLogWindow(
                self.mpconfig, self.mpsoc_information, self.simulation)
        self.message_log_window.show()
        self.message_log_window.raise_()
        self.message_log_window.activateWindow()

    def open_taskmap(self):
        if self.filePath == "":
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        if self.task_mapping_window is None or not self.task_mapping_window.isVisible():
            self.task_mapping_window = TaskMappingWindow(
                self.mpconfig, self.mpsoc_information, self.simulation)
        self.task_mapping_window.show()
        self.task_mapping_window.raise_()
        self.task_mapping_window.activateWindow()

    def open_router_info(self, router_address):
        """Abre a janela "Router Information" do roteador clicado (uma por roteador)."""
        if self.router_info_windows is None:
            self.router_info_windows = {}

        window = self.router_info_windows.get(router_address)
        if window is None:
            window = RouterInfoWindow(self.mpconfig, self.mpsoc_information, router_address, self.simulation)
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            window.destroyed.connect(lambda *_, address=router_address:
                                     self.router_info_windows.pop(address, None))
            self.router_info_windows[router_address] = window
        window.show()
        window.raise_()
        window.activateWindow()

    def close_router_info_windows(self):
        windows = self.router_info_windows or {}
        while windows:
            windows.popitem()[1].close()

    def update_slide(self, valor):
        self.label_2.setText(str(valor))
        if self.simulation is not None:
            self.simulation.set_speed(valor)

    def open_file(self):
        caminho = QFileDialog.getExistingDirectory(self, "Open Debug Directory", "./")
        if caminho != "":
            self.load_debug(caminho)

    def load_debug(self, caminho, title=None):
        """Carrega um diretório de debug. Retorna False se ele não for válido."""
        # Verifica se o diretório possui todos os arquivos necessários
        faltando = [arquivo for arquivo in self.REQUIRED_FILES
                    if not os.path.isfile(os.path.join(caminho, arquivo))]
        if faltando:
            QMessageBox.critical(
                self,
                "Diretório invalido",
                "O diretório selecionado não é um diretório de debug valido.\n\n"
                "Selecione um diretório valido"
            )
            return False

        self.filePath = caminho
        self.actionCommunication_Overview.setEnabled(True)
        self.actionDeloream.setEnabled(True)
        self.actionTask_Mapping_Overview.setEnabled(True)
        self.actionServices_List.setEnabled(True)
        self.actionMessage_Log.setEnabled(True)
        self.actionTask_List.setEnabled(True)

        self.mpconfig = MPSoCConfig.MPSoCConfig(self.filePath)

        # Fecha o traffic_router.txt do debug anterior antes de abrir o novo
        if self.mpsoc_information is not None:
            self.mpsoc_information.close()
        self.mpsoc_information = MPSoCInformation(self.mpconfig)
        self.build_router_matrix()
        self.start_simulation()

        self.setWindowTitle(f"{self.WINDOW_TITLE}: {title or self.mpconfig.get_testcase_path() or caminho}")
        return True

    # ==========================================
    # PROJETOS (.hdf)
    # ==========================================
    def save_project(self):
        if self.mpconfig is None:
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return

        name = ""
        while True:
            name, ok = QInputDialog.getText(self, "Save Project", "Inform the debugging project name", text=name)
            if not ok:
                return
            name = name.strip()
            error = projects.validate_name(name)
            if error is None:
                break
            QMessageBox.critical(self, "Error", error)

        if os.path.exists(projects.project_path(name)):
            answer = QMessageBox.question(self, "Save Project", f"Project {name} already exists. Overwrite it?")
            if answer != QMessageBox.StandardButton.Yes:
                return

        try:
            projects.save_project(name, self.filePath)
        except OSError as error:
            QMessageBox.critical(self, "Save Project", f"Could not save the project {name}:\n{error}")
            return
        self.setWindowTitle(f"{self.WINDOW_TITLE}: {name}")
        self.statusbar.showMessage(f"Project saved in {projects.project_path(name)}", 5000)

    def _choose_project(self, title, accept_label=None):
        dialog = QFileDialog(self, title, projects.projects_dir(), projects.PROJECT_FILTER)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if accept_label is not None:
            dialog.setLabelText(QFileDialog.DialogLabel.Accept, accept_label)
        if dialog.exec() and dialog.selectedFiles():
            return dialog.selectedFiles()[0]
        return None

    def open_project(self):
        path = self._choose_project("Open Project")
        if path is None:
            return
        try:
            debug_dir = projects.read_project(path)
        except OSError:
            QMessageBox.critical(self, "Error", "File not exists")
            return

        if not os.path.isdir(debug_dir):
            QMessageBox.critical(self, "Open Project",
                                 f"The debug directory of project {projects.project_name(path)} no longer exists:\n"
                                 f"{debug_dir or '(empty file)'}")
            return
        self.stop_simulation()
        self.load_debug(debug_dir, projects.project_name(path))

    def delete_project(self):
        path = self._choose_project("Delete Project", "Delete")
        if path is None:
            return
        name = projects.project_name(path)
        answer = QMessageBox.question(self, "Delete Project", f"Delete the project {name}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(path)
        except OSError:
            QMessageBox.warning(self, "Attention", f"Error during the deletion of project: {name}")
            return
        QMessageBox.information(self, "Delete Project", f"Project {name} successfully deleted!")

    def configure_link_usage_print(self):
        """
        "Print Router Total Link Usage" do Java: a cada checkpoint imprime no
        terminal a soma do uso dos enlaces do roteador escolhido (ou o tempo).
        """
        if self.simulation is None:
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return

        current = self.simulation.link_usage_router
        default = "" if current < 0 else self._router_label(current)
        label, ok = QInputDialog.getText(self, "Print Router Total Link Usage",
                                         "Inform the router address (empty to stop printing)", text=default)
        if not ok:
            return
        label = label.strip()
        if label == "":
            self.simulation.link_usage_router = -1
            return
        try:
            if self.mpconfig.router_addressing == MPSoCConfig.MPSoCConfig.XY:
                address = self.mpconfig.xy_label_to_ham_address(label)
            else:
                address = int(label)
            if not 0 <= address < self.mpconfig.get_pe_number():
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Attention", f"Invalid router address: {label}")
            return

        mode, ok = QInputDialog.getItem(self, "Print Router Total Link Usage", "Inform the printing type:",
                                        ["1 - Link Usage", "2 - Time"], 0, False)
        if not ok:
            return
        self.simulation.link_usage_router = address
        self.simulation.print_link_usage = mode.startswith("1")

    def _router_label(self, address):
        if self.mpconfig.router_addressing == MPSoCConfig.MPSoCConfig.XY:
            return self.mpconfig.ham_address_to_xy_label(address)
        return str(address)

    def build_router_matrix(self):
        """
        Monta a matriz de roteadores dentro do self.frame do MainWindow,
        usando mpsoc_x/mpsoc_y (nº de clusters) e cluster_x/cluster_y
        (roteadores por cluster) lidos do arquivo de configuração atual.
        """
        if self.mpconfig is None:
            return

        # Janelas de roteador pertencem ao debug anterior
        self.close_router_info_windows()

        # Cria a matriz de roteadores com base na configuração carregada
        self.router_matrix_widget = RouterMatrixWidget(
            self.mpconfig.mpsoc_x,
            self.mpconfig.mpsoc_y,
            self.mpconfig.cluster_x,
            self.mpconfig.cluster_y,
            mpsoc_config=self.mpconfig,
        )
        self.router_matrix_widget.apply_theme(self.is_dark_mode)
        for router in self.router_matrix_widget.routers.values():
            router.clicked.connect(self.open_router_info)

        # Primeira vez: cria um QScrollArea dentro do self.frame para
        # comportar malhas maiores que a área visível da janela.
        if self.frame_scroll_area is None:
            self.frame_scroll_area = QScrollArea(self.frame)
            # IMPORTANTE: widgetResizable=False. Com True, o Qt estica a
            # matriz para preencher todo o frame e, sem stretch factor nas
            # colunas/linhas do QGridLayout, esse espaço extra é distribuído
            # como gaps entre os roteadores. Com False, a matriz mantém seu
            # tamanho natural (roteadores colados) e o scroll aparece só se
            # ela for maior que a área visível.
            self.frame_scroll_area.setWidgetResizable(False)
            self.frame_scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

            frame_layout = QVBoxLayout(self.frame)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            frame_layout.addWidget(self.frame_scroll_area)
            self.frame.setLayout(frame_layout)

        # Troca (ou define) o widget interno do scroll pela nova matriz,
        # substituindo uma matriz antiga caso um novo arquivo seja aberto.
        old_widget = self.frame_scroll_area.takeWidget()
        if old_widget is not None:
            old_widget.deleteLater()

        # Garante que a matriz assuma seu tamanho real (layout aplicado)
        # antes de ser exibida dentro do scroll area sem resize forçado.
        self.router_matrix_widget.adjustSize()
        self.frame_scroll_area.setWidget(self.router_matrix_widget)

    # ==========================================
    # SIMULAÇÃO DOS ROTEADORES
    # ==========================================
    def start_simulation(self):
        """Cria o controlador da simulação para o debug carregado (ou recarregado)."""
        if self.simulation is not None:
            self.simulation.stop()
            self.simulation.deleteLater()

        self.simulation = SimulationController(self.mpconfig, self.mpsoc_information,
                                               self.router_matrix_widget, self)
        self.simulation.set_speed(self.horizontalSlider.value())

        # Filtro de serviços/PEs: um por debug carregado (as listas voltam a vazio)
        if self.filter_window is not None:
            self.filter_window.close()
            self.filter_window.deleteLater()
        self.filter_window = FilterWindow(self.mpconfig, self)
        self.simulation.packet_filter = self.filter_window.filter

        # Janelas de visão geral abertas passam a acompanhar o novo debug
        for window in (self.communication_window, self.task_mapping_window, self.message_log_window):
            if window is not None and window.isVisible():
                window.set_information(self.mpconfig, self.mpsoc_information, self.simulation)
        self.simulation.time_changed.connect(self.update_simulation_time)
        self.simulation.packet_changed.connect(self.update_current_packet_table)
        self.simulation.running_changed.connect(self.on_simulation_running_changed)
        self.simulation.finished.connect(self.on_simulation_finished)
        self.simulation.unknown_service.connect(self.on_unknown_service)

        self.update_simulation_time(0)
        self.reset_current_packet_table()
        self.set_simulation_buttons(loaded=True)
        self.actionReset_Simulation.setEnabled(True)
        self.actionRest_Graphical_Path.setEnabled(True)

    def set_simulation_buttons(self, loaded, running=False):
        self.pushButton.setEnabled(loaded and not running)
        self.pushButton_2.setEnabled(loaded and not running)
        self.pushButton_3.setEnabled(loaded and running)
        self.toolButton.setEnabled(loaded and not running)
        self.lineEdit.setEnabled(loaded and not running)

    def play_simulation(self):
        if self.simulation is not None:
            self.simulation.play()

    def stop_simulation(self):
        if self.simulation is not None:
            self.simulation.stop()

    def next_packet(self):
        if self.simulation is not None:
            self.simulation.step()

    def go_to_time(self):
        if self.simulation is None:
            return
        try:
            self.simulation.go_to_time(int(self.lineEdit.text()))
        except ValueError:
            QMessageBox.warning(self, "Attention", "Enter only numbers and valid times!\n\n"
                                "It is only possible to go to a time already simulated.")

    def reset_simulation(self):
        """
        Recarrega o debug atual (platform.cfg, services.cfg e traffic_router.txt)
        e volta a simulação para o início, como o "Reset Simulation" do original.
        """
        if self.mpconfig is None:
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return

        self.stop_simulation()

        # Os arquivos podem ter sido apagados/regerados desde que o debug foi aberto
        faltando = [arquivo for arquivo in self.REQUIRED_FILES
                    if not os.path.isfile(os.path.join(self.filePath, arquivo))]
        if faltando:
            QMessageBox.critical(
                self,
                "Reset Simulation",
                "Não foi possível resetar a simulação. Arquivos não encontrados:\n"
                + "\n".join(f"• {arquivo}" for arquivo in faltando)
            )
            return

        self.mpconfig = MPSoCConfig.MPSoCConfig(self.filePath)
        if self.mpsoc_information is not None:
            self.mpsoc_information.close()
        self.mpsoc_information = MPSoCInformation(self.mpconfig)
        self.build_router_matrix()
        self.start_simulation()
        self.lineEdit.clear()

        QMessageBox.information(self, "Reset Simulation", "Simulação recarregada com sucesso!")

    def reset_graphical_path(self):
        if self.simulation is None:
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        self.simulation.reset_graphical_path()

    def on_simulation_running_changed(self, running):
        self.set_simulation_buttons(loaded=True, running=running)

    def on_simulation_finished(self):
        self.statusbar.showMessage("End of traffic_router.txt reached", 5000)

    def on_unknown_service(self, packet):
        if self.mpconfig.router_addressing == MPSoCConfig.MPSoCConfig.XY:
            router = self.mpconfig.ham_address_to_xy_label(packet.router_address)
        else:
            router = str(packet.router_address)

        QMessageBox.critical(self, "Error",
                             f"ERROR: Service <{packet.service}> packet unidentified.\n"
                             f"Router: {router} Input port: {packet.get_input_port_string()}")

    def build_speed_control(self):
        """
        Reorganiza a caixa "Speed Control" igual ao debugger original:
        velocidade no canto superior direito, slider no meio e, embaixo,
        o tempo de simulação em ms (esquerda) e em ticks (direita).
        """
        for widget in (self.horizontalSlider, self.label_2, self.label):
            self.horizontalLayout_4.removeWidget(widget)

        # O antigo rótulo fixo "Ticks" passa a mostrar os ticks da simulação
        self.simulation_ticks_label = self.label
        self.simulation_time_label = QLabel(self.groupBox_2)

        speed_row = QHBoxLayout()
        speed_row.addStretch()
        speed_row.addWidget(self.label_2)

        time_row = QHBoxLayout()
        time_row.addWidget(self.simulation_time_label)
        time_row.addStretch()
        time_row.addWidget(self.simulation_ticks_label)

        speed_layout = QVBoxLayout()
        speed_layout.setSpacing(0)
        speed_layout.addLayout(speed_row)
        speed_layout.addWidget(self.horizontalSlider)
        speed_layout.addLayout(time_row)
        self.horizontalLayout_4.addLayout(speed_layout)

    def update_simulation_time(self, ticks):
        self.simulation_ticks = ticks
        clock_period = self.mpconfig.clock_period_in_ns if self.mpconfig else 0
        self.simulation_time_label.setText(f"{ticks_to_ms(ticks, clock_period):.5f} ms")
        self.simulation_ticks_label.setText(f"{ticks} ticks")

    def update_current_packet_table(self, packet):
        if self.mpconfig.router_addressing == MPSoCConfig.MPSoCConfig.HAMILTONIAN:
            source = str(packet.router_address)
            target = str(packet.target_router)
        else:
            source = self.mpconfig.ham_address_to_xy_label(packet.router_address)
            target = self.mpconfig.ham_address_to_xy_label(packet.target_router)

        values = (source, target,
                  self.mpconfig.get_string_service_name(packet.service),
                  f"{packet.size} | {packet.bandwidth_cycles}")
        for column, value in enumerate(values):
            self.tableWidget.setItem(0, column, QTableWidgetItem(value))

    def reset_current_packet_table(self):
        for column in range(self.tableWidget.columnCount()):
            self.tableWidget.setItem(0, column, QTableWidgetItem("-"))

    def taskList(self):
        task_hash = self.mpconfig.get_task_name_hash()
        rows = [(task_hash[key], str(key)) for key in sorted(task_hash.keys())]
        self.task_list_frame = self.create_table_window("Current Task List", ["Task Name", "ID"], rows)

    def servicesList(self):
        services_hash = self.mpconfig.get_services_hash()
        rows = [(services_hash[key], str(key)) for key in sorted(services_hash.keys())]
        self.services_list_frame = self.create_table_window("Services List", ["Service Name", "ID"], rows)

    def create_table_window(self, title, headers, rows):
        """Cria e exibe uma janela com uma tabela de duas colunas (nome e ID)."""
        table_frame = QWidget()
        table_frame.setWindowTitle(title)

        table_frame.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        table_frame.setGeometry(100, 100, 500, 500)

        table_widget = QTableWidget()
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        table_widget.setRowCount(len(rows))

        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                table_widget.setItem(row, column, QTableWidgetItem(value))

        layout = QVBoxLayout()
        layout.addWidget(table_widget)
        table_frame.setLayout(layout)

        table_frame.show()
        return table_frame


if __name__ == "__main__":
    app = QApplication(sys.argv)

    janela = MinhaJanela()
    janela.show()

    sys.exit(app.exec())