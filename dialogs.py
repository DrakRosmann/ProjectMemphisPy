"""
Diálogos dos menus Edit e Help.

- PlatformSetupDialog (Edit -> Platform Setup): refatoração de
  PlatformSetupFrame.java do GraphicalDebugger original; permite trocar o
  tamanho do flit, o período de clock e a largura da janela de checkpoint
  (intervalo em que a % de uso dos enlaces é recalculada) sem editar o
  platform.cfg. As mudanças valem até o próximo "Reset Simulation" ou
  "New Debugging", que releem os arquivos.
- AboutDialog (util/AboutFrame.java) e show_packet_format
  (MainFrame.packetFormatMenuItemActionPerformed), do menu Help.
"""

import os

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QDoubleValidator, QFont, QIntValidator, QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout, QLabel, QLineEdit, QMessageBox,
                               QVBoxLayout)

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon")

# Formato de cada linha do traffic_router.txt, como lido em information.py (ReadTrafficData)
PACKET_FORMAT = """\
<p>Each line of <b>traffic_router.txt</b> is a packet header captured by a router, with tab-separated fields:</p>
<p><code>Time | Current Router Address | Service | Payload size | Packet bandwidth | Input port |
Target Router | Source task &lt;optional&gt; | Target task &lt;optional&gt;</code></p>
<p><b>Field description:</b></p>
<ul>
<li><b>Time</b>: integer decimal value, the tick counter when the header entered the router by the input port.</li>
<li><b>Current Router Address</b>: integer decimal value. With XY addressing, bits 0-7 (0xFF) are the
Y address and bits 8-15 (0xFF00) the X address; with Hamiltonian addressing, it is the router number.</li>
<li><b>Service</b>: integer decimal value with the packet service (see <i>services.cfg</i>).</li>
<li><b>Payload size</b>: integer decimal value, number of payload flits (the header adds 1 flit).</li>
<li><b>Packet bandwidth</b>: integer decimal value, clock cycles from the moment the header enters the
router until the last flit of the packet leaves it.</li>
<li><b>Input port</b>: integer decimal value, the port where the packet entered the router:
0-EAST 0, 1-EAST 1, 2-WEST 0, 3-WEST 1, 4-NORTH 0, 5-NORTH 1, 6-SOUTH 0, 7-SOUTH 1, 8-LOCAL 0, 9-LOCAL 1.
With <i>channel_number 1</i> the port is 0-EAST, 1-WEST, 2-NORTH, 3-SOUTH, 4-LOCAL.</li>
<li><b>Target Router</b>: same format as Current Router Address; the address in the header, i.e. the
router the packet is going to.</li>
<li><b>Source task</b>: OPTIONAL, integer decimal ID of the producer task of TASK_ALLOCATION,
TASK_TERMINATED, MESSAGE_REQUEST and MESSAGE_DELIVERY packets.</li>
<li><b>Target task</b>: OPTIONAL, same format as Source task, with the consumer task of those packets.</li>
</ul>
<p>Original author: Marcelo Ruaro (mceloruaro@gmail.com)</p>
"""


def show_packet_format(parent):
    box = QMessageBox(parent)
    box.setWindowTitle("Packet Format")
    box.setIcon(QMessageBox.Icon.Information)
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(PACKET_FORMAT)
    box.exec()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")

        logo = QLabel()
        pixmap = QPixmap(os.path.join(ICON_DIR, "gaph_logo.png"))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToWidth(min(pixmap.width(), 260),
                                                Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("GAPH")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)

        lines = [title,
                 QLabel("Grupo de Apoio de Pesquisa ao Hardware"),
                 QLabel("Pontifical Catholic University of Rio Grande do Sul (PUCRS)"),
                 QLabel("Support contact: fernando.moraes@pucrs.br"),
                 QLabel("Porto Alegre - Brasil"),
                 QLabel("Memphis-V Graphical Debugger — Python/PySide6 port")]

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(logo)
        for label in lines:
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        layout.addWidget(buttons)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)


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
