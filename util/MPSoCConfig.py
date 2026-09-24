from sortedcontainers import SortedDict


class MPSoCConfig:
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
        self.channel_number = 0

        self.services_hash = SortedDict()
        self.task_name_hash = SortedDict()

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
        """Lê os serviços (nome e código hexadecimal) do arquivo services.cfg."""
        self.services_hash = SortedDict()

        try:
            with open(services_file_path, "r", encoding="utf-8") as services_file:
                for line in services_file:
                    service_info = line.strip().split()

                    # Ignora linhas vazias e as definições especiais iniciadas com "$"
                    if len(service_info) < 2 or service_info[0].startswith("$"):
                        continue

                    try:
                        service_id = int(service_info[1], 16)
                    except ValueError:
                        # Ignora caso o código não seja um hexadecimal válido
                        continue

                    self.services_hash[service_id] = service_info[0]
        except FileNotFoundError:
            print("Erro")

    # Métodos de acesso necessários para compatibilidade com sua interface gráfica
    def get_task_name_hash(self):
        return self.task_name_hash

    def get_services_hash(self):
        return self.services_hash
