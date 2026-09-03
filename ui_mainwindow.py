# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'MenphisuiDRDXSX.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMenu, QMenuBar, QPushButton, QSizePolicy,
    QSlider, QStatusBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

class MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(986, 696)
        palette = QPalette()
        brush = QBrush(QColor(246, 245, 244, 255))
        brush.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Window, brush)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Window, brush)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, brush)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, brush)
        MainWindow.setPalette(palette)
        MainWindow.setTabShape(QTabWidget.TabShape.Rounded)
        MainWindow.setDockNestingEnabled(False)
        self.actionNew_Debugging = QAction(MainWindow)
        self.actionNew_Debugging.setObjectName(u"actionNew_Debugging")
        self.actionSave_Project = QAction(MainWindow)
        self.actionSave_Project.setObjectName(u"actionSave_Project")
        self.actionSave_Project.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.actionOpen_Project = QAction(MainWindow)
        self.actionOpen_Project.setObjectName(u"actionOpen_Project")
        self.actionDelete_Project = QAction(MainWindow)
        self.actionDelete_Project.setObjectName(u"actionDelete_Project")
        self.actionReset_Simulation = QAction(MainWindow)
        self.actionReset_Simulation.setObjectName(u"actionReset_Simulation")
        self.actionRest_Graphical_Path = QAction(MainWindow)
        self.actionRest_Graphical_Path.setObjectName(u"actionRest_Graphical_Path")
        self.actionExit = QAction(MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionPlatform_Setup = QAction(MainWindow)
        self.actionPlatform_Setup.setObjectName(u"actionPlatform_Setup")
        self.actionCommunication_Overview = QAction(MainWindow)
        self.actionCommunication_Overview.setObjectName(u"actionCommunication_Overview")
        self.actionTask_Mapping_Overview = QAction(MainWindow)
        self.actionTask_Mapping_Overview.setObjectName(u"actionTask_Mapping_Overview")
        self.actionServices_List = QAction(MainWindow)
        self.actionServices_List.setObjectName(u"actionServices_List")
        self.actionTask_List = QAction(MainWindow)
        self.actionTask_List.setObjectName(u"actionTask_List")
        self.actionMessage_Log = QAction(MainWindow)
        self.actionMessage_Log.setObjectName(u"actionMessage_Log")
        self.actionDeloream = QAction(MainWindow)
        self.actionDeloream.setObjectName(u"actionDeloream")
        self.actionService_and_PE_Filter = QAction(MainWindow)
        self.actionService_and_PE_Filter.setObjectName(u"actionService_and_PE_Filter")
        self.actionAbout = QAction(MainWindow)
        self.actionAbout.setObjectName(u"actionAbout")
        self.actionPacket_Format = QAction(MainWindow)
        self.actionPacket_Format.setObjectName(u"actionPacket_Format")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setSpacing(9)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(1, 1, 1, 0)
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setMinimumSize(QSize(25, 25))
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)

        self.verticalLayout.addWidget(self.frame)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.groupBox = QGroupBox(self.centralwidget)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy1)
        self.groupBox.setMinimumSize(QSize(204, 20))
        self.horizontalLayout_3 = QHBoxLayout(self.groupBox)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.pushButton_2 = QPushButton(self.groupBox)
        self.pushButton_2.setObjectName(u"pushButton_2")

        self.horizontalLayout_3.addWidget(self.pushButton_2)

        self.pushButton = QPushButton(self.groupBox)
        self.pushButton.setObjectName(u"pushButton")

        self.horizontalLayout_3.addWidget(self.pushButton)

        self.pushButton_3 = QPushButton(self.groupBox)
        self.pushButton_3.setObjectName(u"pushButton_3")

        self.horizontalLayout_3.addWidget(self.pushButton_3)


        self.horizontalLayout_5.addWidget(self.groupBox)

        self.groupBox_2 = QGroupBox(self.centralwidget)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy1.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy1)
        self.horizontalLayout_4 = QHBoxLayout(self.groupBox_2)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalSlider = QSlider(self.groupBox_2)
        self.horizontalSlider.setObjectName(u"horizontalSlider")
        self.horizontalSlider.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.horizontalSlider.setOrientation(Qt.Orientation.Horizontal)
        self.horizontalSlider.setTickPosition(QSlider.TickPosition.NoTicks)

        self.horizontalLayout_4.addWidget(self.horizontalSlider)

        self.label_2 = QLabel(self.groupBox_2)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_4.addWidget(self.label_2)

        self.label = QLabel(self.groupBox_2)
        self.label.setObjectName(u"label")

        self.horizontalLayout_4.addWidget(self.label)


        self.horizontalLayout_5.addWidget(self.groupBox_2)

        self.groupBox_3 = QGroupBox(self.centralwidget)
        self.groupBox_3.setObjectName(u"groupBox_3")
        sizePolicy1.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy1)
        self.horizontalLayout = QHBoxLayout(self.groupBox_3)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.lineEdit = QLineEdit(self.groupBox_3)
        self.lineEdit.setObjectName(u"lineEdit")

        self.horizontalLayout.addWidget(self.lineEdit)

        self.toolButton = QToolButton(self.groupBox_3)
        self.toolButton.setObjectName(u"toolButton")

        self.horizontalLayout.addWidget(self.toolButton)


        self.horizontalLayout_5.addWidget(self.groupBox_3)

        self.groupBox_4 = QGroupBox(self.centralwidget)
        self.groupBox_4.setObjectName(u"groupBox_4")
        sizePolicy1.setHeightForWidth(self.groupBox_4.sizePolicy().hasHeightForWidth())
        self.groupBox_4.setSizePolicy(sizePolicy1)
        self.horizontalLayout_2 = QHBoxLayout(self.groupBox_4)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.tableWidget = QTableWidget(self.groupBox_4)
        if (self.tableWidget.columnCount() < 4):
            self.tableWidget.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.tableWidget.setObjectName(u"tableWidget")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.tableWidget.sizePolicy().hasHeightForWidth())
        self.tableWidget.setSizePolicy(sizePolicy2)

        self.horizontalLayout_2.addWidget(self.tableWidget)


        self.horizontalLayout_5.addWidget(self.groupBox_4)


        self.verticalLayout.addLayout(self.horizontalLayout_5)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 986, 24))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuEdit = QMenu(self.menubar)
        self.menuEdit.setObjectName(u"menuEdit")
        self.menuTools = QMenu(self.menubar)
        self.menuTools.setObjectName(u"menuTools")
        self.menuFilters = QMenu(self.menubar)
        self.menuFilters.setObjectName(u"menuFilters")
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName(u"menuHelp")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuTools.menuAction())
        self.menubar.addAction(self.menuFilters.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.addAction(self.actionNew_Debugging)
        self.menuFile.addAction(self.actionSave_Project)
        self.menuFile.addAction(self.actionOpen_Project)
        self.menuFile.addAction(self.actionDelete_Project)
        self.menuFile.addAction(self.actionReset_Simulation)
        self.menuFile.addAction(self.actionRest_Graphical_Path)
        self.menuFile.addAction(self.actionExit)
        self.menuEdit.addAction(self.actionPlatform_Setup)
        self.menuTools.addAction(self.actionCommunication_Overview)
        self.menuTools.addSeparator()
        self.menuTools.addAction(self.actionTask_Mapping_Overview)
        self.menuTools.addAction(self.actionServices_List)
        self.menuTools.addAction(self.actionTask_List)
        self.menuTools.addAction(self.actionMessage_Log)
        self.menuTools.addSeparator()
        self.menuTools.addAction(self.actionDeloream)
        self.menuFilters.addAction(self.actionService_and_PE_Filter)
        self.menuHelp.addAction(self.actionAbout)
        self.menuHelp.addAction(self.actionPacket_Format)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.actionNew_Debugging.setText(QCoreApplication.translate("MainWindow", u"New Debugging", None))
#if QT_CONFIG(shortcut)
        self.actionNew_Debugging.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+N", None))
#endif // QT_CONFIG(shortcut)
        self.actionSave_Project.setText(QCoreApplication.translate("MainWindow", u"Save Project", None))
#if QT_CONFIG(shortcut)
        self.actionSave_Project.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+S", None))
#endif // QT_CONFIG(shortcut)
        self.actionOpen_Project.setText(QCoreApplication.translate("MainWindow", u"Open Project", None))
        self.actionDelete_Project.setText(QCoreApplication.translate("MainWindow", u"Delete Project", None))
        self.actionReset_Simulation.setText(QCoreApplication.translate("MainWindow", u"Reset Simulation", None))
        self.actionRest_Graphical_Path.setText(QCoreApplication.translate("MainWindow", u"Rest Graphical Path", None))
        self.actionExit.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
        self.actionPlatform_Setup.setText(QCoreApplication.translate("MainWindow", u"Platform Setup", None))
        self.actionCommunication_Overview.setText(QCoreApplication.translate("MainWindow", u"Communication Overview", None))
        self.actionTask_Mapping_Overview.setText(QCoreApplication.translate("MainWindow", u"Task Mapping Overview", None))
        self.actionServices_List.setText(QCoreApplication.translate("MainWindow", u"Services List", None))
        self.actionTask_List.setText(QCoreApplication.translate("MainWindow", u"Task List", None))
        self.actionMessage_Log.setText(QCoreApplication.translate("MainWindow", u"Message Log", None))
        self.actionDeloream.setText(QCoreApplication.translate("MainWindow", u"Deloream", None))
        self.actionService_and_PE_Filter.setText(QCoreApplication.translate("MainWindow", u"Service and PE Filter", None))
        self.actionAbout.setText(QCoreApplication.translate("MainWindow", u"About", None))
        self.actionPacket_Format.setText(QCoreApplication.translate("MainWindow", u"Packet Format", None))
        self.groupBox.setTitle(QCoreApplication.translate("MainWindow", u"Simulation Control", None))
        self.pushButton_2.setText(QCoreApplication.translate("MainWindow", u">||", None))
        self.pushButton.setText(QCoreApplication.translate("MainWindow", u">", None))
        self.pushButton_3.setText(QCoreApplication.translate("MainWindow", u"STOP", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("MainWindow", u"Speed Control", None))
        self.label_2.setText("")
        self.label.setText(QCoreApplication.translate("MainWindow", u"Ticks", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("MainWindow", u"Back To", None))
        self.toolButton.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("MainWindow", u"Current Packet Information", None))
        ___qtablewidgetitem = self.tableWidget.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"Current", None))
        ___qtablewidgetitem1 = self.tableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"Target", None))
        ___qtablewidgetitem2 = self.tableWidget.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"Service", None))
        ___qtablewidgetitem3 = self.tableWidget.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"Size", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuEdit.setTitle(QCoreApplication.translate("MainWindow", u"Edit", None))
        self.menuTools.setTitle(QCoreApplication.translate("MainWindow", u"Tools", None))
        self.menuFilters.setTitle(QCoreApplication.translate("MainWindow", u"Filters", None))
        self.menuHelp.setTitle(QCoreApplication.translate("MainWindow", u"Help", None))
    # retranslateUi

