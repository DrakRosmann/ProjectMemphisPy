import os

class MPSoCConfig(object):

    debugFile = ""
    ##
    routerAddressing = 0
    mpsoc_x = 0
    mpsoc_y = 0
    cluster_x = 0
    cluster_y = 0
    managerPositionX = 0
    managerPositionY = 0
    global_position_x = 0
    global_position_y = 0
    globalManagerCluster = 0
    flitSize = 0
    clockPeriodInNs = 0
    channel_number = 0


    #Const:
    HAMILTONIAN = 0
    XY = 1

    def __init__(self, debugFile):
        self.debugFile = debugFile

        config_path = debugFile

        self.debug_dir_path = debugFile

        with open(config_path, "r") as platform_file:
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

                    #case "BEGIN_task_name_relation":
                        # Em Python, o iterador do arquivo é passado para continuar a leitura de onde parou
                        #self.initialize_task_naming(platform_file)

                    case "channel_number":
                        self.channel_number = int(config_info[1])

                    case _:
                        # Equivalente ao 'default' do switch
                        pass


