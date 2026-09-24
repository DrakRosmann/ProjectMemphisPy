import os

from sortedcontainers import SortedDict


class MPSoCConfig:
    # Portas físicas do roteador (índice da porta no traffic_router.txt)
    EAST0 = 0
    EAST1 = 1
    WEST0 = 2
    WEST1 = 3
    NORTH0 = 4
    NORTH1 = 5
    SOUTH0 = 6
    SOUTH1 = 7
    LOCAL0 = 8
    LOCAL1 = 9

    NPORT = 10

    PORT_NAMES = ("EAST 0", "EAST 1", "WEST 0", "WEST 1", "NORTH 0",
                  "NORTH 1", "SOUTH 0", "SOUTH 1", "LOCAL 0", "LOCAL 1")

    # Canais
    LOW = 0x100
    HIGH = 0

    # Tipos de PE
    GLOBAL_MASTER = 0
    CLUSTER_MASTER = 1
    SLAVE = 2

    # Constantes de Direção (Variáveis de Classe)
    EAST_IN_HIGH = 0
    EAST_OUT_HIGH = 1
    WEST_IN_HIGH = 2
    WEST_OUT_HIGH = 3
    NORTH_IN_HIGH = 4
    NORTH_OUT_HIGH = 5
    SOUTH_IN_HIGH = 6
    SOUTH_OUT_HIGH = 7
    EAST_IN_LOW = 8
    EAST_OUT_LOW = 9
    WEST_IN_LOW = 10
    WEST_OUT_LOW = 11
    NORTH_IN_LOW = 12
    NORTH_OUT_LOW = 13
    SOUTH_IN_LOW = 14
    SOUTH_OUT_LOW = 15
    LOCAL_IN = 16
    LOCAL_OUT = 17

    # Constantes de Roteamento
    HAMILTONIAN = 0
    XY = 1

    def __init__(self, debug_file_path):
        self.debug_file_path = debug_file_path

        # Inicializando variáveis de instância padrão
        self.router_addressing = 0
        self.mpsoc_x = 0
        self.mpsoc_y = 0
        self.cluster_x = 0
        self.cluster_y = 0
        self.manager_position_x = 0
        self.manager_position_y = 0
        self.global_position_x = 0
        self.global_position_y = 0
        self.global_manager_cluster = 0
        self.flit_size = 0
        self.clock_period_in_ns = 0
        self.channel_number = 2

        self.services_hash = SortedDict()
        self.task_name_hash = SortedDict()
        self.service_reference = []
        self.task_allocation_services = []
        self.task_terminated_services = []

        # Abre o arquivo em modo leitura de texto garantindo o encoding UTF-8
        try:
            with open(debug_file_path+"/platform.cfg", "r", encoding="utf-8") as platform_file:
                for line in platform_file:
                    config_info = line.strip().split()

                    if not config_info:
                        continue

                    match config_info[0]:
                        case "router_addressing":
                            if config_info[1].upper() == "XY":
                                self.router_addressing = self.XY
                            else:
                                self.router_addressing = self.HAMILTONIAN
                        case "mpsoc_x":
                            self.mpsoc_x = int(config_info[1])
                        case "mpsoc_y":
                            self.mpsoc_y = int(config_info[1])
                        case "cluster_x":
                            self.cluster_x = int(config_info[1])
                        case "cluster_y":
                            self.cluster_y = int(config_info[1])
                        case "manager_position_x":
                            self.manager_position_x = int(config_info[1])
                        case "manager_position_y":
                            self.manager_position_y = int(config_info[1])
                        case "global_manager_cluster":
                            self.global_manager_cluster = int(config_info[1])
                        case "flit_size":
                            self.flit_size = int(config_info[1])
                        case "clock_period_ns":
                            self.clock_period_in_ns = int(config_info[1])
                        case "channel_number":
                            self.channel_number = int(config_info[1])
                        case "BEGIN_task_name_relation":
                            # Passamos o OBJETO do arquivo, não a string do caminho
                            self.initialize_task_naming(platform_file)
                        case _:
                            pass
        except FileNotFoundError:
            print("Erro")

        self.discovery_global_xy_position()
        self.initialize_services(debug_file_path + "/services.cfg")

    def initialize_task_naming(self, platform_file):
        """Lê as tarefas diretamente do objeto de arquivo aberto."""
        self.task_name_hash = SortedDict()

        # Continua iterando sobre as linhas do MESMO arquivo aberto no __init__
        for line in platform_file:
            line = line.strip()

            if line == "END_task_name_relation":
                break  # Sai do loop e devolve o controle para o __init__

            if line == "":
                continue

            task_name_id = line.split(" ")

            if len(task_name_id) >= 2:
                task_name = task_name_id[0]
                try:
                    task_id = int(task_name_id[1])
                    self.task_name_hash[task_id] = task_name
                except ValueError:
                    # Ignora caso o ID não seja um número válido
                    continue


    def initialize_services(self, services_file_path):
        """Lê os serviços (nome e código decimal) do arquivo services.cfg."""
        self.services_hash = SortedDict()
        self.task_allocation_services = []
        self.task_terminated_services = []

        try:
            with open(services_file_path, "r", encoding="utf-8") as services_file:
                for line in services_file:
                    service_info = line.strip().split()

                    if len(service_info) < 2:
                        continue

                    try:
                        values = [int(value) for value in service_info[1:]]
                    except ValueError:
                        # Ignora caso o código não seja um número válido
                        continue

                    # Linhas especiais com a lista de serviços de alocação/término de tarefa
                    match service_info[0]:
                        case "$TASK_ALLOCATION_SERVICE":
                            self.task_allocation_services.extend(values)
                        case "$TASK_TERMINATED_SERVICE":
                            self.task_terminated_services.extend(values)
                        case _:
                            self.services_hash[values[0]] = service_info[0]
        except FileNotFoundError:
            print("Erro")

        self.service_reference = list(self.services_hash.keys())

    def discovery_global_xy_position(self):
        """Descobre a posição XY do gerente global a partir do cluster configurado."""
        if self.cluster_x == 0 or self.mpsoc_x == 0:
            return

        cluster_master = self.global_manager_cluster + 1
        x_master = 0
        y_master = 0

        while cluster_master > 0:
            if self.mpsoc_x % (cluster_master * self.cluster_x) == 0:
                x_master = cluster_master - 1
            else:
                y_master += 1
            cluster_master -= self.mpsoc_x // self.cluster_x

        self.global_position_x = x_master * self.cluster_x + self.manager_position_x
        self.global_position_y = y_master * self.cluster_y + self.manager_position_y

    # ==========================================
    # PORTAS E CANAIS
    # ==========================================
    @staticmethod
    def get_channel(port):
        """Portas pares (EAST0, WEST0, NORTH0, SOUTH0, LOCAL0) são do canal HIGH."""
        return MPSoCConfig.HIGH if port % 2 == 0 else MPSoCConfig.LOW

    @staticmethod
    def get_port_string(port):
        if 0 <= port < MPSoCConfig.NPORT:
            return MPSoCConfig.PORT_NAMES[port]
        return None

    # ==========================================
    # SERVIÇOS
    # ==========================================
    def get_string_service_name(self, service):
        return self.services_hash.get(service, "---")

    def get_service_value(self, name):
        for service_value, service_name in self.services_hash.items():
            if service_name == name:
                return service_value
        return -1

    # ==========================================
    # ENDEREÇAMENTO (XY <-> HAMILTONIANO)
    # ==========================================
    def xy_to_ham_addr(self, xy_addr):
        xy_addr &= 0xFFFF  # limpa o header
        y = xy_addr & 0xFF
        x = xy_addr >> 8

        if y % 2 == 1:
            return (y * self.mpsoc_x) + (self.mpsoc_x - x) - 1
        return (y * self.mpsoc_x) + x

    def ham_to_xy_addr(self, ham_addr):
        ham_addr &= 0xFF  # limpa o header
        y, addr = divmod(ham_addr, self.mpsoc_x)

        x = self.mpsoc_x - addr - 1 if y % 2 == 1 else addr
        return (x << 8) | y

    def ham_address_to_xy_label(self, ham_addr):
        xy_addr = self.ham_to_xy_addr(ham_addr)
        return f"{xy_addr >> 8}x{xy_addr & 0xFF}"

    def xy_label_to_ham_address(self, xy_label):
        x, y = (int(value) for value in xy_label.split("x"))
        return self.xy_to_ham_addr((x << 8) | y)

    def get_pe_type(self, ham_addr):
        xy_addr = self.ham_to_xy_addr(ham_addr)
        x = xy_addr >> 8
        y = xy_addr & 0xFF

        if x < self.manager_position_x or y < self.manager_position_y:
            return self.SLAVE

        if x == self.global_position_x and y == self.global_position_y:
            return self.GLOBAL_MASTER

        if ((x - self.manager_position_x) % self.cluster_x == 0
                and (y - self.manager_position_y) % self.cluster_y == 0):
            return self.CLUSTER_MASTER

        return self.SLAVE

    # ==========================================
    # PLATAFORMA
    # ==========================================
    def get_pe_number(self):
        return self.mpsoc_x * self.mpsoc_y

    def get_testcase_path(self):
        """Pasta do cenário: a que contém o diretório de debug (e o log/)."""
        debug_dir = os.path.normpath(self.debug_file_path)
        if os.path.basename(debug_dir) != "debug":
            return None
        return os.path.dirname(debug_dir)

    def get_frequency_in_hz(self):
        return 1_000_000_000 // self.clock_period_in_ns

    def get_frequency_in_khz(self):
        return self.get_frequency_in_hz() // 1000

    def get_frequency_in_mhz(self):
        return self.get_frequency_in_hz() // 1_000_000

    def get_link_bandwidth_in_mbps(self):
        return self.get_frequency_in_hz() * self.flit_size // 1_000_000

    # Métodos de acesso necessários para compatibilidade com sua interface gráfica
    def get_task_name_hash(self):
        return self.task_name_hash

    def get_services_hash(self):
        return self.services_hash
