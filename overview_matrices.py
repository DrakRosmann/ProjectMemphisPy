"""
Matrizes de células das janelas de visão geral (overview_windows.py).

- SlaveMatrixWidget: grade "Slave XxY" do Communication Overview (commsUi.py),
  com fundo de mapa de calor, percentual de tráfego e unidade ("flits").
- PEMatrixWidget: grade "PEXxY" do Task Mapping Overview (taskmap.py), com
  uma linha por tarefa na cor da aplicação.

Cada célula é um widget simples e expansível (cresce para ocupar toda a
largura/altura do scrollArea do formulário). Usam apenas mpsoc_x / mpsoc_y de
MPSoCConfig.py, que representam a dimensão TOTAL da malha (mesma convenção de
router_matrix.py): a célula "0x0" fica no canto inferior esquerdo e o eixo Y
cresce para cima.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


# Cores fixas, independentes do tema (claro/escuro) do MainWindow: sem
# isso, o toggle Dark/Light recoloriria essas células via
# QApplication.setPalette().
# O fundo (cor do mapa de calor) é pintado em paintEvent, pois muda a
# cada atualização da simulação.
_SLAVE_STYLESHEET = """
QLabel {
    background-color: transparent;
    color: #ffffff;
}
QLabel#slaveTitle {
    font-weight: bold;
    font-size: 11pt;
}
"""


class SlaveWidget(QWidget):
    """
    Uma célula "Slave XxY" da visão de comunicação: título, percentual de
    tráfego e a unidade ("flits"), com fundo azul e borda branca fina —
    igual ao print de referência do Communication Overview.
    """

    def __init__(self, pos_x: int, pos_y: int, parent=None):
        super().__init__(parent)
        self.setObjectName("slaveWidget")

        self.pos_x = pos_x
        self.pos_y = pos_y

        # Isola a célula do tema global do app (ver comentário de
        # _SLAVE_STYLESHEET acima).
        self.setStyleSheet(_SLAVE_STYLESHEET)
        self._background = QColor("#0000cc")

        # Cresce para preencher toda a área do scrollArea, como no print
        # (diferente do RouterWidget, que tem tamanho fixo 170x170).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(110, 110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(0)

        self.title_label = QLabel(f"Slave {pos_x}x{pos_y}")
        self.title_label.setObjectName("slaveTitle")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        layout.addWidget(self.title_label)

        layout.addStretch(1)

        self.percent_label = QLabel("0%")
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.percent_label)

        layout.addStretch(1)

        self.flits_label = QLabel("flits")
        self.flits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.flits_label)

        self.setLayout(layout)

    def _set_background(self, color: QColor) -> None:
        if color != self._background:
            self._background = QColor(color)
            self.update()

    def paintEvent(self, event):
        # Fundo com a cor do mapa de calor e borda preta de 1 px
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background)
        painter.setPen(QPen(QColor("#000000"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()

    def set_values(self, title: str, value: str, unit: str, background: QColor) -> None:
        """Atualiza a célula com os dados do mapa de calor do Communication Overview."""
        self.title_label.setText(title)
        self.percent_label.setText(value)
        self.flits_label.setText(unit)
        self._set_background(background)

    def set_traffic(self, percent: float, flits: int | None = None) -> None:
        """
        Atualiza o percentual mostrado (e, opcionalmente, a contagem de
        flits), útil para quando os dados reais de tráfego estiverem
        disponíveis.
        """
        self.percent_label.setText(f"{percent:.0f}%")
        if flits is not None:
            self.flits_label.setText(f"{flits} flits")


class SlaveMatrixWidget(QWidget):
    """
    Organiza mpsoc_x * mpsoc_y SlaveWidget em uma única grade que ocupa
    toda a área disponível (linhas e colunas com stretch igual), igual ao
    print do Communication Overview.
    """

    def __init__(self, mpsoc_x: int, mpsoc_y: int, parent=None):
        super().__init__(parent)

        # mpsoc_x/mpsoc_y é o tamanho TOTAL da malha (mesma convenção de
        # router_matrix.py) — aqui usado direto, sem noção de cluster,
        # pois o Communication Overview mostra a malha inteira de uma vez.
        self.total_cols = max(1, mpsoc_x)
        self.total_rows = max(1, mpsoc_y)

        self.slaves: dict[tuple[int, int], SlaveWidget] = {}

        self._build_matrix()

    def _build_matrix(self) -> None:
        layout = QGridLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stretch igual em todas as linhas/colunas para as células
        # dividirem uniformemente o espaço disponível, esticando para
        # preencher a largura/altura do scrollArea como no print.
        for col in range(self.total_cols):
            layout.setColumnStretch(col, 1)
        for row in range(self.total_rows):
            layout.setRowStretch(row, 1)

        for y in range(self.total_rows):
            for x in range(self.total_cols):
                slave = SlaveWidget(x, y, self)
                self.slaves[(x, y)] = slave

                # Linha 0 do grid = topo; invertemos Y para 0x0 ficar embaixo.
                grid_row = self.total_rows - 1 - y
                layout.addWidget(slave, grid_row, x)

        self.setLayout(layout)

    def get_slave(self, x: int, y: int) -> SlaveWidget | None:
        """Retorna o SlaveWidget na posição global (x, y), se existir."""
        return self.slaves.get((x, y))


# Cores fixas, independentes do tema (claro/escuro) do MainWindow — mesmo
# motivo do _SLAVE_STYLESHEET acima: sem isso, o toggle
# Dark/Light recoloriria essas células via QApplication.setPalette().
_PE_STYLESHEET = """
QWidget#peWidget {
    background-color: #ffffff;
    border: 1px solid #808080;
}
QLabel {
    background-color: transparent;
    color: #000000;
}
QLabel#peTitle {
    font-weight: bold;
}
"""

# Uma linha de tarefa: fundo com a cor da aplicação
_TASK_STYLESHEET = "QLabel {{ background-color: {background}; color: {text}; font-weight: bold; padding: 2px; }}"


def _text_color_for(background: QColor) -> str:
    """Texto preto em fundos claros e branco em fundos escuros."""
    luminance = 0.299 * background.red() + 0.587 * background.green() + 0.114 * background.blue()
    return "#000000" if luminance > 140 else "#ffffff"


class PEWidget(QWidget):
    """
    Uma célula "PEXxY" da visão de mapeamento de tarefas: fundo branco,
    borda cinza fina e um rótulo central, igual ao print de referência do
    Task Mapping Overview. Pensado para, futuramente, também mostrar a
    tarefa/status alocado no PE (ver set_task).
    """

    def __init__(self, pos_x: int, pos_y: int, parent=None):
        super().__init__(parent)
        self.setObjectName("peWidget")

        self.pos_x = pos_x
        self.pos_y = pos_y

        # Isola a célula do tema global do app (ver comentário de
        # _PE_STYLESHEET acima).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_PE_STYLESHEET)

        # Cresce para preencher toda a área do scrollArea, como no print
        # (diferente do RouterWidget, que tem tamanho fixo 170x170).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(90, 90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.pe_label = QLabel(f"PE{pos_x}x{pos_y}")
        self.pe_label.setObjectName("peTitle")
        self.pe_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.pe_label)

        # Linhas de tarefas (preenchidas por set_tasks), centralizadas na célula
        layout.addStretch(1)
        self.tasks_layout = QVBoxLayout()
        self.tasks_layout.setSpacing(2)
        layout.addLayout(self.tasks_layout)
        layout.addStretch(1)

        self.task_labels: list[QLabel] = []

        self.setLayout(layout)

    def set_tasks(self, title: str, tasks: list[tuple[str, QColor]]) -> None:
        """
        Mostra o título do PE e uma linha por tarefa, cada uma com o texto
        e a cor da aplicação a que pertence.
        """
        self.pe_label.setText(title)

        # Reaproveita os rótulos existentes e cria/remove só a diferença
        while len(self.task_labels) < len(tasks):
            label = QLabel(self)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tasks_layout.addWidget(label)
            self.task_labels.append(label)
        while len(self.task_labels) > len(tasks):
            self.task_labels.pop().deleteLater()

        for label, (text, color) in zip(self.task_labels, tasks):
            label.setText(text)
            style = _TASK_STYLESHEET.format(background=color.name(), text=_text_color_for(color))
            if label.styleSheet() != style:
                label.setStyleSheet(style)

    def set_task(self, task_name: str | None) -> None:
        """
        Atualiza o rótulo para mostrar a tarefa alocada neste PE, além da
        posição — útil para quando o mapeamento real de tarefas estiver
        disponível (ex.: filtros "Only running" / "Without Task ID").
        """
        base = f"PE{self.pos_x}x{self.pos_y}"
        self.pe_label.setText(f"{base}\n{task_name}" if task_name else base)


class PEMatrixWidget(QWidget):
    """
    Organiza mpsoc_x * mpsoc_y PEWidget em uma única grade que ocupa toda
    a área disponível (linhas e colunas com stretch igual), igual ao
    print do Task Mapping Overview.
    """

    def __init__(self, mpsoc_x: int, mpsoc_y: int, parent=None):
        super().__init__(parent)

        # mpsoc_x/mpsoc_y é o tamanho TOTAL da malha (mesma convenção de
        # router_matrix.py / SlaveMatrixWidget) — usado direto, sem noção de
        # cluster, pois o Task Mapping Overview mostra a malha inteira.
        self.total_cols = max(1, mpsoc_x)
        self.total_rows = max(1, mpsoc_y)

        self.pes: dict[tuple[int, int], PEWidget] = {}

        self._build_matrix()

    def _build_matrix(self) -> None:
        layout = QGridLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stretch igual em todas as linhas/colunas para as células
        # dividirem uniformemente o espaço disponível, esticando para
        # preencher a largura/altura do scrollArea como no print.
        for col in range(self.total_cols):
            layout.setColumnStretch(col, 1)
        for row in range(self.total_rows):
            layout.setRowStretch(row, 1)

        for y in range(self.total_rows):
            for x in range(self.total_cols):
                pe = PEWidget(x, y, self)
                self.pes[(x, y)] = pe

                # Linha 0 do grid = topo; invertemos Y para 0x0 ficar embaixo.
                grid_row = self.total_rows - 1 - y
                layout.addWidget(pe, grid_row, x)

        self.setLayout(layout)

    def get_pe(self, x: int, y: int) -> PEWidget | None:
        """Retorna o PEWidget na posição global (x, y), se existir."""
        return self.pes.get((x, y))
