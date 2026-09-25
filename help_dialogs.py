"""
Janelas do menu Help: "About" (util/AboutFrame.java) e "Packet Format"
(MainFrame.packetFormatMenuItemActionPerformed).
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QVBoxLayout

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon")

# Formato de cada linha do traffic_router.txt, como lido em information/read_traffic_data.py
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
