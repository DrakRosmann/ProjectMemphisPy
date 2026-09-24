import os
import sys

from PySide6.QtGui import Qt, QPalette, QColor, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, QWidget,
                               QVBoxLayout, QHBoxLayout, QScrollArea, QTableWidgetItem, QTableWidget, QLabel,
                               QHeaderView)

from ui_mainwindow import MainWindow
from commsUi import Ui_Form
from taskmap import Ui_TaskMap
from util import MPSoCConfig
from information import MPSoCInformation
from router_matrix import RouterMatrixWidget
from simulation import SimulationController, MAX_REPAINT_SPEED, ticks_to_ms
from slave_matrix import SlaveMatrixWidget
from pe_matrix import PEMatrixWidget


class MinhaJanela(QMainWindow, MainWindow):
    filePath = ""
    mpconfig = None
    mpsoc_information = None
    router_matrix_widget = None
    frame_scroll_area = None
    simulation = None

    # Arquivos obrigatórios em um diretório de debug
    REQUIRED_FILES = ("platform.cfg", "services.cfg", "traffic_router.txt")

    # Variável de controle do tema
    is_dark_mode = False

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # ---------------------------------------------------------
        # SISTEMA DE TEMA (DARK/LIGHT MODE)
        # ---------------------------------------------------------
        # Limpa a paleta fixa gerada pelo arquivo .ui para herdar a do App
        self.setPalette(QPalette())
        self.apply_light_theme(app)
        self.is_dark_mode = False
        # Cria uma ação para alternar o tema e adiciona no menu "Edit"
        self.actionToggle_Theme = QAction("Alternar Tema (Dark/Light)", self)
        self.actionToggle_Theme.setShortcut(QKeySequence("Ctrl+T"))
        self.menuEdit.addAction(self.actionToggle_Theme)
        self.actionToggle_Theme.triggered.connect(self.toggle_theme)

        # Garante que o aplicativo inicie no modo claro padrão do estilo Fusion
        self.apply_light_theme(QApplication.instance())
        # ---------------------------------------------------------

        self.actionCommunication_Overview.setEnabled(False)
        self.actionDeloream.setEnabled(False)
        self.actionTask_Mapping_Overview.setEnabled(False)
        self.actionServices_List.setEnabled(False)
        self.actionMessage_Log.setEnabled(False)
        self.actionTask_List.setEnabled(False)

        self.actionExit.triggered.connect(self.close)
        self.actionNew_Debugging.triggered.connect(self.open_file)
        self.horizontalSlider.valueChanged.connect(self.update_slide)
        self.label_2.setText(f"{self.horizontalSlider.value()}")
        self.actionCommunication_Overview.triggered.connect(self.open_communication)
        self.actionTask_Mapping_Overview.triggered.connect(self.open_taskmap)
        self.actionTask_List.triggered.connect(self.taskList)
        self.actionServices_List.triggered.connect(self.servicesList)

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
        app = QApplication.instance()
        if not self.is_dark_mode:
            self.apply_dark_theme(app)
            self.is_dark_mode = True
        else:
            self.apply_light_theme(app)
            self.is_dark_mode = False

    def apply_dark_theme(self, app):
        app.setStyle("Fusion")
        dark_palette = QPalette()

        # Configurando as cores do modo escuro
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

        # Aplica na aplicação inteira (afeta abas secundárias também)
        app.setPalette(dark_palette)

    def apply_light_theme(self, app):
        app.setStyle("Fusion")
        light_palette = QPalette()

        # Força as cores do modo claro para sobrescrever o tema do Sistema Operacional
        light_palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(225, 225, 225))
        light_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        light_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        light_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        light_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        light_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        light_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

        app.setPalette(light_palette)

    # ==========================================

    def open_communication(self):
        if self.filePath == "":
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        self.janela_secundaria = NovaJanela(self.mpconfig)
        self.janela_secundaria.show()

    def open_taskmap(self):
        if self.filePath == "":
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        self.janela_taskmap = TaskMapWindow(self.mpconfig)
        self.janela_taskmap.show()

    def update_slide(self, valor):
        self.label_2.setText(str(valor))
        if self.simulation is not None:
            self.simulation.set_speed(valor)

    def open_file(self):
        caminho = QFileDialog.getExistingDirectory(self, "Open Debug Directory", "./")
        if caminho == "":
            return

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
            return

        self.filePath = caminho
        if self.filePath != "":
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

    def build_router_matrix(self):
        """
        Monta a matriz de roteadores dentro do self.frame do MainWindow,
        usando mpsoc_x/mpsoc_y (nº de clusters) e cluster_x/cluster_y
        (roteadores por cluster) lidos do arquivo de configuração atual.
        """
        if self.mpconfig is None:
            return

        # Cria a matriz de roteadores com base na configuração carregada
        self.router_matrix_widget = RouterMatrixWidget(
            self.mpconfig.mpsoc_x,
            self.mpconfig.mpsoc_y,
            self.mpconfig.cluster_x,
            self.mpconfig.cluster_y,
            mpsoc_config=self.mpconfig,
        )

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


class NovaJanela(QWidget, Ui_Form):
    def __init__(self, mpconfig=None):
        super().__init__()
        self.setupUi(self)
        self.mpconfig = mpconfig
        self.checkBox.checkStateChanged.connect(self.on_checkbox_changed)

        self.build_slave_matrix()

    def build_slave_matrix(self):
        """
        Monta a matriz de slaves dentro do scrollArea gerado por commsUi.py
        (self.scrollAreaWidgetContents), usando mpsoc_x/mpsoc_y do arquivo
        de configuração atual — igual ao print do Communication Overview.
        """
        if self.mpconfig is None:
            return

        matrix = SlaveMatrixWidget(self.mpconfig.mpsoc_x, self.mpconfig.mpsoc_y)

        layout = QVBoxLayout(self.scrollAreaWidgetContents)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(matrix)
        self.scrollAreaWidgetContents.setLayout(layout)

    def on_checkbox_changed(self):
        if (self.checkBox.isChecked()):
            self.radioButton.setEnabled(False)
            self.radioButton_2.setEnabled(False)
            self.radioButton_3.setEnabled(False)
            self.comboBox.setEnabled(False)
        else:
            self.radioButton.setEnabled(True)
            self.radioButton_2.setEnabled(True)
            self.radioButton_3.setEnabled(True)
            self.comboBox.setEnabled(True)


class TaskMapWindow(QWidget, Ui_TaskMap):
    def __init__(self, mpconfig=None):
        super().__init__()
        self.setupUi(self)
        self.mpconfig = mpconfig

        self.build_pe_matrix()

    def build_pe_matrix(self):
        """
        Monta a matriz de PEs dentro do scrollArea gerado por taskmap.py
        (self.scrollAreaWidgetContents), usando mpsoc_x/mpsoc_y do arquivo
        de configuração atual — igual ao print do Task Mapping Overview.
        """
        if self.mpconfig is None:
            return

        matrix = PEMatrixWidget(self.mpconfig.mpsoc_x, self.mpconfig.mpsoc_y)

        layout = QVBoxLayout(self.scrollAreaWidgetContents)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(matrix)
        self.scrollAreaWidgetContents.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    janela = MinhaJanela()
    janela.show()

    sys.exit(app.exec())