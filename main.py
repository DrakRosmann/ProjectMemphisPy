import os
import sys

from PySide6.QtGui import Qt, QPalette, QColor, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, QWidget,
                               QVBoxLayout, QScrollArea, QTableWidgetItem, QTableWidget)

from ui_mainwindow import MainWindow
from commsUi import Ui_Form
from taskmap import Ui_TaskMap
from util import MPSoCConfig
from router_matrix import RouterMatrixWidget
from slave_matrix import SlaveMatrixWidget
from pe_matrix import PEMatrixWidget


class MinhaJanela(QMainWindow, MainWindow):
    filePath = ""
    mpconfig = None
    router_matrix_widget = None
    frame_scroll_area = None

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
                "Invalid Directory",
                "The selected directory is not a valid debug directory.\n\n"
                "Missing files:\n" + "\n".join(f"• {arquivo}" for arquivo in faltando)
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
            self.build_router_matrix()

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

    def taskList(self):
        services_hash = self.mpconfig.get_task_name_hash()

        self.task_list_frame = QWidget()
        self.task_list_frame.setWindowTitle("Current Task List")

        self.task_list_frame.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.task_list_frame.setGeometry(100, 100, 500, 500)

        table_widget = QTableWidget()
        table_widget.setColumnCount(2)
        table_widget.setHorizontalHeaderLabels(["Task Name", "ID"])
        table_widget.setRowCount(len(services_hash))

        for row, key in enumerate(sorted(services_hash.keys())):
            task_name = services_hash[key]

            name_item = QTableWidgetItem(task_name)
            id_item = QTableWidgetItem(str(key))

            table_widget.setItem(row, 0, name_item)
            table_widget.setItem(row, 1, id_item)

        layout = QVBoxLayout()
        layout.addWidget(table_widget)
        self.task_list_frame.setLayout(layout)

        self.task_list_frame.show()



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