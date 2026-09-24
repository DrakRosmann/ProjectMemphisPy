# -*- coding: utf-8 -*-
"""
router_matrix.py

Monta a matriz gráfica de roteadores (grade NoC/MPSoC) dentro de um QWidget,
usando como base o "Ui_Form" gerado a partir de Roteador.ui (arquivo
Roteador.py) para desenhar cada roteador individual.

Semântica dos campos de MPSoCConfig (igual ao formato de configuração do
Memphis: mpsoc_dimension é o tamanho TOTAL da malha, cluster_dimension é o
tamanho de um agrupamento dentro dela):

    mpsoc_x / mpsoc_y     -> dimensão TOTAL da malha (nº de roteadores)
    cluster_x / cluster_y -> dimensão de um cluster (agrupamento de
                              gerenciamento dentro da malha), usado só para
                              desenhar a borda de separação entre clusters

Ou seja, o total de roteadores é sempre mpsoc_x * mpsoc_y — cluster_x e
cluster_y NÃO multiplicam esse total, apenas dividem a malha em blocos
visuais (com borda) de cluster_x por cluster_y roteadores cada.

A numeração de cada roteador segue a mesma convenção do print de
referência: o roteador "0x0" fica no canto inferior esquerdo e o eixo Y
cresce para cima (0x0, 0x1, 0x2, ... de baixo para cima).

Durante a simulação, cada roteador pinta de vermelho as setas por onde o
pacote atual passou (paint_arrow) e mostra a taxa de uso de cada enlace
(update_throughput), igual ao Roteador.java do debugger original.
"""

import math
import os

from PySide6.QtCore import QEvent, QObject, QRect, Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QWidget

from Roteador import Ui_Form
from util.MPSoCConfig import MPSoCConfig


IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

# Cache das imagens já carregadas (QPixmap só pode ser criado com a QApplication ativa)
_pixmap_cache: dict[str, QPixmap] = {}


def _pixmap(name: str) -> QPixmap:
    if name not in _pixmap_cache:
        _pixmap_cache[name] = QPixmap(os.path.join(IMAGES_DIR, name))
    return _pixmap_cache[name]


# Imagem do roteador de acordo com o tipo de PE
_ROUTER_IMAGES = {
    MPSoCConfig.SLAVE: "Router.png",
    MPSoCConfig.CLUSTER_MASTER: "Router_cluster_master.png",
    MPSoCConfig.GLOBAL_MASTER: "Router_master.png",
}

# Seta -> (widget do Roteador.ui, imagem quando pintada de vermelho)
_ARROWS = {
    MPSoCConfig.EAST_IN_HIGH: ("in_east_HIGH", "red_left.png"),
    MPSoCConfig.EAST_OUT_HIGH: ("out_east_HIGH", "red_undirected_h.png"),
    MPSoCConfig.EAST_IN_LOW: ("in_east_LOW", "red_left.png"),
    MPSoCConfig.EAST_OUT_LOW: ("out_east_LOW", "red_undirected_h.png"),
    MPSoCConfig.NORTH_IN_HIGH: ("in_north_HIGH", "red_down.png"),
    MPSoCConfig.NORTH_OUT_HIGH: ("out_north_HIGH", "red_undirected_v.png"),
    MPSoCConfig.NORTH_IN_LOW: ("in_north_LOW", "red_down.png"),
    MPSoCConfig.NORTH_OUT_LOW: ("out_north_LOW", "red_undirected_v.png"),
    MPSoCConfig.WEST_IN_HIGH: ("in_weast_HIGH", "red_right.png"),
    MPSoCConfig.WEST_OUT_HIGH: ("out_weast_HIGH", "red_undirected_h.png"),
    MPSoCConfig.WEST_IN_LOW: ("in_weast_LOW", "red_right.png"),
    MPSoCConfig.WEST_OUT_LOW: ("out_weast_LOW", "red_undirected_h.png"),
    MPSoCConfig.SOUTH_IN_HIGH: ("in_south_HIGH", "red_up.png"),
    MPSoCConfig.SOUTH_OUT_HIGH: ("out_south_HIGH", "red_undirected_v.png"),
    MPSoCConfig.SOUTH_IN_LOW: ("in_south_LOW", "red_up.png"),
    MPSoCConfig.SOUTH_OUT_LOW: ("out_south_LOW", "red_undirected_v.png"),
    MPSoCConfig.LOCAL_IN: ("local_in", "red_local_in.png"),
    MPSoCConfig.LOCAL_OUT: ("local_out", "red_local_out.png"),
}

# Setas (e imagens em estado normal) de cada lado do roteador; só são
# desenhadas quando existe um vizinho naquele lado
_WEST_ARROWS = {"out_weast_HIGH": "undirected_h.png", "in_weast_HIGH": "right.png",
                "out_weast_LOW": "undirected_h.png", "in_weast_LOW": "right.png"}
_EAST_ARROWS = {"in_east_LOW": "left.png", "out_east_LOW": "undirected_h.png",
                "in_east_HIGH": "left.png", "out_east_HIGH": "undirected_h.png"}
_SOUTH_ARROWS = {"in_south_LOW": "up.png", "out_south_LOW": "undirected_v.png",
                 "in_south_HIGH": "up.png", "out_south_HIGH": "undirected_v.png"}
_NORTH_ARROWS = {"out_north_HIGH": "undirected_v.png", "in_north_HIGH": "down.png",
                 "out_north_LOW": "undirected_v.png", "in_north_LOW": "down.png"}

# Porta física -> rótulo com a taxa de uso do enlace
_PORT_LABELS = {
    MPSoCConfig.EAST0: "east_HIGH_Label",
    MPSoCConfig.EAST1: "east_LOW_Label",
    MPSoCConfig.NORTH0: "north_HIGH_Label",
    MPSoCConfig.NORTH1: "north_LOW_Label",
    MPSoCConfig.WEST0: "weast_HIGH_Label",
    MPSoCConfig.WEST1: "weast_LOW_Label",
    MPSoCConfig.SOUTH0: "south_HIGH_Label",
    MPSoCConfig.SOUTH1: "south_LOW_Label",
    MPSoCConfig.LOCAL0: "local_Label",
    MPSoCConfig.LOCAL1: "local_Label",
}


class _ImagePainter(QObject):
    """
    Desenha uma imagem esticada sobre os QWidgets "vazios" do Roteador.ui
    (setas e corpo do roteador), no lugar do UJPanelImagem do Java.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.images: dict[QWidget, str] = {}

    def set_image(self, widget: QWidget, name: str | None) -> None:
        """Define a imagem do widget; None deixa o widget vazio."""
        if self.images.get(widget) == name:
            return
        if widget not in self.images:
            widget.installEventFilter(self)
        self.images[widget] = name
        widget.update()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Paint and obj in self.images:
            if self.images[obj] is None:
                return True
            painter = QPainter(obj)
            painter.drawPixmap(obj.rect(), _pixmap(self.images[obj]))
            painter.end()
            return True
        return super().eventFilter(obj, event)


# Cores fixas do roteador, independentes do tema (claro/escuro) que o
# MainWindow aplica globalmente via QApplication.setPalette(). Sem isso,
# alternar o tema (Ctrl+T) recolore os widgets internos do roteador (portas,
# rótulos) porque eles não têm paleta própria e herdam a paleta do app,
# quebrando a visualização (fundo/texto ficam com a mesma cor, sumindo, ou
# os pequenos retângulos de porta ficam visíveis onde antes eram
# transparentes ao fundo).
_ROUTER_STYLESHEET = """
QWidget {
    background-color: #ffffff;
    color: #000000;
}
QLabel {
    background-color: transparent;
}
"""


class RouterWidget(QWidget, Ui_Form):
    """
    Um único roteador da malha. Reaproveita o layout gerado em Roteador.py
    e apenas customiza o texto central (routerLabel) para exibir a posição
    "XxY" do roteador dentro da malha, igual ao print de referência.
    """

    # Emitido com o endereço hamiltoniano quando o roteador é clicado
    clicked = Signal(int)

    def __init__(self, pos_x: int, pos_y: int, parent=None,
                 mpsoc_x: int = 1, mpsoc_y: int = 1, mpsoc_config=None):
        super().__init__(parent)
        self.setupUi(self)

        self.pos_x = pos_x
        self.pos_y = pos_y
        self.mpsoc_x = mpsoc_x
        self.mpsoc_y = mpsoc_y
        self.need_reset = True

        if mpsoc_config is not None:
            self.router_address = mpsoc_config.xy_to_ham_addr((pos_x << 8) | pos_y)
            self.pe_type = mpsoc_config.get_pe_type(self.router_address)
            if mpsoc_config.channel_number == 1:
                self._set_single_channel_geometry()
        else:
            self.router_address = pos_y * mpsoc_x + pos_x
            self.pe_type = MPSoCConfig.SLAVE

        if mpsoc_config is not None and mpsoc_config.router_addressing == MPSoCConfig.HAMILTONIAN:
            self.routerLabel.setText(str(self.router_address))
        else:
            self.routerLabel.setText(f"{pos_x}x{pos_y}")

        self.router.setCursor(Qt.CursorShape.PointingHandCursor)
        self._painter = _ImagePainter(self)

        # "Andale Mono" nem sempre está instalada; usa qualquer fonte
        # monoespaçada em tamanho fixo para o "00.00%" caber no rótulo
        percent_font = QFont("Monospace")
        percent_font.setStyleHint(QFont.StyleHint.Monospace)
        percent_font.setPixelSize(10)
        for label_name in set(_PORT_LABELS.values()):
            getattr(self, label_name).setFont(percent_font)

        # Isola este roteador do tema global do app (ver comentário acima
        # de _ROUTER_STYLESHEET): fixa cores próprias em toda a subárvore,
        # que não são afetadas por um app.setPalette() posterior.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        for child in self.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_ROUTER_STYLESHEET)

        self.reset_arrows()

    def _set_single_channel_geometry(self) -> None:
        """Com apenas um canal físico, as setas LOW ocupam o centro de cada lado."""
        self.north_LOW_Label.setGeometry(QRect(70, 0, 40, 20))
        self.in_north_LOW.setGeometry(QRect(110, 0, 20, 30))
        self.out_north_LOW.setGeometry(QRect(77, 0, 6, 30))

        self.east_LOW_Label.setGeometry(QRect(90, 30, 40, 20))
        self.in_east_LOW.setGeometry(QRect(160, 63, 33, 20))
        self.out_east_LOW.setGeometry(QRect(160, 107, 30, 6))

        self.south_LOW_Label.setGeometry(QRect(40, 110, 40, 20))
        self.in_south_LOW.setGeometry(QRect(70, 160, 20, 30))
        self.out_south_LOW.setGeometry(QRect(117, 160, 6, 30))

        self.weast_LOW_Label.setGeometry(QRect(1, 70, 40, 20))
        self.in_weast_LOW.setGeometry(QRect(0, 100, 30, 20))
        self.out_weast_LOW.setGeometry(QRect(0, 70, 30, 6))

    def mouseReleaseEvent(self, event):
        if self.router.geometry().contains(event.position().toPoint()):
            self.clicked.emit(self.router_address)
        super().mouseReleaseEvent(event)

    def reset_arrows(self) -> None:
        """Volta todas as setas para o estado normal (sem pacote passando)."""
        self.need_reset = False

        self._painter.set_image(self.router, _ROUTER_IMAGES.get(self.pe_type, "Router.png"))
        self._painter.set_image(self.local_in, "local_in.png")
        self._painter.set_image(self.local_out, "local_out.png")

        # Setas de bordas sem vizinho ficam vazias; só aparecem (em vermelho)
        # quando um pacote de periférico passa por elas
        sides = (
            (_WEST_ARROWS, self.pos_x != 0),
            (_EAST_ARROWS, self.pos_x != self.mpsoc_x - 1),
            (_SOUTH_ARROWS, self.pos_y != 0),
            (_NORTH_ARROWS, self.pos_y != self.mpsoc_y - 1),
        )

        for side, has_neighbor in sides:
            for widget_name, image in side.items():
                self._painter.set_image(getattr(self, widget_name), image if has_neighbor else None)

    def paint_arrow(self, arrow: int) -> None:
        """Pinta de vermelho a seta indicada (constantes *_IN_*/*_OUT_* do MPSoCConfig)."""
        if arrow not in _ARROWS:
            return

        widget_name, image = _ARROWS[arrow]
        self.need_reset = True
        self._painter.set_image(getattr(self, widget_name), image)

    def update_throughput(self, port: int, value: float) -> None:
        """Atualiza o percentual de uso do enlace da porta física informada."""
        label_name = _PORT_LABELS.get(port)
        if label_name is not None:
            self.set_link_load(getattr(self, label_name), value)

    def set_link_load(self, direction_label: QWidget, value: float) -> None:
        """
        Atualiza o percentual mostrado em um dos rótulos de enlace
        (north_HIGH_Label, south_LOW_Label, etc.).
        """
        value = min(value, 99.99)
        direction_label.setText(f"{value:05.2f}%")


class RouterMatrixWidget(QWidget):
    """
    Widget que organiza mpsoc_x * mpsoc_y roteadores em uma grade única,
    desenhando uma borda a cada bloco de cluster_x por cluster_y roteadores
    apenas para separação visual (sem alterar o total de roteadores).
    """

    def __init__(self, mpsoc_x: int, mpsoc_y: int,
                 cluster_x: int, cluster_y: int, parent=None, mpsoc_config=None):
        super().__init__(parent)

        self.mpsoc_config = mpsoc_config

        # mpsoc_x/mpsoc_y é o tamanho TOTAL da malha.
        self.total_cols = max(1, mpsoc_x)
        self.total_rows = max(1, mpsoc_y)

        # cluster_x/cluster_y é o tamanho de cada bloco visual; se não
        # definido (0) ou maior que a própria malha, cai para "sem cluster"
        # (um bloco único, sem bordas internas).
        self.cluster_x = max(1, min(cluster_x, self.total_cols)) if cluster_x else self.total_cols
        self.cluster_y = max(1, min(cluster_y, self.total_rows)) if cluster_y else self.total_rows

        # Guarda referência de cada roteador por posição global (x, y)
        # e pelo endereço hamiltoniano usado no traffic_router.txt
        self.routers: dict[tuple[int, int], RouterWidget] = {}
        self.routers_by_address: dict[int, RouterWidget] = {}

        self._build_matrix()

    def _build_matrix(self) -> None:
        n_clusters_x = math.ceil(self.total_cols / self.cluster_x)
        n_clusters_y = math.ceil(self.total_rows / self.cluster_y)

        draw_borders = self.cluster_x < self.total_cols or self.cluster_y < self.total_rows

        outer_layout = QGridLayout(self)
        # Roteadores grudados uns nos outros: só deixamos um pequeno
        # espaçamento entre blocos quando existe borda de cluster separando
        # eles; sem clusters, a malha fica totalmente colada (spacing 0).
        outer_layout.setSpacing(2 if draw_borders else 0)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Clusters em coordenadas de "cluster" (cx, cy), com cy=0 embaixo
        for cluster_y in range(n_clusters_y):
            for cluster_x in range(n_clusters_x):
                cluster_widget = self._build_cluster(
                    cluster_x, cluster_y, draw_borders
                )

                # Linha 0 do grid = topo da janela, então invertemos o Y
                # para que o cluster (0,0) fique embaixo, como no print.
                grid_row = n_clusters_y - 1 - cluster_y
                outer_layout.addWidget(cluster_widget, grid_row, cluster_x)

        self.setLayout(outer_layout)

    def _build_cluster(self, cluster_x: int, cluster_y: int,
                        draw_borders: bool) -> QFrame:
        """
        Cria um bloco visual contendo até cluster_x * cluster_y roteadores
        (o último bloco de cada linha/coluna pode ter menos roteadores caso
        a dimensão total não seja múltipla do tamanho do cluster).
        """
        cluster_frame = QFrame()
        cluster_frame.setObjectName(f"cluster_{cluster_x}x{cluster_y}")

        if draw_borders:
            cluster_frame.setFrameShape(QFrame.Shape.Box)
            cluster_frame.setFrameShadow(QFrame.Shadow.Plain)
            cluster_frame.setLineWidth(1)
            # Borda do cluster com cor fixa, isolada do tema global (mesmo
            # motivo do _ROUTER_STYLESHEET: sem isso, o toggle Dark/Light
            # do MainWindow também recolore essa borda de forma inconsistente).
            cluster_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            cluster_frame.setStyleSheet(
                "QFrame { background-color: #ffffff; border: 1px solid #808080; }"
            )

        cluster_layout = QGridLayout(cluster_frame)
        cluster_layout.setSpacing(0)
        # Roteadores dentro do bloco ficam colados; só reservamos uma borda
        # (via margem) quando o bloco realmente representa um cluster.
        margin = 1 if draw_borders else 0
        cluster_layout.setContentsMargins(margin, margin, margin, margin)

        # Início (inclusive) e fim (exclusivo) deste bloco na malha total
        x_start = cluster_x * self.cluster_x
        x_end = min(x_start + self.cluster_x, self.total_cols)
        y_start = cluster_y * self.cluster_y
        y_end = min(y_start + self.cluster_y, self.total_rows)

        block_rows = y_end - y_start

        for global_y in range(y_start, y_end):
            for global_x in range(x_start, x_end):
                router = RouterWidget(global_x, global_y, cluster_frame,
                                      self.total_cols, self.total_rows, self.mpsoc_config)
                self.routers[(global_x, global_y)] = router
                self.routers_by_address[router.router_address] = router

                local_x = global_x - x_start
                # Linha 0 do grid = topo, então invertemos o Y local também
                local_row = block_rows - 1 - (global_y - y_start)
                cluster_layout.addWidget(router, local_row, local_x)

        cluster_frame.setLayout(cluster_layout)
        return cluster_frame

    def get_router(self, x: int, y: int) -> RouterWidget | None:
        """Retorna o RouterWidget na posição global (x, y), se existir."""
        return self.routers.get((x, y))

    def get_router_by_address(self, router_address: int) -> RouterWidget | None:
        """Retorna o RouterWidget pelo endereço hamiltoniano, se existir."""
        return self.routers_by_address.get(router_address)

    def reset_routers(self) -> None:
        """Apaga as setas pintadas de todos os roteadores."""
        for router in self.routers.values():
            if router.need_reset:
                router.reset_arrows()