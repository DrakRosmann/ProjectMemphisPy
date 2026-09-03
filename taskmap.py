# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'taskmaptUrHBC.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QPushButton,
    QRadioButton, QScrollArea, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_TaskMap(object):
    def setupUi(self, TaskMap):
        if not TaskMap.objectName():
            TaskMap.setObjectName(u"TaskMap")
        TaskMap.resize(665, 377)
        self.verticalLayout = QVBoxLayout(TaskMap)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 3, 0, 0)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.radioButton = QRadioButton(TaskMap)
        self.radioButton.setObjectName(u"radioButton")

        self.horizontalLayout.addWidget(self.radioButton)

        self.radioButton_2 = QRadioButton(TaskMap)
        self.radioButton_2.setObjectName(u"radioButton_2")

        self.horizontalLayout.addWidget(self.radioButton_2)

        self.radioButton_3 = QRadioButton(TaskMap)
        self.radioButton_3.setObjectName(u"radioButton_3")

        self.horizontalLayout.addWidget(self.radioButton_3)

        self.pushButton = QPushButton(TaskMap)
        self.pushButton.setObjectName(u"pushButton")

        self.horizontalLayout.addWidget(self.pushButton)

        self.checkBox = QCheckBox(TaskMap)
        self.checkBox.setObjectName(u"checkBox")

        self.horizontalLayout.addWidget(self.checkBox)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.scrollArea = QScrollArea(TaskMap)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setMinimumSize(QSize(28, 28))
        self.scrollArea.setMaximumSize(QSize(32767, 32767))
        self.scrollArea.setBaseSize(QSize(200, 200))
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 663, 337))
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.verticalLayout.addWidget(self.scrollArea)


        self.retranslateUi(TaskMap)

        QMetaObject.connectSlotsByName(TaskMap)
    # setupUi

    def retranslateUi(self, TaskMap):
        TaskMap.setWindowTitle(QCoreApplication.translate("TaskMap", u"Task Mapping Overview", None))
        self.radioButton.setText(QCoreApplication.translate("TaskMap", u"All tasks status", None))
        self.radioButton_2.setText(QCoreApplication.translate("TaskMap", u"Only Running", None))
        self.radioButton_3.setText(QCoreApplication.translate("TaskMap", u"All tasks status", None))
        self.pushButton.setText(QCoreApplication.translate("TaskMap", u"Update", None))
        self.checkBox.setText(QCoreApplication.translate("TaskMap", u"Without Task ID", None))
    # retranslateUi

