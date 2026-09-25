"""
Temas claro/escuro da aplicação.

Concentra as paletas do Qt e as cores da grade de roteadores, para que a
janela principal, as janelas secundárias e a matriz mudem juntas. A escolha
do usuário fica salva com QSettings e é restaurada na próxima execução.
"""

from dataclasses import dataclass

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette, Qt
from PySide6.QtWidgets import QApplication

_SETTINGS_ORG = "GAPH"
_SETTINGS_APP = "MemphisGraphicalDebugger"
_SETTINGS_KEY = "theme/dark_mode"


@dataclass(frozen=True)
class MatrixColors:
    """Cores da área onde a grade de roteadores é desenhada."""

    canvas: str         # fundo atrás dos roteadores
    text: str           # textos fora do corpo do roteador (ex.: % da porta local)
    cluster_border: str  # borda entre clusters
    arrow: str           # enlace sem pacote passando
    arrow_active: str    # enlace por onde o pacote atual passou
    peripheral_fill: str
    peripheral_text: str  # também usado na borda da caixa do periférico


LIGHT_MATRIX = MatrixColors(canvas="#ffffff", text="#000000", cluster_border="#808080",
                            arrow="#8c8c8c", arrow_active="#e00000",
                            peripheral_fill="#fff1e0", peripheral_text="#b34700")
DARK_MATRIX = MatrixColors(canvas="#262626", text="#e6e6e6", cluster_border="#6e6e6e",
                           arrow="#7a7a7a", arrow_active="#ff4040",
                           peripheral_fill="#3d2a1a", peripheral_text="#ffb070")


def matrix_colors(dark):
    return DARK_MATRIX if dark else LIGHT_MATRIX


def _build_palette(dark):
    palette = QPalette()

    if dark:
        window, base, alternate = QColor(53, 53, 53), QColor(35, 35, 35), QColor(45, 45, 45)
        text, disabled_text = QColor(Qt.GlobalColor.white), QColor(127, 127, 127)
        tooltip_base, highlighted_text = QColor(25, 25, 25), QColor(Qt.GlobalColor.black)
        button, placeholder = QColor(53, 53, 53), QColor(150, 150, 150)
    else:
        window, base, alternate = QColor(240, 240, 240), QColor(Qt.GlobalColor.white), QColor(225, 225, 225)
        text, disabled_text = QColor(Qt.GlobalColor.black), QColor(160, 160, 160)
        tooltip_base, highlighted_text = QColor(Qt.GlobalColor.white), QColor(Qt.GlobalColor.white)
        button, placeholder = QColor(240, 240, 240), QColor(120, 120, 120)

    role = QPalette.ColorRole
    palette.setColor(role.Window, window)
    palette.setColor(role.WindowText, text)
    palette.setColor(role.Base, base)
    palette.setColor(role.AlternateBase, alternate)
    palette.setColor(role.ToolTipBase, tooltip_base)
    palette.setColor(role.ToolTipText, text)
    palette.setColor(role.Text, text)
    palette.setColor(role.PlaceholderText, placeholder)
    palette.setColor(role.Button, button)
    palette.setColor(role.ButtonText, text)
    palette.setColor(role.BrightText, QColor(Qt.GlobalColor.red))
    palette.setColor(role.Link, QColor(42, 130, 218))
    palette.setColor(role.Highlight, QColor(42, 130, 218))
    palette.setColor(role.HighlightedText, highlighted_text)

    # Sem isso, botões e campos desabilitados ficam com o texto quase
    # invisível no modo escuro (o Fusion usa a cor ativa escurecida)
    disabled = QPalette.ColorGroup.Disabled
    for disabled_role in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(disabled, disabled_role, disabled_text)
    palette.setColor(disabled, role.Base, window)
    palette.setColor(disabled, role.Button, window)

    return palette


def apply_theme(dark, app=None):
    """Aplica a paleta clara ou escura na aplicação inteira."""
    app = app or QApplication.instance()
    app.setStyle("Fusion")
    app.setPalette(_build_palette(dark))


def load_dark_mode():
    """Retorna o último tema escolhido (claro por padrão)."""
    return QSettings(_SETTINGS_ORG, _SETTINGS_APP).value(_SETTINGS_KEY, False, type=bool)


def save_dark_mode(dark):
    QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(_SETTINGS_KEY, dark)
