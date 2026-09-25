import os
from bisect import bisect_right

from util.MPSoCConfig import MPSoCConfig
from information.packet_information import PacketInformation


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
