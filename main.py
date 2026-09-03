import sys

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QWidget, QVBoxLayout

import commsUi
# Importa a classe 'MainWindow' do arquivo que você gerou
# (Substitua 'ui_mainwindow' pelo nome correto do seu arquivo sem a extensão .py)
from ui_mainwindow import MainWindow
from commsUi import Ui_Form
from taskmap import Ui_TaskMap

class MinhaJanela(QMainWindow, MainWindow):
    filePath = ""
    def __init__(self):
        super().__init__()
        # Configura a interface criada no Qt Designer
        self.setupUi(self)

        #:
        self.actionCommunication_Overview.setEnabled(False)
        self.actionDeloream.setEnabled(False)
        self.actionTask_Mapping_Overview.setEnabled(False)
        self.actionServices_List.setEnabled(False)
        self.actionMessage_Log.setEnabled(False)
        self.actionTask_List.setEnabled(False)

        # --- AQUI VOCÊ ADICIONA A LÓGICA DO SEU PROGRAMA ---
        # Exemplo: Conectando o botão de "STOP" (pushButton_3) a uma função
        self.pushButton_3.clicked.connect(self.parar_simulacao)
        self.actionExit.triggered.connect(self.close)  # Fecha o programa
        self.actionNew_Debugging.triggered.connect(self.open_file)
        self.horizontalSlider.valueChanged.connect(self.updadeSlide)
        self.label_2.setText(f"{self.horizontalSlider.value()}")
        self.actionCommunication_Overview.triggered.connect(self.open_communication)
        self.actionTask_Mapping_Overview.triggered.connect(self.open_taskmap)

    def open_communication(self):
        if self.filePath == "":
            QMessageBox.warning(self, "Attention", "Please, load a debugging before")
            return
        self.janela_secundaria = NovaJanela()
        self.janela_secundaria.show()

    def open_taskmap(self):
        self.janela_taskmap = taskMap()
        self.janela_taskmap.show()

    def updadeSlide(self, valor):
        self.label_2.setText(str(valor))

    def open_file(self):
        self.filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "./",
            "Config Files (*.cfg);;All Files (*)"
        )
        if self.filePath != "":
            self.actionCommunication_Overview.setEnabled(True)
            self.actionDeloream.setEnabled(True)
            self.actionTask_Mapping_Overview.setEnabled(True)
            self.actionServices_List.setEnabled(True)
            self.actionMessage_Log.setEnabled(True)
            self.actionTask_List.setEnabled(True)

        #TESTE:
        #with open(self.filePath[0], "r") as file:
               # content = file.read()
               # print(content)
        print(self.filePath)



    def parar_simulacao(self):
        print("Botão STOP clicado!")

class NovaJanela(QWidget, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.checkBox.checkStateChanged.connect(self.CheckB)



    def CheckB(self):
        if(self.checkBox.isChecked()):
            self.radioButton.setEnabled(False)
            self.radioButton_2.setEnabled(False)
            self.radioButton_3.setEnabled(False)
            self.comboBox.setEnabled(False)
        else:
            self.radioButton.setEnabled(True)
            self.radioButton_2.setEnabled(True)
            self.radioButton_3.setEnabled(True)
            self.comboBox.setEnabled(True)

class taskMap(QWidget, Ui_TaskMap):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

if __name__ == "__main__":
    # Inicializa o aplicativo
    app = QApplication(sys.argv)

    # Cria a janela principal
    janela = MinhaJanela()
    janela.show()

    # Mantém o aplicativo rodando
    sys.exit(app.exec())