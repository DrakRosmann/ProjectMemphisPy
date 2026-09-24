from dataclasses import dataclass, field

from util.MPSoCConfig import MPSoCConfig


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
