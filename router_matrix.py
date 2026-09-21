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
"""

import math

from PySide6.QtWidgets import QFrame, QGridLayout, QWidget

from Roteador import Ui_Form


class RouterWidget(QWidget, Ui_Form):
    """
    Um único roteador da malha. Reaproveita o layout gerado em Roteador.py
    e apenas customiza o texto central (routerLabel) para exibir a posição
    "XxY" do roteador dentro da malha, igual ao print de referência.
    """

    def __init__(self, pos_x: int, pos_y: int, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.pos_x = pos_x
        self.pos_y = pos_y

        self.routerLabel.setText(f"{pos_x}x{pos_y}")

    def set_link_load(self, direction_label: QWidget, value: float) -> None:
        """
        Atualiza o percentual mostrado em um dos rótulos de enlace
        (north_HIGH_Label, south_LOW_Label, etc.), útil para quando os dados
        reais de tráfego estiverem disponíveis.
        """
        direction_label.setText(f"{value:05.2f}%")


class RouterMatrixWidget(QWidget):
    """
    Widget que organiza mpsoc_x * mpsoc_y roteadores em uma grade única,
    desenhando uma borda a cada bloco de cluster_x por cluster_y roteadores
    apenas para separação visual (sem alterar o total de roteadores).
    """

    def __init__(self, mpsoc_x: int, mpsoc_y: int,
                 cluster_x: int, cluster_y: int, parent=None):
        super().__init__(parent)

        # mpsoc_x/mpsoc_y é o tamanho TOTAL da malha.
        self.total_cols = max(1, mpsoc_x)
        self.total_rows = max(1, mpsoc_y)

        # cluster_x/cluster_y é o tamanho de cada bloco visual; se não
        # definido (0) ou maior que a própria malha, cai para "sem cluster"
        # (um bloco único, sem bordas internas).
        self.cluster_x = max(1, min(cluster_x, self.total_cols)) if cluster_x else self.total_cols
        self.cluster_y = max(1, min(cluster_y, self.total_rows)) if cluster_y else self.total_rows

        # Guarda referência de cada roteador por posição global (x, y)
        self.routers: dict[tuple[int, int], RouterWidget] = {}

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
                router = RouterWidget(global_x, global_y, cluster_frame)
                self.routers[(global_x, global_y)] = router

                local_x = global_x - x_start
                # Linha 0 do grid = topo, então invertemos o Y local também
                local_row = block_rows - 1 - (global_y - y_start)
                cluster_layout.addWidget(router, local_row, local_x)

        cluster_frame.setLayout(cluster_layout)
        return cluster_frame

    def get_router(self, x: int, y: int) -> RouterWidget | None:
        """Retorna o RouterWidget na posição global (x, y), se existir."""
        return self.routers.get((x, y))