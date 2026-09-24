from collections import defaultdict


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
