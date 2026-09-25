"""
Janela "Service and PE Filter" (menu Filters, Ctrl+F).

Refatoração de FilterForm.java do GraphicalDebugger original. Escolhe quais
pacotes do traffic_router.txt a simulação processa:

  - aba Services: só os serviços da lista ("Only") ou todos menos eles ("Except")
  - aba PE:       só os pacotes capturados nos roteadores da lista
  - aba Application: só os pacotes de/para tarefas das aplicações da lista
    (não existe no Java; o artigo do Memphis cita o filtro por aplicação)

A lista montada numa aba só passa a valer ao clicar em "Apply" (lista vazia
desliga o filtro daquela aba). Pacotes rejeitados não atualizam os roteadores
nem são desenhados; ver MPSoCInformation.get_next_packet.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QRadioButton, QTabWidget, QVBoxLayout, QWidget)

import analysis
from util.MPSoCConfig import MPSoCConfig

# Serviço sempre descartado pelo filtro do Java
IGNORED_SERVICE = "SLACK_TIME_REPORT"


class _FilterTab(QWidget):
    """Combo de itens + lista dos adicionados, com Add / Remove / Remove All / Apply / Close."""

    def __init__(self, caption, added_caption, items, on_apply, on_close, extra_widget=None):
        super().__init__()
        self.on_apply = on_apply

        self.combo = QComboBox()
        for label, value in items:
            self.combo.addItem(label, value)

        self.added_list = QListWidget()

        add_button = QPushButton("Add")
        remove_button = QPushButton("Remove")
        remove_all_button = QPushButton("Remove All")
        apply_button = QPushButton("Apply")
        close_button = QPushButton("Close")
        add_button.clicked.connect(self.add_selected)
        remove_button.clicked.connect(self.remove_selected)
        remove_all_button.clicked.connect(self.added_list.clear)
        apply_button.clicked.connect(self._apply)
        close_button.clicked.connect(on_close)

        left = QVBoxLayout()
        left.addWidget(QLabel(caption))
        left.addWidget(self.combo)
        left.addWidget(add_button)
        left.addWidget(remove_button)
        left.addWidget(remove_all_button)
        if extra_widget is not None:
            left.addWidget(extra_widget)
        left.addStretch()

        right = QVBoxLayout()
        right.addWidget(QLabel(added_caption))
        right.addWidget(self.added_list)

        lists = QHBoxLayout()
        lists.addLayout(left)
        lists.addLayout(right, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(apply_button)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(lists)
        layout.addLayout(buttons)

    def added_values(self):
        return [self.added_list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.added_list.count())]

    def add_selected(self):
        value = self.combo.currentData()
        if value is None or value in self.added_values():
            return
        item = QListWidgetItem(self.combo.currentText())
        item.setData(Qt.ItemDataRole.UserRole, value)
        self.added_list.addItem(item)

    def remove_selected(self):
        for item in self.added_list.selectedItems():
            self.added_list.takeItem(self.added_list.row(item))

    def _apply(self):
        answer = QMessageBox.question(self, "Attention", "You are sure?")
        if answer == QMessageBox.StandardButton.Yes:
            self.on_apply(self.added_values())


class FilterWindow(QWidget):
    """
    Guarda o filtro aplicado e o expõe em filter(packet), usado como
    SimulationController.packet_filter. A janela é criada uma vez por debug
    carregado e apenas escondida ao fechar, mantendo as listas montadas.
    """

    def __init__(self, mpsoc_config, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.mpsoc_config = mpsoc_config
        self.setWindowTitle("Service and PE Filter")
        self.resize(480, 340)

        self.filtered_services = set()
        self.filtered_pes = set()
        self.filtered_apps = set()
        self.except_services = False
        self.known_apps = analysis.known_app_ids(mpsoc_config)
        self.ignored_service = mpsoc_config.get_service_value(IGNORED_SERVICE)

        services = [(mpsoc_config.get_string_service_name(service), service)
                    for service in mpsoc_config.service_reference]
        pes = [(self._pe_label(address), address) for address in range(mpsoc_config.get_pe_number())]

        self.only_radio = QRadioButton("Only")
        self.except_radio = QRadioButton("Except")
        self.only_radio.setChecked(True)
        mode = QWidget()
        mode_layout = QHBoxLayout(mode)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(self.only_radio)
        mode_layout.addWidget(self.except_radio)
        mode_layout.addStretch()

        self.services_tab = _FilterTab("Services", "Added Services", services,
                                       self._apply_services, self.close, mode)
        self.pe_tab = _FilterTab("PEs", "Added PEs", pes, self._apply_pes, self.close)
        apps = [(analysis.app_label(mpsoc_config, app), app) for app in sorted(self.known_apps)]
        self.app_tab = _FilterTab("Applications", "Added Applications", apps, self._apply_apps, self.close)
        self.app_tab.setToolTip("Keeps only packets whose source or target task belongs to the selected "
                                "applications.\nKernel packets without task IDs are hidden.")

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)

        tabs = QTabWidget()
        tabs.addTab(self.services_tab, "Services")
        tabs.addTab(self.pe_tab, "PE")
        tabs.addTab(self.app_tab, "Application")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(self.status_label)
        self._update_status()

    def _pe_label(self, address):
        if self.mpsoc_config.router_addressing == MPSoCConfig.XY:
            return self.mpsoc_config.ham_address_to_xy_label(address)
        return str(address)

    # ------------------------------------------
    # Apply
    # ------------------------------------------
    def _apply_services(self, services):
        self.filtered_services = set(services)
        self.except_services = self.except_radio.isChecked()
        self._update_status()

    def _apply_pes(self, pes):
        self.filtered_pes = set(pes)
        self._update_status()

    def _apply_apps(self, apps):
        self.filtered_apps = set(apps)
        self._update_status()

    def _update_status(self):
        config = self.mpsoc_config
        parts = []
        if self.filtered_services:
            names = ", ".join(sorted(config.get_string_service_name(service) for service in self.filtered_services))
            parts.append(f"{'Except' if self.except_services else 'Only'} services: {names}")
        if self.filtered_pes:
            names = ", ".join(self._pe_label(address) for address in sorted(self.filtered_pes))
            parts.append(f"Only PEs: {names}")
        if self.filtered_apps:
            names = ", ".join(analysis.app_label(config, app) for app in sorted(self.filtered_apps))
            parts.append(f"Only applications: {names}")
        self.status_label.setText("Active filter — " + "; ".join(parts) if parts else "No filter applied")

    # ------------------------------------------
    # Filtro
    # ------------------------------------------
    def filter(self, packet):
        """True se o pacote deve ser processado pela simulação."""
        if packet.service == self.ignored_service:
            return False

        if self.filtered_services:
            if (packet.service in self.filtered_services) == self.except_services:
                return False

        # No Java o filtro de PE era ignorado quando havia filtro de serviço;
        # aqui os dois valem juntos
        if self.filtered_pes and packet.router_address not in self.filtered_pes:
            return False

        if self.filtered_apps and not analysis.packet_apps(packet, self.known_apps) & self.filtered_apps:
            return False

        return True
