"""
Modelo de dados do tráfego da NoC lido de traffic_router.txt.

Refatoração em Python das classes do pacote "source" do GraphicalDebugger
original em Java (MPSoCInformation, RouterInformation, PacketInformation,
TaskInformation, PortInformation, RouterNeighbors e ReadTrafficData).
"""

import os
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field

from MPSoCConfig import MPSoCConfig


class RouterNeighbors:
    """
    Calcula os vizinhos de um roteador a partir do seu endereço hamiltoniano.
    Os métodos retornam -1 quando o vizinho não existe (borda da malha).
    """

    def __init__(self, x_dimension, y_dimension):
        self.x_dimension = x_dimension
        self.y_dimension = y_dimension

    @classmethod
    def from_config(cls, mpsoc_config):
        return cls(mpsoc_config.mpsoc_x, mpsoc_config.mpsoc_y)

    def xy_to_ham_addr(self, xy_addr):
        xy_addr &= 0xFFFF  # limpa o header
        y = xy_addr & 0xFF
        x = xy_addr >> 8

        if y % 2 == 1:
            return (y * self.x_dimension) + (self.x_dimension - x) - 1
        return (y * self.x_dimension) + x

    def ham_to_xy_addr(self, ham_addr):
        ham_addr &= 0xFF  # limpa o header
        y, addr = divmod(ham_addr, self.x_dimension)

        x = self.x_dimension - addr - 1 if y % 2 == 1 else addr
        return (x << 8) | y

    def xy_address_to_xy_label(self, ham_addr):
        xy_addr = self.ham_to_xy_addr(ham_addr)
        return f"{xy_addr >> 8}{xy_addr & 0xFF}"

    def get_x_coordinate(self, ham_addr):
        return self.ham_to_xy_addr(ham_addr) >> 8

    def get_y_coordinate(self, ham_addr):
        return self.ham_to_xy_addr(ham_addr) & 0xFF

    def _neighbor(self, ham_addr, dx, dy):
        x = self.get_x_coordinate(ham_addr) + dx
        y = self.get_y_coordinate(ham_addr) + dy

        if 0 <= x < self.x_dimension and 0 <= y < self.y_dimension:
            return self.xy_to_ham_addr((x << 8) | y)
        return -1

    def get_vizinho_cima(self, ham_addr):
        return self._neighbor(ham_addr, 0, 1)

    def get_vizinho_baixo(self, ham_addr):
        return self._neighbor(ham_addr, 0, -1)

    def get_vizinho_esquerda(self, ham_addr):
        return self._neighbor(ham_addr, -1, 0)

    def get_vizinho_direita(self, ham_addr):
        return self._neighbor(ham_addr, 1, 0)


@dataclass
class PacketInformation:
    """Um pacote registrado em traffic_router.txt ao passar por um roteador."""

    router_address: int
    time: int
    service: int
    size: int
    bandwidth_cycles: int
    input_port: int
    target_router: int
    task_source: int = -1
    task_target: int = -1
    channel: int = field(init=False)

    def __post_init__(self):
        # O canal é definido pela porta de entrada (portas pares = HIGH)
        self.channel = MPSoCConfig.get_channel(self.input_port)

    def get_input_port_string(self):
        return MPSoCConfig.get_port_string(self.input_port)

    def get_channel_string(self):
        return "HIGH" if self.channel == MPSoCConfig.HIGH else "LOW"

    def print_packet(self):
        print("*********PACKET************")
        print(f"router_address: {self.router_address}")
        print(f"time: {self.time}")
        print(f"service: {self.service}")
        print(f"size: {self.size}")
        print(f"bandwidth cycles: {self.bandwidth_cycles}")
        print(f"channel: {self.get_channel_string()}")
        print(f"input_port: {self.get_input_port_string()}")
        print(f"target_router: {self.target_router}")
        print(f"task_source: {self.task_source}")
        print(f"task_target: {self.task_target}")


@dataclass
class TaskInformation:
    """Um evento de tarefa (alocação, término, mensagem) ocorrido em um PE."""

    id: int
    service: str
    time: int
    remote_task_id: int = -1

    @property
    def task_id(self):
        # Os 8 bits menos significativos identificam a tarefa dentro da aplicação
        return self.id & 0xFF

    @property
    def app_id(self):
        return self.id >> 8


class PortInformation:
    """Volume e largura de banda acumulados em uma porta de um roteador."""

    def __init__(self, mpsoc_config, channel):
        self.channel = channel
        self.total_volume = 0
        self.total_bandwidth = 0
        self.throughput = 0
        self.bandwidth_throughput = 0

        # Serviços desconhecidos começam em zero em vez de gerar erro
        self.service_volume = defaultdict(int, dict.fromkeys(mpsoc_config.service_reference, 0))
        self.service_bandwidth = defaultdict(int, dict.fromkeys(mpsoc_config.service_reference, 0))

    def add_new_information(self, packet):
        volume = packet.size + 1  # +1 por causa do header

        self.total_volume += volume
        self.throughput += volume

        self.total_bandwidth += packet.bandwidth_cycles
        self.bandwidth_throughput += packet.bandwidth_cycles

        self.service_volume[packet.service] += volume
        self.service_bandwidth[packet.service] += packet.bandwidth_cycles

    def get_service_volume_in_flits(self, service):
        return self.service_volume.get(service, 0)

    def get_service_bandwidth_in_cycles(self, service):
        return self.service_bandwidth.get(service, 0)

    def reset_port_throughput(self):
        self.throughput = 0

    def reset_port_bandwidth_throughput(self):
        self.bandwidth_throughput = 0


class RouterInformation:
    """Pacotes, portas e eventos de tarefa acumulados em um roteador (PE)."""

    def __init__(self, mpsoc_config, router_address):
        self.router_address = router_address
        self.mpsoc_config = mpsoc_config
        self.task_counter = 0
        self.packets = []
        self.tasks = []
        self.port_informations = [
            PortInformation(mpsoc_config, MPSoCConfig.get_channel(port))
            for port in range(MPSoCConfig.NPORT)
        ]

    def add_packet(self, packet):
        self.packets.append(packet)
        self.port_informations[packet.input_port].add_new_information(packet)
        self._update_task_information(packet)

    def _update_task_information(self, packet):
        config = self.mpsoc_config

        # Pacote está entrando no PE
        if packet.target_router == self.router_address:
            if packet.service in config.task_allocation_services:
                self.task_counter += 1
                self.tasks.append(TaskInformation(packet.task_source, "ALLOCATED", packet.time))
            elif packet.service == config.get_service_value("MESSAGE_DELIVERY"):
                self.tasks.append(TaskInformation(packet.task_target, "MESSAGE_DELIVERY",
                                                  packet.time, packet.task_source))

        # Pacote está saindo do PE
        elif packet.input_port in (MPSoCConfig.LOCAL0, MPSoCConfig.LOCAL1):
            if packet.service in config.task_terminated_services:
                # No Memphis-V a tarefa terminada vem no último campo (task_source = -1);
                # no formato do HeMPS, usado pelo Java, vinha no penúltimo
                task_id = packet.task_source if packet.task_source >= 0 else packet.task_target
                self.tasks.append(TaskInformation(task_id, "TERMINATED", packet.time))
            elif packet.service == config.get_service_value("MESSAGE_REQUEST"):
                self.tasks.append(TaskInformation(packet.task_target, "MESSAGE_REQUEST",
                                                  packet.time, packet.task_source))

    def get_tasks_information(self):
        return self.tasks

    def get_task_number(self):
        return self.task_counter

    # ==========================================
    # TOTAIS DO ROTEADOR (SOMA DE TODAS AS PORTAS)
    # ==========================================
    def get_router_total_throughput_in_flits(self):
        return sum(port.throughput for port in self.port_informations)

    def get_router_total_bandwidth_throughput_in_cycles(self):
        return sum(port.bandwidth_throughput for port in self.port_informations)

    def get_router_total_volume_in_flits(self):
        return sum(port.total_volume for port in self.port_informations)

    def get_router_total_bandwidth_in_cycles(self):
        return sum(port.total_bandwidth for port in self.port_informations)

    def get_router_total_services_volume_in_flits(self, services):
        return sum(self.get_port_volume_in_flits(port, services) for port in range(MPSoCConfig.NPORT))

    def get_router_total_services_bandwidth_in_cycles(self, services):
        return sum(self.get_port_bandwidth_in_cycles(port, services) for port in range(MPSoCConfig.NPORT))

    # ==========================================
    # INFORMAÇÕES POR PORTA
    # ==========================================
    def get_port_total_volume_in_flits(self, port):
        return self.port_informations[port].total_volume

    def get_port_total_bandwidth_in_cycles(self, port):
        return self.port_informations[port].total_bandwidth

    def get_port_volume_in_flits(self, port, services):
        port_info = self.port_informations[port]
        return sum(port_info.get_service_volume_in_flits(service) for service in services)

    def get_port_bandwidth_in_cycles(self, port, services):
        port_info = self.port_informations[port]
        return sum(port_info.get_service_bandwidth_in_cycles(service) for service in services)

    def get_port_throughput_in_flits(self, port):
        return self.port_informations[port].throughput

    def get_port_bandwidth_throughput_in_cycles(self, port):
        return self.port_informations[port].bandwidth_throughput

    def reset_throughput(self):
        for port in self.port_informations:
            port.reset_port_throughput()

    def reset_bandwidth_throughput(self):
        for port in self.port_informations:
            port.reset_port_bandwidth_throughput()


class ReadTrafficData:
    """
    Lê os pacotes de traffic_router.txt sob demanda.

    Os pacotes já lidos ficam em all_packets, assim é possível voltar no tempo
    (reset_packet_counter) sem precisar reler o arquivo.
    """

    def __init__(self, mpsoc_config, neighbors):
        self.mpsoc_config = mpsoc_config
        self.neighbors = neighbors
        self.packet_read_control = 0
        self.all_packets = []
        # Arquivo ainda sendo gravado pelo simulador: uma linha sem "\n" no
        # fim está incompleta e só é lida quando terminar de ser gravada
        self.follow = False

        traffic_path = os.path.join(mpsoc_config.debug_file_path, "traffic_router.txt")
        # Gera FileNotFoundError caso o arquivo não exista
        self.traffic = open(traffic_path, "r", encoding="utf-8")

    def close(self):
        self.traffic.close()

    def reset_packet_counter(self):
        self.packet_read_control = 0

    def get_packet_counter_by_time(self, time):
        """Retorna quantos pacotes já lidos ocorreram até o tempo informado (-1 se fora do intervalo)."""
        if not self.all_packets or time < 0 or self.all_packets[-1].time < time:
            return -1

        return bisect_right(self.all_packets, time, key=lambda packet: packet.time)

    def get_next_packet(self):
        # Ainda não lido: busca a próxima linha válida do arquivo
        if self.packet_read_control == len(self.all_packets):
            while True:
                # tell() em arquivo texto é lento: só é preciso para desfazer uma linha incompleta
                position = self.traffic.tell() if self.follow else None
                line = self.traffic.readline()
                if not line:
                    return None               # fim do arquivo (por enquanto, no modo follow)
                if self.follow and not line.endswith("\n"):
                    self.traffic.seek(position)
                    return None
                packet = self._parse_packet(line)
                if packet is not None:
                    self.all_packets.append(packet)
                    self.packet_read_control += 1
                    return packet

        packet = self.all_packets[self.packet_read_control]
        self.packet_read_control += 1
        return packet

    def _parse_packet(self, line):
        fields = line.strip().split("\t")
        if fields == [""]:
            return None

        try:
            time = int(fields[0])
            router_address = self._extract_router_address(fields[1])
            service = int(fields[2])
            size = int(fields[3])
            bandwidth_cycles = int(fields[4])

            if self.mpsoc_config.channel_number == 1:
                # Suporte a canal físico duplicado
                input_port = int(fields[5]) * 2 + 1
            else:
                input_port = int(fields[5])

            target_router = self._extract_router_address(fields[6])
            task_source = int(fields[7]) if len(fields) > 7 else -1
            task_target = int(fields[8]) if len(fields) > 8 else -1
        except (ValueError, IndexError):
            print(f"WARNING: Wrong packet format in traffic_router.txt: {line.strip()}")
            return None

        return PacketInformation(router_address, time, service, size, bandwidth_cycles,
                                 input_port, target_router, task_source, task_target)

    def _extract_router_address(self, value):
        address = int(value)
        if self.mpsoc_config.router_addressing == MPSoCConfig.XY:
            return self.neighbors.xy_to_ham_addr(address)
        return address


class MPSoCInformation:
    """Estado de todos os roteadores do MPSoC, alimentado pelos pacotes de traffic_router.txt."""

    def __init__(self, mpsoc_config):
        self.mpsoc_config = mpsoc_config
        self.initialize_pe_information()
        self.neighbors = RouterNeighbors.from_config(mpsoc_config)
        self.read_traffic = ReadTrafficData(mpsoc_config, self.neighbors)

    def initialize_pe_information(self):
        self.pe_information = {
            address: RouterInformation(self.mpsoc_config, address)
            for address in range(self.mpsoc_config.get_pe_number())
        }

    def close(self):
        self.read_traffic.close()

    def get_packet_counter_by_time(self, time):
        """Retorna o número de pacotes até chegar no tempo desejado."""
        counter = self.read_traffic.get_packet_counter_by_time(time)

        if counter != -1:
            self.read_traffic.reset_packet_counter()

        return counter

    def get_router_information(self, router_address):
        return self.pe_information.get(router_address)

    def get_router_information_xy(self, x, y):
        return self.get_router_information(self.neighbors.xy_to_ham_addr((x << 8) | y))

    # ==========================================
    # TOTAIS DA NOC
    # ==========================================
    def get_total_noc_volume(self):
        return sum(router.get_router_total_volume_in_flits() for router in self.pe_information.values())

    def get_total_noc_bandwidth(self):
        return sum(router.get_router_total_bandwidth_in_cycles() for router in self.pe_information.values())

    def get_total_noc_service_volume(self, services):
        return sum(router.get_router_total_services_volume_in_flits(services)
                   for router in self.pe_information.values())

    def get_total_noc_service_bandwidth(self, services):
        return sum(router.get_router_total_services_bandwidth_in_cycles(services)
                   for router in self.pe_information.values())

    def get_next_packet(self, packet_filter=None, limit_time=0):
        """
        Lê o próximo pacote e o registra no roteador em que foi capturado.

        packet_filter é uma função (packet -> bool); pacotes rejeitados são
        pulados enquanto estiverem antes de limit_time (0 = sem limite).
        Retorna None quando não há mais pacotes.
        """
        while True:
            packet = self.read_traffic.get_next_packet()

            if packet is None:
                return None

            # Serviços desconhecidos são repassados sem atualizar os roteadores
            if packet.service not in self.mpsoc_config.services_hash:
                return packet

            if packet_filter is not None and not packet_filter(packet):
                if limit_time == 0 or limit_time > packet.time:
                    continue

            router = self.pe_information.get(packet.router_address)
            if router is not None:
                router.add_packet(packet)

            return packet
