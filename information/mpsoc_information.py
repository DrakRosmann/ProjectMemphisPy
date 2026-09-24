from information.read_traffic_data import ReadTrafficData
from information.router_information import RouterInformation
from information.router_neighbors import RouterNeighbors


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
