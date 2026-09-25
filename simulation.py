"""
Controle da simulação dos roteadores (play / próximo pacote / stop / voltar no tempo).

Refatoração da parte de simulação do MainFrame.java e do CheckpointController.java
do GraphicalDebugger original. A thread com sleep() do Java foi trocada por um
QTimer, que roda no laço de eventos do Qt e pode atualizar a interface com segurança.
"""

from PySide6.QtCore import QObject, QTimer, Signal

from util.MPSoCConfig import MPSoCConfig

# Velocidade (slider 0-100) acima da qual os roteadores não são redesenhados,
# para avançar o mais rápido possível
MAX_REPAINT_SPEED = 98

# Pacotes processados por passo do timer quando está sem redesenhar
FAST_BATCH_SIZE = 200

# No "voltar no tempo", só os últimos pacotes são desenhados
GO_REPAINT_LAST_PACKETS = 50


class CheckpointController:
    """
    Divide a simulação em janelas de tempo. Ao fim de cada janela a taxa de uso
    dos enlaces é recalculada (checkpoint_reached).
    """

    def __init__(self, clock_period_ns, checkpoint_reached, window_size_ms=0.5):
        self.clock_period_ns = clock_period_ns
        self.checkpoint_reached = checkpoint_reached
        self.window_size_ms = window_size_ms
        self.reset()

    def reset(self):
        self.window_init_ms = 0.0
        self.current_time_ms = 0.0

    def set_time(self, time_in_ticks):
        self.current_time_ms = ticks_to_ms(time_in_ticks, self.clock_period_ns)

        if self.current_time_ms - self.window_init_ms > self.window_size_ms:
            self.window_init_ms = self.current_time_ms
            self.checkpoint_reached()

    def get_window_size_in_ns(self):
        return self.window_size_ms * 1_000_000


def ticks_to_ms(ticks, clock_period_ns):
    return ticks * clock_period_ns / 1_000_000


# Porta de entrada -> (seta no roteador atual, seta no vizinho de onde o pacote veio)
_INPUT_ARROWS = {
    MPSoCConfig.EAST0: (MPSoCConfig.EAST_IN_HIGH, MPSoCConfig.WEST_OUT_HIGH),
    MPSoCConfig.EAST1: (MPSoCConfig.EAST_IN_LOW, MPSoCConfig.WEST_OUT_LOW),
    MPSoCConfig.NORTH0: (MPSoCConfig.NORTH_IN_HIGH, MPSoCConfig.SOUTH_OUT_HIGH),
    MPSoCConfig.NORTH1: (MPSoCConfig.NORTH_IN_LOW, MPSoCConfig.SOUTH_OUT_LOW),
    MPSoCConfig.WEST0: (MPSoCConfig.WEST_IN_HIGH, MPSoCConfig.EAST_OUT_HIGH),
    MPSoCConfig.WEST1: (MPSoCConfig.WEST_IN_LOW, MPSoCConfig.EAST_OUT_LOW),
    MPSoCConfig.SOUTH0: (MPSoCConfig.SOUTH_IN_HIGH, MPSoCConfig.NORTH_OUT_HIGH),
    MPSoCConfig.SOUTH1: (MPSoCConfig.SOUTH_IN_LOW, MPSoCConfig.NORTH_OUT_LOW),
}


class SimulationController(QObject):
    """Reproduz os pacotes de traffic_router.txt sobre a matriz de roteadores."""

    # Tempo (em ticks) do último pacote processado
    time_changed = Signal(int)
    # Último pacote processado (PacketInformation)
    packet_changed = Signal(object)
    # Play/stop mudou (True = rodando)
    running_changed = Signal(bool)
    # Fim do traffic_router.txt
    finished = Signal()
    # Pacote com serviço que não existe no services.cfg
    unknown_service = Signal(object)

    def __init__(self, mpsoc_config, mpsoc_information, router_matrix, parent=None):
        super().__init__(parent)
        self.mpsoc_config = mpsoc_config
        self.mpsoc_information = mpsoc_information
        self.router_matrix = router_matrix

        # Função (packet -> bool) usada pelo filtro de serviços/PEs; None = todos
        self.packet_filter = None
        self.speed = MAX_REPAINT_SPEED
        self.running = False

        # Roteadores de destino dos pacotes que saíram de um PE e ainda não
        # chegaram; enquanto houver algum, as setas pintadas não são apagadas
        self.unfinished_packets = []

        # "Print Router Total Link Usage": roteador (-1 = desligado) e o que imprimir
        self.link_usage_router = -1
        self.print_link_usage = True

        self.checkpoint = CheckpointController(mpsoc_config.clock_period_in_ns, self.checkpoint_reached)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._play_step)

    # ==========================================
    # CONTROLES
    # ==========================================
    def set_speed(self, speed):
        """Velocidade de 0 (parado) a 100 (máxima, sem redesenhar as setas)."""
        self.speed = speed
        if self.running:
            self.timer.setInterval(self._interval())

    def _interval(self):
        return max(0, 400 - self.speed * 4)

    def play(self):
        if self.running:
            return
        self.running = True
        self.timer.start(self._interval())
        self.running_changed.emit(True)

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.timer.stop()
        self.running_changed.emit(False)

    def step(self):
        """Processa um único pacote, sempre redesenhando."""
        return self.next_packet(repaint=True)

    def _play_step(self):
        if self.speed == 0:
            return

        if self.speed > MAX_REPAINT_SPEED:
            # Modo rápido: vários pacotes por passo e sem desenhar as setas
            self.unfinished_packets.clear()
            for _ in range(FAST_BATCH_SIZE):
                if self.next_packet(repaint=False) == -1 or not self.running:
                    return
        else:
            self.next_packet(repaint=True)

    def go_to_time(self, desired_time):
        """
        Volta (ou avança) a simulação até o tempo informado, em ticks.
        Só é possível ir até o último pacote já lido. Gera ValueError se o
        tempo for inválido.
        """
        packet_counter = self.mpsoc_information.get_packet_counter_by_time(desired_time)
        if packet_counter == -1:
            raise ValueError(f"Invalid time: {desired_time}")

        self.stop()
        self.mpsoc_information.initialize_pe_information()
        self.checkpoint.reset()
        self.reset_graphical_path()

        time = 0
        while packet_counter > 0:
            time = self.next_packet(packet_counter <= GO_REPAINT_LAST_PACKETS, desired_time)
            if time == -1 or time > desired_time:
                break
            packet_counter -= 1

        self.time_changed.emit(max(time, 0))

    def reset_graphical_path(self):
        self.unfinished_packets.clear()
        self.router_matrix.reset_routers()

    # ==========================================
    # PROCESSAMENTO DOS PACOTES
    # ==========================================
    def next_packet(self, repaint=True, limit_time=0):
        """Processa o próximo pacote. Retorna o tempo dele ou -1 no fim do arquivo."""
        packet = self.mpsoc_information.get_next_packet(self.packet_filter, limit_time)

        if packet is None:
            self.router_matrix.reset_routers()
            self.stop()
            self.finished.emit()
            return -1

        if packet.service not in self.mpsoc_config.services_hash:
            self.stop()
            self.unknown_service.emit(packet)

        self.checkpoint.set_time(packet.time)

        if repaint:
            self.repaint_router(packet)

        self.packet_changed.emit(packet)
        self.time_changed.emit(packet.time)
        return packet.time

    def repaint_router(self, packet):
        """Pinta o caminho do pacote: seta de entrada no roteador e de saída no vizinho."""
        router = self.router_matrix.get_router_by_address(packet.router_address)
        if router is None:
            return

        port = packet.input_port
        neighbors = self.mpsoc_information.neighbors
        address = packet.router_address

        if port in _INPUT_ARROWS:
            local_arrow, neighbor_arrow = _INPUT_ARROWS[port]

            if port in (MPSoCConfig.NORTH0, MPSoCConfig.NORTH1):
                neighbor_address = neighbors.get_vizinho_cima(address)
            elif port in (MPSoCConfig.SOUTH0, MPSoCConfig.SOUTH1):
                neighbor_address = neighbors.get_vizinho_baixo(address)
            elif port in (MPSoCConfig.EAST0, MPSoCConfig.EAST1):
                neighbor_address = neighbors.get_vizinho_direita(address)
            else:
                neighbor_address = neighbors.get_vizinho_esquerda(address)

            neighbor = self.router_matrix.get_router_by_address(neighbor_address)
            if neighbor is not None:
                neighbor.paint_arrow(neighbor_arrow)

        elif port in (MPSoCConfig.LOCAL0, MPSoCConfig.LOCAL1):
            # Pacote novo saindo do PE: apaga o caminho anterior se nenhum
            # outro pacote estiver em trânsito
            if not self.unfinished_packets:
                self.router_matrix.reset_routers()

            local_arrow = MPSoCConfig.LOCAL_IN

            # Destinos fora da malha (ex.: periféricos) nunca "chegam", então não são aguardados
            if 0 <= packet.target_router < self.mpsoc_config.get_pe_number():
                self.unfinished_packets.append(packet.target_router)
        else:
            return

        router.paint_arrow(local_arrow)

        # Pacote chegou ao destino
        if address == packet.target_router:
            router.paint_arrow(MPSoCConfig.LOCAL_OUT)
            if address in self.unfinished_packets:
                self.unfinished_packets.remove(address)

    # ==========================================
    # TAXA DE USO DOS ENLACES
    # ==========================================
    def checkpoint_reached(self):
        """Atualiza o percentual de uso dos enlaces de todos os roteadores."""
        max_throughput_per_window = self.checkpoint.get_window_size_in_ns() / self.mpsoc_config.clock_period_in_ns

        for address in range(self.mpsoc_config.get_pe_number()):
            router_info = self.mpsoc_information.get_router_information(address)
            self.update_router_throughput(address, router_info, max_throughput_per_window)

    def update_router_throughput(self, address, router_info, max_throughput):
        router = self.router_matrix.get_router_by_address(address)
        if router is None or router_info is None:
            return

        neighbors = self.mpsoc_information.neighbors
        percent = 100.0 / max_throughput

        # Só as portas que possuem vizinho, mais as portas locais
        ports = []
        if neighbors.get_x_coordinate(address) != 0:
            ports += [MPSoCConfig.WEST0, MPSoCConfig.WEST1]
        if neighbors.get_x_coordinate(address) != self.mpsoc_config.mpsoc_x - 1:
            ports += [MPSoCConfig.EAST0, MPSoCConfig.EAST1]
        if neighbors.get_y_coordinate(address) != 0:
            ports += [MPSoCConfig.SOUTH0, MPSoCConfig.SOUTH1]
        if neighbors.get_y_coordinate(address) != self.mpsoc_config.mpsoc_y - 1:
            ports += [MPSoCConfig.NORTH0, MPSoCConfig.NORTH1]
        ports += [MPSoCConfig.LOCAL0, MPSoCConfig.LOCAL1]

        total_link_usage = 0.0
        for port in ports:
            usage = router_info.get_port_bandwidth_throughput_in_cycles(port) * percent
            router.update_throughput(port, usage)
            if port not in (MPSoCConfig.LOCAL0, MPSoCConfig.LOCAL1):
                total_link_usage += usage

        if address == self.link_usage_router:
            # Mesma saída do Java: um valor por checkpoint, com vírgula decimal
            value = total_link_usage if self.print_link_usage else self.checkpoint.current_time_ms
            print(f"{value:.6g}".replace(".", ","), flush=True)

        router_info.reset_bandwidth_throughput()
        router_info.reset_throughput()
