"""Leitura do traffic_router.txt e estado dos roteadores."""

from information import MPSoCInformation
from util.MPSoCConfig import MPSoCConfig


def test_all_packets_read(packets):
    assert len(packets) == 3101
    # O arquivo não está estritamente em ordem de tempo: a linha de um pacote
    # longo pode ser gravada depois de registros mais novos
    out_of_order = sum(a.time > b.time for a, b in zip(packets, packets[1:]))
    assert 0 < out_of_order < len(packets) * 0.05


def run_all(config, packet_filter=None):
    information = MPSoCInformation(config)
    try:
        while information.get_next_packet(packet_filter) is not None:
            pass
        return information
    finally:
        information.close()


def test_router_volumes(config):
    information = run_all(config)
    assert information.get_router_information(0).get_router_total_volume_in_flits() == 6864
    assert information.get_total_noc_volume() > 0


def test_terminated_tasks_have_real_ids(config):
    # No Memphis-V a tarefa terminada vem no último campo (task_source = -1)
    information = run_all(config)
    terminated = sorted(task.id for address in range(config.get_pe_number())
                        for task in information.get_router_information(address).get_tasks_information()
                        if task.service == "TERMINATED")
    assert terminated == [1, 2, 256, 257, 258, 259, 512, 513, 768, 769]


def test_packet_filter_skips_packets(config):
    information = run_all(config, lambda packet: packet.router_address == 0)
    assert information.get_router_information(4).get_router_total_volume_in_flits() == 0
    assert information.get_router_information(0).get_router_total_volume_in_flits() == 6864


def test_go_back_in_time(config):
    information = MPSoCInformation(config)
    try:
        for _ in range(100):
            information.get_next_packet()
        time = information.read_traffic.all_packets[49].time
        counter = information.get_packet_counter_by_time(time)
        assert counter >= 50
        assert information.get_packet_counter_by_time(10 ** 12) == -1
    finally:
        information.close()


def test_port_names():
    assert MPSoCConfig.get_port_string(MPSoCConfig.LOCAL1) == "LOCAL 1"
    assert MPSoCConfig.get_port_string(99) is None


def test_follow_reads_lines_as_they_are_written(tmp_path, debug_dir):
    import shutil

    from information.read_traffic_data import ReadTrafficData
    from information.router_neighbors import RouterNeighbors
    from util.MPSoCConfig import MPSoCConfig

    debug = tmp_path / "debug"
    shutil.copytree(debug_dir, debug)
    lines = (debug / "traffic_router.txt").read_text().splitlines(keepends=True)
    traffic = debug / "traffic_router.txt"
    traffic.write_text("".join(lines[:2]) + lines[2][:5])     # terceira linha pela metade

    config = MPSoCConfig(str(debug))
    reader = ReadTrafficData(config, RouterNeighbors.from_config(config))
    reader.follow = True
    try:
        assert reader.get_next_packet() is not None
        assert reader.get_next_packet() is not None
        assert reader.get_next_packet() is None               # linha incompleta: espera
        with open(traffic, "a") as traffic_file:
            traffic_file.write(lines[2][5:] + lines[3])
        assert reader.get_next_packet().time == int(lines[2].split("\t")[0])
        assert reader.get_next_packet().time == int(lines[3].split("\t")[0])
        assert reader.get_next_packet() is None
    finally:
        reader.close()
