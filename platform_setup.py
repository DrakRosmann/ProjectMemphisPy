"""
Janela "Platform Setup" (menu Edit).

Refatoração de PlatformSetupFrame.java do GraphicalDebugger original: permite
trocar o tamanho do flit, o período de clock e a largura da janela de
checkpoint (intervalo em que a % de uso dos enlaces é recalculada) sem
editar o platform.cfg. As mudanças valem até o próximo "Reset Simulation"
ou "New Debugging", que releem os arquivos.
"""

from PySide6.QtCore import QLocale
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QLabel, QLineEdit, QMessageBox, QVBoxLayout


class PlatformSetupDialog(QDialog):
    def __init__(self, mpsoc_config, checkpoint, parent=None):
        super().__init__(parent)
        self.mpsoc_config = mpsoc_config
        self.checkpoint = checkpoint
        self.setWindowTitle("Platform Setup")

        self.flit_size_edit = QLineEdit(str(mpsoc_config.flit_size))
        self.flit_size_edit.setValidator(QIntValidator(1, 1024, self))

        self.clock_edit = QLineEdit(str(mpsoc_config.clock_period_in_ns))
        self.clock_edit.setValidator(QIntValidator(1, 1_000_000, self))

        # Largura da janela em us, como no Java (guardada em ms no controlador)
        self.window_width_edit = QLineEdit(f"{checkpoint.window_size_ms * 1000:g}")
        window_validator = QDoubleValidator(0.001, 1e9, 3, self)
        window_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        window_validator.setLocale(QLocale.c())  # aceita ponto decimal em qualquer idioma
        self.window_width_edit.setValidator(window_validator)

        form = QGridLayout()
        rows = (("Flit Size", self.flit_size_edit, "bits"),
                ("Clock Period", self.clock_edit, "ns"),
                ("Window Width", self.window_width_edit, "us"))
        for row, (caption, edit, unit) in enumerate(rows):
            form.addWidget(QLabel(caption), row, 0)
            form.addWidget(edit, row, 1)
            form.addWidget(QLabel(unit), row, 2)

        buttons = QDialogButtonBox()
        buttons.addButton("Confirm", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)  # não redimensionável, como no Java

    def accept(self):
        edits = (self.flit_size_edit, self.clock_edit, self.window_width_edit)
        invalid = next((edit for edit in edits if not edit.hasAcceptableInput()), None)
        if invalid is not None:
            QMessageBox.warning(self, "Platform Setup", "Enter only valid positive numbers.")
            invalid.setFocus()
            invalid.selectAll()
            return

        clock_period = int(self.clock_edit.text())
        self.mpsoc_config.flit_size = int(self.flit_size_edit.text())
        self.mpsoc_config.clock_period_in_ns = clock_period
        # O Java esquecia de repassar o clock ao CheckpointController
        self.checkpoint.clock_period_ns = clock_period
        self.checkpoint.window_size_ms = float(self.window_width_edit.text()) / 1000.0

        QMessageBox.information(self, "Platform Setup", "Settings applied")
        super().accept()
