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
    EAST_IN_HIGH = 0
    EAST_OUT_HIGH = 1
    WEAST_IN_HIGH = 2
    WEAST_OUT_HIGH = 3
    NORTH_IN_HIGH = 4
    NORTH_OUT_HIGH = 5
    SOUTH_IN_HIGH = 6
    SOUTH_OUT_HIGH = 7
    EAST_IN_LOW = 8
    EAST_OUT_LOW = 9
    WEAST_IN_LOW = 10
    WEAST_OUT_LOW = 11
    NORTH_IN_LOW = 12
    NORTH_OUT_LOW = 13
    SOUTH_IN_LOW = 14
    SOUTH_OUT_LOW = 15
    LOCAL_IN = 16
    LOCAL_OUT = 17

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

                        #self.initialize_task_naming(platform_file)

                    case "channel_number":
                        self.channel_number = int(config_info[1])

                    case _:
                        pass


