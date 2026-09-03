# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'CommmLyrIx.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGroupBox,
    QHeaderView, QLabel, QRadioButton, QScrollArea,
    QSizePolicy, QTableWidget, QTableWidgetItem, QWidget)

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(851, 344)
        self.groupBox = QGroupBox(Form)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setGeometry(QRect(0, 0, 291, 101))
        self.comboBox = QComboBox(self.groupBox)
        self.comboBox.setObjectName(u"comboBox")
        self.comboBox.setGeometry(QRect(10, 60, 86, 27))
        self.radioButton = QRadioButton(self.groupBox)
        self.radioButton.setObjectName(u"radioButton")
        self.radioButton.setGeometry(QRect(160, 20, 110, 24))
        self.radioButton_2 = QRadioButton(self.groupBox)
        self.radioButton_2.setObjectName(u"radioButton_2")
        self.radioButton_2.setGeometry(QRect(160, 40, 110, 24))
        self.radioButton_3 = QRadioButton(self.groupBox)
        self.radioButton_3.setObjectName(u"radioButton_3")
        self.radioButton_3.setGeometry(QRect(160, 60, 110, 24))
        self.checkBox = QCheckBox(self.groupBox)
        self.checkBox.setObjectName(u"checkBox")
        self.checkBox.setGeometry(QRect(10, 30, 96, 24))
        self.groupBox_2 = QGroupBox(Form)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setGeometry(QRect(300, 0, 120, 101))
        self.radioButton_4 = QRadioButton(self.groupBox_2)
        self.radioButton_4.setObjectName(u"radioButton_4")
        self.radioButton_4.setGeometry(QRect(10, 30, 110, 24))
        self.radioButton_5 = QRadioButton(self.groupBox_2)
        self.radioButton_5.setObjectName(u"radioButton_5")
        self.radioButton_5.setGeometry(QRect(10, 70, 110, 24))
        self.groupBox_3 = QGroupBox(Form)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.groupBox_3.setGeometry(QRect(430, 0, 291, 101))
        self.tableWidget = QTableWidget(self.groupBox_3)
        if (self.tableWidget.columnCount() < 3):
            self.tableWidget.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        self.tableWidget.setObjectName(u"tableWidget")
        self.tableWidget.setGeometry(QRect(0, 20, 291, 81))
        self.groupBox_4 = QGroupBox(Form)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.groupBox_4.setGeometry(QRect(730, 0, 120, 101))
        self.label = QLabel(self.groupBox_4)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(20, 40, 81, 16))
        self.label.setPixmap(QPixmap(u"color_spectrum.png"))
        self.label.setScaledContents(True)
        self.label_2 = QLabel(self.groupBox_4)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(20, 60, 21, 19))
        self.label_3 = QLabel(self.groupBox_4)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setGeometry(QRect(70, 60, 31, 20))
        self.scrollArea = QScrollArea(Form)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setGeometry(QRect(0, 110, 851, 241))
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 849, 239))
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.groupBox.setTitle(QCoreApplication.translate("Form", u"Service Filter", None))
        self.radioButton.setText(QCoreApplication.translate("Form", u"All traffic", None))
        self.radioButton_2.setText(QCoreApplication.translate("Form", u"Global", None))
        self.radioButton_3.setText(QCoreApplication.translate("Form", u"Router", None))
        self.checkBox.setText(QCoreApplication.translate("Form", u"All Services", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("Form", u"Data Filter", None))
        self.radioButton_4.setText(QCoreApplication.translate("Form", u"Volume", None))
        self.radioButton_5.setText(QCoreApplication.translate("Form", u"Bandwidth", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("Form", u"Statistics", None))
        ___qtablewidgetitem = self.tableWidget.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("Form", u"Bigger", None))
        ___qtablewidgetitem1 = self.tableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("Form", u"Average", None))
        ___qtablewidgetitem2 = self.tableWidget.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("Form", u"Small", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("Form", u"Color Length", None))
        self.label.setText("")
        self.label_2.setText(QCoreApplication.translate("Form", u"low", None))
        self.label_3.setText(QCoreApplication.translate("Form", u"high", None))
    # retranslateUi

