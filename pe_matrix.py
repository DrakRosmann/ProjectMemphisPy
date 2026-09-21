# -*- coding: utf-8 -*-
"""
pe_matrix.py

Monta a matriz de PEs (Processing Elements) exibida na tela de Task
Mapping Overview (taskmap.py), dentro do QScrollArea já existente naquele
formulário (self.scrollArea / self.scrollAreaWidgetContents).

Segue o mesmo padrão de slave_matrix.py: cada célula é um widget simples e
expansível (cresce para ocupar toda a largura/altura disponível no
scrollArea), com fundo branco, borda cinza e um rótulo central "PEXxY",
igual ao print de referência do Task Mapping Overview.

Usa apenas mpsoc_x / mpsoc_y de MPSoCConfig.py, que representam a dimensão
TOTAL da malha (mesma convenção de router_matrix.py e slave_matrix.py): o
PE "0x0" fica no canto inferior esquerdo e o eixo Y cresce para cima.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


# Cores fixas, independentes do tema (claro/escuro) do MainWindow — mesmo
# motivo do _ROUTER_STYLESHEET em router_matrix.py e do _SLAVE_STYLESHEET
# em slave_matrix.py: sem isso, o toggle Dark/Light recoloriria essas
# células via QApplication.setPalette().
_PE_STYLESHEET = """
QWidget#peWidget {
    background-color: #ffffff;
    border: 1px solid #808080;
}
QLabel {
    background-color: transparent;
    color: #000000;
}
"""


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

        self.pe_label = QLabel(f"PE{pos_x}x{pos_y}")
        self.pe_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.pe_label)

        self.setLayout(layout)

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
        # router_matrix.py / slave_matrix.py) — usado direto, sem noção de
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
