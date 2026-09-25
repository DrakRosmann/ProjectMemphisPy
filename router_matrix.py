# -*- coding: utf-8 -*-
"""
router_matrix.py

Desenha a matriz de roteadores (grade NoC/MPSoC) com QGraphicsView /
QGraphicsScene: corpo dos roteadores, setas dos enlaces, porta local e
periféricos são desenhados em vetor pelo próprio Qt (sem imagens), então a
malha pode ser ampliada/reduzida sem perder nitidez.

Semântica dos campos de MPSoCConfig (igual ao formato de configuração do
Memphis: mpsoc_dimension é o tamanho TOTAL da malha, cluster_dimension é o
tamanho de um agrupamento dentro dela):

    mpsoc_x / mpsoc_y     -> dimensão TOTAL da malha (nº de roteadores)
    cluster_x / cluster_y -> dimensão de um cluster (agrupamento de
                              gerenciamento dentro da malha), usado só para
                              desenhar a borda de separação entre clusters

A numeração de cada roteador segue a convenção do debugger original: o
roteador "0x0" fica no canto inferior esquerdo e o eixo Y cresce para cima.

Cada enlace entre dois roteadores vizinhos tem, por canal (HIGH/LOW), uma
seta em cada sentido. A mesma seta é, ao mesmo tempo, a saída de um roteador
e a entrada do vizinho (ex.: EAST_OUT_HIGH de 0x0 == WEST_IN_HIGH de 1x0),
por isso os dois roteadores guardam a mesma ArrowItem. Nas bordas da malha,
as setas ligam o roteador à caixa do periférico (desenhada fora do roteador).

Durante a simulação, cada roteador pinta de vermelho as setas por onde o
pacote atual passou (paint_arrow) e mostra a taxa de uso de cada enlace
(update_throughput), igual ao Roteador.java do debugger original.

Zoom: Ctrl + roda do mouse (ou gesto de pinça), Ctrl +/-/0, os botões no
canto da vista ou duplo clique no fundo (ajusta a malha à janela). Arrastar
o fundo move a vista.
"""

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QImage, QKeySequence, QPainter,
                           QPainterPath, QPen, QPolygonF, QShortcut)
from PySide6.QtWidgets import (QFrame, QGraphicsItem, QGraphicsObject, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsView, QHBoxLayout, QLabel, QToolButton)

import theme
from util.MPSoCConfig import MPSoCConfig


# ==========================================
# GEOMETRIA (unidades da cena = pixels com zoom 100%)
# ==========================================
BODY = 130                  # lado do corpo do roteador
GAP = 64                    # espaço entre dois roteadores (onde ficam as setas)
PITCH = BODY + GAP
ARROW_OFFSET = 8            # distância de cada seta do par ao centro do canal
ARROW_MARGIN = 4            # folga entre a ponta da seta e o corpo do roteador
SHAFT_WIDTH = 4.5
HEAD_LENGTH = 11
HEAD_WIDTH = 12

# Caixa do periférico: mais larga nas bordas norte/sul (setas verticais) e mais
# alta nas bordas leste/oeste, para cobrir os dois pares de setas
PERIPHERAL_NS = QSize(110, 38)
PERIPHERAL_EW = QSize(100, 90)

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.1, 8.0, 1.25

# Cor do corpo do roteador de acordo com o tipo de PE (as mesmas das imagens antigas)
_ROUTER_COLORS = {
    MPSoCConfig.SLAVE: "#b7dde8",
    MPSoCConfig.CLUSTER_MASTER: "#c4d6a0",
    MPSoCConfig.GLOBAL_MASTER: "#f9c499",
}
_PE_TYPE_NAMES = {
    MPSoCConfig.SLAVE: "Slave PE",
    MPSoCConfig.CLUSTER_MASTER: "Cluster manager PE",
    MPSoCConfig.GLOBAL_MASTER: "Global manager PE",
}
_BODY_BORDER = "#2d2e2f"
_HIGHLIGHT = "#ff8c00"

_SIDE_NAMES = {"N": "north", "S": "south", "E": "east", "W": "west"}
_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
# Direção "para fora" de cada lado, em coordenadas da cena (Y cresce para baixo)
_OUTWARD = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}

HIGH, LOW = MPSoCConfig.HIGH, MPSoCConfig.LOW

# (lado, canal) -> (seta de entrada, seta de saída) nas constantes do MPSoCConfig
_SIDE_ARROWS = {
    ("E", HIGH): (MPSoCConfig.EAST_IN_HIGH, MPSoCConfig.EAST_OUT_HIGH),
    ("E", LOW): (MPSoCConfig.EAST_IN_LOW, MPSoCConfig.EAST_OUT_LOW),
    ("W", HIGH): (MPSoCConfig.WEST_IN_HIGH, MPSoCConfig.WEST_OUT_HIGH),
    ("W", LOW): (MPSoCConfig.WEST_IN_LOW, MPSoCConfig.WEST_OUT_LOW),
    ("N", HIGH): (MPSoCConfig.NORTH_IN_HIGH, MPSoCConfig.NORTH_OUT_HIGH),
    ("N", LOW): (MPSoCConfig.NORTH_IN_LOW, MPSoCConfig.NORTH_OUT_LOW),
    ("S", HIGH): (MPSoCConfig.SOUTH_IN_HIGH, MPSoCConfig.SOUTH_OUT_HIGH),
    ("S", LOW): (MPSoCConfig.SOUTH_IN_LOW, MPSoCConfig.SOUTH_OUT_LOW),
}

# Porta física -> (lado, canal) do rótulo com a taxa de uso do enlace
_PORT_SIDES = {
    MPSoCConfig.EAST0: ("E", HIGH), MPSoCConfig.EAST1: ("E", LOW),
    MPSoCConfig.WEST0: ("W", HIGH), MPSoCConfig.WEST1: ("W", LOW),
    MPSoCConfig.NORTH0: ("N", HIGH), MPSoCConfig.NORTH1: ("N", LOW),
    MPSoCConfig.SOUTH0: ("S", HIGH), MPSoCConfig.SOUTH1: ("S", LOW),
}
_LOCAL_PORTS = (MPSoCConfig.LOCAL0, MPSoCConfig.LOCAL1)


def _channel_positions(mpsoc_config) -> dict[int, float]:
    """
    Posição (ao longo do lado do roteador) do centro de cada canal. Com um
    canal físico só existem as portas ímpares (LOW, ver read_traffic_data),
    que ficam no meio do lado.
    """
    if mpsoc_config is not None and mpsoc_config.channel_number == 1:
        return {LOW: BODY * 0.5}
    return {HIGH: BODY * 0.3, LOW: BODY * 0.7}


def _percent_font() -> QFont:
    # "Andale Mono" nem sempre está instalada; qualquer monoespaçada serve
    font = QFont("Monospace")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(10)
    return font


def _format_load(value: float) -> str:
    return f"{min(value, 99.99):05.2f}%"


class _MeshScene(QGraphicsScene):
    """Cena da malha; guarda as cores do tema atual, lidas pelos itens ao pintar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = theme.matrix_colors(False)


# ==========================================
# ITENS DA CENA
# ==========================================
class ArrowItem(QGraphicsItem):
    """
    Seta de um enlace, de `start` até `end`. Fica cinza normalmente e vermelha
    quando o pacote atual passou por ela. Setas `optional` (bordas da malha sem
    periférico conhecido) só aparecem enquanto estão pintadas.
    """

    def __init__(self, start: QPointF, end: QPointF, optional: bool = False, tooltip: str = ""):
        super().__init__()
        self.painted = False
        self.optional = optional

        delta = end - start
        self._length = math.hypot(delta.x(), delta.y())
        self.setPos(start)
        self.setRotation(math.degrees(math.atan2(delta.y(), delta.x())))
        self.setZValue(1)
        if tooltip:
            self.setToolTip(tooltip)

        length, shaft, head = self._length, SHAFT_WIDTH / 2, HEAD_WIDTH / 2
        neck = length - HEAD_LENGTH
        self._polygon = QPolygonF([
            QPointF(0, -shaft), QPointF(neck, -shaft), QPointF(neck, -head), QPointF(length, 0),
            QPointF(neck, head), QPointF(neck, shaft), QPointF(0, shaft),
        ])
        self._update_visibility()

    def set_painted(self, painted: bool) -> None:
        if painted != self.painted:
            self.painted = painted
            self._update_visibility()
            self.update()

    def set_optional(self, optional: bool) -> None:
        self.optional = optional
        self._update_visibility()

    def _update_visibility(self) -> None:
        self.setVisible(self.painted or not self.optional)

    def boundingRect(self) -> QRectF:
        return QRectF(0, -HEAD_WIDTH / 2 - 1, self._length + 1, HEAD_WIDTH + 2)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        colors = self.scene().colors
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors.arrow_active if self.painted else colors.arrow))
        painter.drawPolygon(self._polygon)


class PeripheralItem(QGraphicsItem):
    """Caixa com o nome do periférico ligado a uma porta de borda, fora do roteador."""

    def __init__(self, rect: QRectF, name: str, router_label: str, side: str):
        super().__init__()
        self._rect = rect
        self.name = name
        self.setZValue(1)
        self.setToolTip(f"Peripheral {name} at the {_SIDE_NAMES[side]} port of router {router_label}")
        self._font = QFont()
        self._font.setBold(True)
        self._font.setPixelSize(12)

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-1, -1, 1, 1)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        colors = self.scene().colors
        color = QColor(colors.peripheral_text)
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(QColor(colors.peripheral_fill))
        painter.drawRoundedRect(self._rect, 6, 6)

        painter.setFont(self._font)
        text_rect = self._rect.adjusted(6, 4, -6, -4)
        text = QFontMetricsF(self._font).elidedText(self.name, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)


class RouterItem(QGraphicsObject):
    """
    Um roteador da malha: corpo colorido pelo tipo de PE, nome no centro,
    porcentagem de uso de cada enlace junto ao lado correspondente e, no canto
    superior esquerdo (fora do corpo), as setas e a porcentagem da porta local.
    As setas dos enlaces são itens próprios (ArrowItem), compartilhados com o
    vizinho, e ficam em `self.arrows`.
    """

    # Emitido com o endereço hamiltoniano quando o roteador é clicado
    clicked = Signal(int)

    def __init__(self, pos_x: int, pos_y: int, mpsoc_x: int = 1, mpsoc_y: int = 1, mpsoc_config=None):
        super().__init__()
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.mpsoc_x = mpsoc_x
        self.mpsoc_y = mpsoc_y
        self.need_reset = False
        self.highlighted = False
        self._hovered = False

        if mpsoc_config is not None:
            self.router_address = mpsoc_config.xy_to_ham_addr((pos_x << 8) | pos_y)
            self.pe_type = mpsoc_config.get_pe_type(self.router_address)
        else:
            self.router_address = pos_y * mpsoc_x + pos_x
            self.pe_type = MPSoCConfig.SLAVE

        self.xy_label = f"{pos_x}x{pos_y}"
        if mpsoc_config is not None and mpsoc_config.router_addressing == MPSoCConfig.HAMILTONIAN:
            self.label = str(self.router_address)
        else:
            self.label = self.xy_label

        self._channels = _channel_positions(mpsoc_config)

        # Constante do MPSoCConfig (*_IN_* / *_OUT_* / LOCAL_*) -> ArrowItem
        self.arrows: dict[int, ArrowItem] = {}
        # Periféricos ligados às portas de borda: lado ("N", "S", "E", "W") -> nome
        self.peripherals: dict[str, str] = {}
        # Callback da matriz que desenha a caixa do periférico
        self._peripheral_added = None

        self._loads = {key: _format_load(0) for key in _PORT_SIDES.values()}
        self._local_load = _format_load(0)

        self._name_font = QFont("Arial")
        self._name_font.setBold(True)
        self._name_font.setPixelSize(19)
        self._percent_font = _percent_font()

        self.setZValue(2)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        pe_name = _PE_TYPE_NAMES.get(self.pe_type, "PE")
        self.setToolTip(f"Router {self.label} ({self.xy_label}, address {self.router_address})\n"
                        f"{pe_name} - click for details")

    # ---------- desenho ----------
    def body_rect(self) -> QRectF:
        return QRectF(0, 0, BODY, BODY)

    def boundingRect(self) -> QRectF:
        # Inclui a porcentagem da porta local (canto superior esquerdo, fora do
        # corpo) e a moldura de destaque
        return QRectF(-GAP, -GAP, BODY + GAP + 6, BODY + GAP + 6)

    def shape(self) -> QPainterPath:
        # Só o corpo recebe cliques e hover
        path = QPainterPath()
        path.addRect(self.body_rect())
        return path

    def _label_rect(self, side: str, position: float) -> QRectF:
        width, height, pad = 44, 14, 4
        if side == "E":
            return QRectF(BODY - width - pad, position - height / 2, width, height)
        if side == "W":
            return QRectF(pad, position - height / 2, width, height)
        if side == "N":
            return QRectF(position - width / 2, pad, width, height)
        return QRectF(position - width / 2, BODY - height - pad, width, height)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        colors = self.scene().colors
        body = self.body_rect()

        painter.setPen(QPen(QColor(_BODY_BORDER), 2.5 if self._hovered else 1.2))
        painter.setBrush(QColor(_ROUTER_COLORS.get(self.pe_type, _ROUTER_COLORS[MPSoCConfig.SLAVE])))
        painter.drawRect(body)

        # O corpo tem cor clara nos dois temas: textos internos sempre pretos
        painter.setPen(QColor("#000000"))
        painter.setFont(self._name_font)
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter, self.label)

        painter.setFont(self._percent_font)
        for (side, channel), text in self._loads.items():
            position = self._channels.get(channel)
            if position is None:
                continue
            align = {"E": Qt.AlignmentFlag.AlignRight, "W": Qt.AlignmentFlag.AlignLeft}.get(
                side, Qt.AlignmentFlag.AlignHCenter)
            painter.drawText(self._label_rect(side, position), align | Qt.AlignmentFlag.AlignVCenter, text)

        # Porta local: acima das setas diagonais, no canto fora do corpo
        painter.setPen(QColor(colors.text))
        painter.drawText(QRectF(-GAP + 2, -GAP + 1, 46, 13), Qt.AlignmentFlag.AlignLeft, self._local_load)

        if self.highlighted:
            painter.setPen(QPen(QColor(_HIGHLIGHT), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(body.adjusted(-4, -4, 4, 4), 6, 6)

    # ---------- interação ----------
    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # Aceitar o clique impede que a vista comece a arrastar a partir do roteador
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.body_rect().contains(event.pos()):
            self.clicked.emit(self.router_address)
        super().mouseReleaseEvent(event)

    # ---------- estado da simulação ----------
    def reset_arrows(self) -> None:
        """Volta todas as setas para o estado normal (sem pacote passando)."""
        self.need_reset = False
        for arrow in self.arrows.values():
            arrow.set_painted(False)
        if self.highlighted:
            self.highlighted = False
            self.update()

    def paint_arrow(self, arrow: int) -> None:
        """Pinta de vermelho a seta indicada (constantes *_IN_*/*_OUT_*/LOCAL_* do MPSoCConfig)."""
        item = self.arrows.get(arrow)
        if item is not None:
            self.need_reset = True
            item.set_painted(True)

    def set_highlight(self, on: bool = True) -> None:
        """Moldura laranja em volta do roteador (some no próximo reset das setas)."""
        self.highlighted = on
        if on:
            self.need_reset = True
        self.update()

    def set_peripheral(self, side: str, name: str) -> None:
        """Mostra o periférico `name` ligado à porta de borda `side` ("N", "S", "E" ou "W")."""
        if self.peripherals.get(side) == name:
            return
        self.peripherals[side] = name
        if self._peripheral_added is not None:
            self._peripheral_added(self, side, name)

    def update_throughput(self, port: int, value: float) -> None:
        """Atualiza o percentual de uso do enlace da porta física informada."""
        text = _format_load(value)
        if port in _LOCAL_PORTS:
            changed = self._local_load != text
            self._local_load = text
        elif port in _PORT_SIDES:
            key = _PORT_SIDES[port]
            changed = self._loads[key] != text
            self._loads[key] = text
        else:
            return
        if changed:
            self.update()

    def link_load(self, port: int) -> str:
        """Texto mostrado para a taxa de uso da porta (usado nos testes)."""
        if port in _LOCAL_PORTS:
            return self._local_load
        return self._loads[_PORT_SIDES[port]]


# ==========================================
# VISTA DA MALHA
# ==========================================
class _ZoomControls(QFrame):
    """Botões de zoom no canto inferior direito da vista."""

    def __init__(self, view: "RouterMatrixWidget"):
        super().__init__(view)
        self.setObjectName("zoomControls")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(2)

        def button(text, tooltip, slot):
            tool = QToolButton(self)
            tool.setText(text)
            tool.setToolTip(tooltip)
            tool.setAutoRaise(True)
            tool.clicked.connect(slot)
            layout.addWidget(tool)
            return tool

        button("−", "Zoom out (Ctrl+-)", view.zoom_out)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumWidth(44)
        self.label.setToolTip("Zoom level - Ctrl + mouse wheel to zoom")
        layout.addWidget(self.label)
        button("+", "Zoom in (Ctrl++)", view.zoom_in)
        button("1:1", "Actual size (Ctrl+0)", view.reset_zoom)
        button("Fit", "Fit the mesh to the window (double-click the background)", view.fit_to_view)

    def set_zoom(self, zoom: float) -> None:
        self.label.setText(f"{round(zoom * 100)}%")


class RouterMatrixWidget(QGraphicsView):
    """
    Vista com os mpsoc_x * mpsoc_y roteadores, desenhando uma borda a cada
    bloco de cluster_x por cluster_y roteadores apenas para separação visual
    (sem alterar o total de roteadores).
    """

    zoom_changed = Signal(float)

    def __init__(self, mpsoc_x: int, mpsoc_y: int,
                 cluster_x: int, cluster_y: int, parent=None, mpsoc_config=None):
        self._scene = _MeshScene()
        super().__init__(self._scene, parent)
        self._scene.setParent(self)

        self.mpsoc_config = mpsoc_config
        self.total_cols = max(1, mpsoc_x)
        self.total_rows = max(1, mpsoc_y)

        # cluster_x/cluster_y é o tamanho de cada bloco visual; se não definido
        # (0) ou maior que a própria malha, cai para "sem cluster"
        self.cluster_x = max(1, min(cluster_x, self.total_cols)) if cluster_x else self.total_cols
        self.cluster_y = max(1, min(cluster_y, self.total_rows)) if cluster_y else self.total_rows

        # Roteadores por posição global (x, y) e pelo endereço hamiltoniano
        # usado no traffic_router.txt
        self.routers: dict[tuple[int, int], RouterItem] = {}
        self.routers_by_address: dict[int, RouterItem] = {}
        self.peripheral_items: dict[tuple[int, int, str], PeripheralItem] = {}
        self._cluster_items: list[QGraphicsRectItem] = []
        self._channels = _channel_positions(mpsoc_config)

        self._zoom = 1.0
        # Até o usuário mexer no zoom, a malha acompanha o tamanho da janela
        self._auto_fit = True

        self.setObjectName("routerMatrix")
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.viewport().grabGesture(Qt.GestureType.PinchGesture)

        self._build_matrix()

        self._controls = _ZoomControls(self)
        self._controls.set_zoom(self._zoom)

        for keys, slot in ((QKeySequence.StandardKey.ZoomIn, self.zoom_in),
                           (QKeySequence.StandardKey.ZoomOut, self.zoom_out),
                           ("Ctrl+=", self.zoom_in),
                           ("Ctrl+0", self.reset_zoom)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

    # ---------- construção ----------
    def _body_origin(self, x: int, y: int) -> QPointF:
        # Linha 0 da cena = topo: invertemos o Y para o 0x0 ficar embaixo
        return QPointF(x * PITCH, (self.total_rows - 1 - y) * PITCH)

    def _build_matrix(self) -> None:
        for y in range(self.total_rows):
            for x in range(self.total_cols):
                router = RouterItem(x, y, self.total_cols, self.total_rows, self.mpsoc_config)
                router.setPos(self._body_origin(x, y))
                router._peripheral_added = self._add_peripheral
                self._scene.addItem(router)
                self.routers[(x, y)] = router
                self.routers_by_address[router.router_address] = router
                self._add_local_arrows(router)

        for (x, y), router in self.routers.items():
            for side in ("E", "N"):
                neighbor = self.get_router(x + 1, y) if side == "E" else self.get_router(x, y + 1)
                if neighbor is not None:
                    self._add_link(router, side, neighbor)
            for side, at_border in (("W", x == 0), ("E", x == self.total_cols - 1),
                                    ("S", y == 0), ("N", y == self.total_rows - 1)):
                if at_border:
                    self._add_link(router, side, None)

        if self.cluster_x < self.total_cols or self.cluster_y < self.total_rows:
            self._add_cluster_borders()

        self._update_scene_rect()

    def _edge_point(self, router: RouterItem, side: str, position: float, distance: float) -> QPointF:
        """Ponto a `distance` para fora do lado `side`, a `position` ao longo dele."""
        origin = router.pos()
        dx, dy = _OUTWARD[side]
        if side in ("E", "W"):
            edge_x = origin.x() + (BODY if side == "E" else 0)
            return QPointF(edge_x + dx * distance, origin.y() + position)
        edge_y = origin.y() + (BODY if side == "S" else 0)
        return QPointF(origin.x() + position, edge_y + dy * distance)

    def _add_link(self, router: RouterItem, side: str, neighbor: RouterItem | None) -> None:
        """
        Setas do lado `side` do roteador, uma por sentido e por canal. Com
        `neighbor` None é uma borda da malha: as setas ligam o roteador ao
        periférico e ficam ocultas até existir um (ou um pacote passar).
        """
        near, far = ARROW_MARGIN, GAP - ARROW_MARGIN
        # Desloca o par perpendicularmente: a saída fica "à esquerda" de quem sai
        out_shift = -ARROW_OFFSET if side in ("E", "S") else ARROW_OFFSET
        other = neighbor.label if neighbor is not None else f"{_SIDE_NAMES[side]} peripheral"

        for channel, position in self._channels.items():
            channel_name = "HIGH" if channel == HIGH else "LOW"
            out_pos, in_pos = position + out_shift, position - out_shift

            outgoing = ArrowItem(self._edge_point(router, side, out_pos, near),
                                 self._edge_point(router, side, out_pos, far),
                                 optional=neighbor is None,
                                 tooltip=f"{router.label} → {other} ({channel_name})")
            incoming = ArrowItem(self._edge_point(router, side, in_pos, far),
                                 self._edge_point(router, side, in_pos, near),
                                 optional=neighbor is None,
                                 tooltip=f"{other} → {router.label} ({channel_name})")
            self._scene.addItem(outgoing)
            self._scene.addItem(incoming)

            in_arrow, out_arrow = _SIDE_ARROWS[(side, channel)]
            router.arrows[out_arrow] = outgoing
            router.arrows[in_arrow] = incoming
            if neighbor is not None:
                neighbor_in, neighbor_out = _SIDE_ARROWS[(_OPPOSITE[side], channel)]
                neighbor.arrows[neighbor_in] = outgoing
                neighbor.arrows[neighbor_out] = incoming

    def _add_local_arrows(self, router: RouterItem) -> None:
        """Setas diagonais da porta local, no canto superior esquerdo do corpo."""
        corner = router.pos()
        shift = QPointF(5, -5)      # perpendicular à diagonal
        near, far = QPointF(-ARROW_MARGIN, -ARROW_MARGIN), QPointF(-GAP * 0.6, -GAP * 0.6)

        local_in = ArrowItem(corner + far + shift, corner + near + shift,
                             tooltip=f"PE → router {router.label} (local port)")
        local_out = ArrowItem(corner + near - shift, corner + far - shift,
                              tooltip=f"Router {router.label} → PE (local port)")
        self._scene.addItem(local_in)
        self._scene.addItem(local_out)
        router.arrows[MPSoCConfig.LOCAL_IN] = local_in
        router.arrows[MPSoCConfig.LOCAL_OUT] = local_out

    def _add_peripheral(self, router: RouterItem, side: str, name: str) -> None:
        key = (router.pos_x, router.pos_y, side)
        old = self.peripheral_items.pop(key, None)
        if old is not None:
            self._scene.removeItem(old)

        size = PERIPHERAL_NS if side in ("N", "S") else PERIPHERAL_EW
        center = self._edge_point(router, side, BODY / 2, GAP + (size.height() if side in ("N", "S")
                                                                  else size.width()) / 2)
        rect = QRectF(center.x() - size.width() / 2, center.y() - size.height() / 2,
                      size.width(), size.height())
        item = PeripheralItem(rect, name, router.label, side)
        self._scene.addItem(item)
        self.peripheral_items[key] = item

        for channel in self._channels:
            for arrow in _SIDE_ARROWS[(side, channel)]:
                router.arrows[arrow].set_optional(False)

        self._update_scene_rect()

    def _add_cluster_borders(self) -> None:
        half = GAP / 2
        for cy in range(math.ceil(self.total_rows / self.cluster_y)):
            for cx in range(math.ceil(self.total_cols / self.cluster_x)):
                x0, y0 = cx * self.cluster_x, cy * self.cluster_y
                x1 = min(x0 + self.cluster_x, self.total_cols) - 1
                y1 = min(y0 + self.cluster_y, self.total_rows) - 1
                top_left = self._body_origin(x0, y1)
                bottom_right = self._body_origin(x1, y0) + QPointF(BODY, BODY)
                rect = QRectF(top_left, bottom_right).adjusted(-half + 2, -half + 2, half - 2, half - 2)

                item = QGraphicsRectItem(rect)
                item.setZValue(0)
                item.setBrush(Qt.BrushStyle.NoBrush)
                self._scene.addItem(item)
                self._cluster_items.append(item)
        self._apply_cluster_pen()

    def _apply_cluster_pen(self) -> None:
        pen = QPen(QColor(self._scene.colors.cluster_border), 1.5, Qt.PenStyle.DashLine)
        for item in self._cluster_items:
            item.setPen(pen)

    def _update_scene_rect(self) -> None:
        # Todas as setas de borda contam (mesmo ocultas), para a cena não mudar
        # de tamanho quando um pacote de periférico aparece
        rect = QRectF()
        for item in self._scene.items():
            rect = rect.united(item.sceneBoundingRect())
        self._scene.setSceneRect(rect.adjusted(-16, -16, 16, 16))

    # ---------- API usada pela janela principal e pela simulação ----------
    def get_router(self, x: int, y: int) -> RouterItem | None:
        """Retorna o roteador na posição global (x, y), se existir."""
        return self.routers.get((x, y))

    def get_router_by_address(self, router_address: int) -> RouterItem | None:
        """Retorna o roteador pelo endereço hamiltoniano, se existir."""
        return self.routers_by_address.get(router_address)

    def set_peripherals(self, peripherals) -> None:
        """Periféricos (testcase_files.Peripheral) nas bordas da malha."""
        for peripheral in peripherals:
            router = self.get_router(peripheral.x, peripheral.y)
            if router is not None:
                router.set_peripheral(peripheral.side, peripheral.name)

    def reset_routers(self) -> None:
        """Apaga as setas pintadas de todos os roteadores."""
        for router in self.routers.values():
            if router.need_reset:
                router.reset_arrows()

    def apply_theme(self, dark: bool) -> None:
        """Aplica as cores do tema claro ou escuro na malha."""
        self._scene.colors = theme.matrix_colors(dark)
        self.setBackgroundBrush(QBrush(QColor(self._scene.colors.canvas)))
        self._apply_cluster_pen()
        self._scene.update()

    def ensure_router_visible(self, router: RouterItem) -> None:
        self.ensureVisible(router.sceneBoundingRect(), 20, 20)

    def to_image(self, scale: float = 2.0) -> QImage:
        """A malha inteira (independente do zoom e da rolagem) como imagem."""
        source = self._scene.sceneRect()
        image = QImage(max(1, round(source.width() * scale)), max(1, round(source.height() * scale)),
                       QImage.Format.Format_ARGB32)
        image.fill(QColor(self._scene.colors.canvas))
        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self._scene.render(painter, QRectF(image.rect()), source)
        painter.end()
        return image

    # ---------- zoom ----------
    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float, user: bool = True) -> None:
        zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
        if user:
            self._auto_fit = False
        if math.isclose(zoom, self._zoom):
            return
        self.scale(zoom / self._zoom, zoom / self._zoom)
        self._zoom = zoom
        self._controls.set_zoom(zoom)
        self.zoom_changed.emit(zoom)

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom * ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom / ZOOM_STEP)

    def reset_zoom(self) -> None:
        self.set_zoom(1.0)

    def fit_to_view(self, user: bool = True) -> None:
        """Ajusta o zoom para a malha inteira caber na vista."""
        rect = self._scene.sceneRect()
        viewport = self.viewport().size()
        if rect.isEmpty() or viewport.isEmpty():
            return
        zoom = min(viewport.width() / rect.width(), viewport.height() / rect.height())
        anchor = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.set_zoom(zoom, user)
        self.setTransformationAnchor(anchor)
        self.centerOn(rect.center())
        if user:
            # "Fit" volta a acompanhar o tamanho da janela
            self._auto_fit = True

    def _auto_zoom(self) -> None:
        """Zoom inicial: 100%, ou menos se a malha não couber na janela."""
        if not self._auto_fit:
            return
        rect = self._scene.sceneRect()
        viewport = self.viewport().size()
        if rect.isEmpty() or viewport.isEmpty():
            return
        fit = min(viewport.width() / rect.width(), viewport.height() / rect.height())
        if fit < 1:
            self.fit_to_view(user=False)
        else:
            self.set_zoom(1.0, user=False)
            self.centerOn(rect.center())

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() / 120
            if steps:
                self.set_zoom(self._zoom * ZOOM_STEP ** steps)
            event.accept()
            return
        super().wheelEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.Gesture:
            pinch = event.gesture(Qt.GestureType.PinchGesture)
            if pinch is not None:
                self.set_zoom(self._zoom * pinch.scaleFactor())
                event.accept()
                return True
        elif event.type() == QEvent.Type.NativeGesture and \
                event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self.set_zoom(self._zoom * (1 + event.value()))
            event.accept()
            return True
        return super().viewportEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.itemAt(event.position().toPoint()) is None:
            self.fit_to_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 8
        viewport = self.viewport().geometry()
        self._controls.adjustSize()
        self._controls.move(viewport.right() - self._controls.width() - margin,
                            viewport.bottom() - self._controls.height() - margin)
        self._controls.raise_()
        # Adia para depois do layout terminar (o viewport já com o tamanho final)
        QTimer.singleShot(0, self, self._auto_zoom)
