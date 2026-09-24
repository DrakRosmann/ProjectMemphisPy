from util.MPSoCConfig import MPSoCConfig
from information.port_information import PortInformation
from information.task_information import TaskInformation


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
                self.tasks.append(TaskInformation(packet.task_source, "TERMINATED", packet.time))
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
