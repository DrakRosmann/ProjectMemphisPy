"""analysis.py: aplicações, roteamento XY, latência, pacotes parados, deadlock e linha do tempo."""

import pytest

import analysis
from information.packet_information import PacketInformation
from util.MPSoCConfig import MPSoCConfig

REQUEST = 41
BROADCAST = 0


@pytest.fixture
def mesh(tmp_path):
    """Plataforma sintética 3x3 XY, flits de 32 bits a 100 MHz."""
    (tmp_path / "platform.cfg").write_text(
        "router_addressing XY\nchannel_number 2\nmpsoc_x 3\nmpsoc_y 3\nflit_size 32\nclock_period_ns 10\n"
        "BEGIN_task_name_relation\ntaskA 256\ntaskB 257\nEND_task_name_relation\n"
        "BEGIN_app_name_relation\nmanagement\t0\nsynthetic\t1\nEND_app_name_relation\n")
    (tmp_path / "services.cfg").write_text("NEW_APP 0\nMESSAGE_REQUEST 41\nTASK_ALLOCATION 42\n"
                                           "$TASK_ALLOCATION_SERVICE 42\n")
    return MPSoCConfig(str(tmp_path))


def at(config, x, y):
    return config.xy_to_ham_addr((x << 8) | y)


def packet(config, time, router, port, target, service=REQUEST, size=2, bandwidth=6, source=256, target_task=257):
    return PacketInformation(at(config, *router), time, service, size, bandwidth, port,
                             at(config, *target), source, target_task)


def path_packets(config, start=100):
    """Pacote de 0x0 para 2x1 pelo XY: leste, leste, norte."""
    return [packet(config, start, (0, 0), MPSoCConfig.LOCAL0, (2, 1)),
            packet(config, start + 5, (1, 0), MPSoCConfig.WEST0, (2, 1)),
            packet(config, start + 10, (2, 0), MPSoCConfig.WEST0, (2, 1)),
            packet(config, start + 15, (2, 1), MPSoCConfig.SOUTH0, (2, 1))]


# ------------------------------------------------------------------ geometria
def test_next_hop_goes_x_first(mesh):
    assert analysis.next_hop(mesh, at(mesh, 0, 0), at(mesh, 2, 1)) == at(mesh, 1, 0)
    assert analysis.next_hop(mesh, at(mesh, 2, 0), at(mesh, 2, 1)) == at(mesh, 2, 1)
    assert analysis.next_hop(mesh, at(mesh, 2, 1), at(mesh, 2, 1)) is None


def test_neighbor_and_border(mesh):
    assert analysis.neighbor(mesh, at(mesh, 1, 0), MPSoCConfig.WEST0) == at(mesh, 0, 0)
    assert analysis.neighbor(mesh, at(mesh, 0, 0), MPSoCConfig.SOUTH0) is None
    assert analysis.is_peripheral_input(mesh, at(mesh, 0, 0), MPSoCConfig.SOUTH0)
    assert not analysis.is_peripheral_input(mesh, at(mesh, 1, 1), MPSoCConfig.SOUTH0)


@pytest.mark.parametrize("router, port, target, expected", [
    ((1, 0), MPSoCConfig.WEST0, (2, 2), True),    # andando para leste, destino à frente em X
    ((1, 0), MPSoCConfig.WEST0, (0, 2), False),   # andando para leste, destino atrás
    ((2, 1), MPSoCConfig.SOUTH0, (2, 2), True),   # andando para norte na coluna certa
    ((1, 1), MPSoCConfig.SOUTH0, (2, 2), False),  # andando em Y antes de terminar o X
])
def test_xy_consistent(mesh, router, port, target, expected):
    assert analysis.xy_consistent(mesh, at(mesh, *router), port, at(mesh, *target)) is expected


def test_link_capacity_and_mbps(mesh):
    assert analysis.link_capacity_mbps(mesh) == 3200.0
    assert analysis.mbps(mesh, 100, 100) == 3200.0   # 1 flit por ciclo = capacidade total
    assert analysis.mbps(mesh, 10, 0) == 0.0


# ---------------------------------------------------------------- aplicações
def test_packet_apps_ignore_kernel_and_unknown(mesh):
    known = analysis.known_app_ids(mesh)
    assert known == {0, 1}
    assert analysis.packet_apps(packet(mesh, 0, (0, 0), 8, (1, 0), source=256, target_task=257), known) == {1}
    assert analysis.packet_apps(packet(mesh, 0, (0, 0), 8, (1, 0), source=0xFFFF, target_task=0), known) == {0}
    assert analysis.packet_apps(packet(mesh, 0, (0, 0), 8, (1, 0), source=-1, target_task=5000), known) == set()
    assert analysis.app_label(mesh, 1) == "1 - synthetic"


# --------------------------------------------------------- latência e caminho
def test_task_fields_may_change_between_hops(mesh):
    tracker = analysis.TrafficTracker(mesh)
    records = path_packets(mesh)
    records[3].task_source, records[3].task_target = 0xFFFF, 0   # como no trace do Memphis-V
    for record in records:
        tracker.consume(record)
    [message] = tracker.delivered()
    assert message.hops_seen == 3
    assert message.apps == {1}                  # vale a tarefa da injeção


def test_ignores_records_outside_the_mesh(mesh):
    tracker = analysis.TrafficTracker(mesh)
    record = packet(mesh, 10, (1, 1), MPSoCConfig.LOCAL0, (0, 0), size=0, bandwidth=0)
    record.target_router = 512
    tracker.consume(record)
    assert tracker.messages == []


def test_tracks_packet_hop_by_hop(mesh):
    tracker = analysis.TrafficTracker(mesh)
    for record in path_packets(mesh):
        tracker.consume(record)

    [message] = tracker.delivered()
    assert message.latency == 15 + 6          # chegada do header + ciclos até o último flit sair
    assert message.hops == 3
    assert message.hops_seen == 3
    assert message.apps == {1}
    assert tracker.pending_count() == 0
    assert analysis.routing_summary(tracker) == ({}, [])


def test_path_is_recorded(mesh):
    tracker = analysis.TrafficTracker(mesh)
    for record in path_packets(mesh):
        tracker.consume(record)
    [message] = tracker.delivered()
    assert [(router, port) for router, port, _time in message.path] == [
        (at(mesh, 0, 0), MPSoCConfig.LOCAL0), (at(mesh, 1, 0), MPSoCConfig.WEST0),
        (at(mesh, 2, 0), MPSoCConfig.WEST0), (at(mesh, 2, 1), MPSoCConfig.SOUTH0)]


def test_violation_points_to_its_packet(mesh):
    tracker = analysis.TrafficTracker(mesh)
    # Sai de 1x0 para 2x2 mas sobe antes de terminar o X: 1x0 -> 1x1 (errado) -> 2x1 -> 2x2
    records = [packet(mesh, 10, (1, 0), MPSoCConfig.LOCAL0, (2, 2)),
               packet(mesh, 12, (1, 1), MPSoCConfig.SOUTH0, (2, 2)),
               packet(mesh, 14, (2, 1), MPSoCConfig.WEST0, (2, 2)),
               packet(mesh, 16, (2, 2), MPSoCConfig.SOUTH0, (2, 2))]
    for record in records:
        tracker.consume(record)
    _non_xy, [violation] = analysis.routing_summary(tracker)
    assert violation.router == at(mesh, 1, 1)
    assert violation.message is tracker.messages[0]
    assert tracker.messages[0].hops_seen == 3


def test_messages_in_slice(mesh):
    tracker = analysis.TrafficTracker(mesh)
    for record in path_packets(mesh, start=100):      # entregue em 2x1 no tick 121
        tracker.consume(record)
    target, source = at(mesh, 2, 1), at(mesh, 0, 0)
    [(message, direction)] = analysis.messages_in_slice(tracker.messages, target, 150, 300)
    assert direction == "received"                    # 29 ciclos antes do trecho
    assert analysis.messages_in_slice(tracker.messages, target, 300, 400) == []
    assert analysis.messages_in_slice(tracker.messages, source, 90, 110)[0][1] == "sent"


def test_same_router_delivery(mesh):
    tracker = analysis.TrafficTracker(mesh)
    tracker.consume(packet(mesh, 50, (1, 1), MPSoCConfig.LOCAL0, (1, 1), bandwidth=4))
    [message] = tracker.delivered()
    assert (message.latency, message.hops) == (4, 0)


def test_missing_intermediate_records_still_match(mesh):
    tracker = analysis.TrafficTracker(mesh)
    records = path_packets(mesh)
    for record in (records[0], records[3]):      # só injeção e chegada
        tracker.consume(record)
    [message] = tracker.delivered()
    assert message.latency == 21
    assert message.hops_seen == 0


def test_traffic_by_app(mesh):
    tracker = analysis.TrafficTracker(mesh)
    for start in (100, 1000):
        for record in path_packets(mesh, start):
            tracker.consume(record)
    stats = analysis.traffic_by_app(tracker.delivered())[1]
    assert stats.messages == 2
    assert stats.flits == 6
    assert stats.active_cycles == 1021 - 100
    assert stats.median_latency == 21


# ------------------------------------------------------------------ roteamento
def test_detects_xy_violation(mesh):
    tracker = analysis.TrafficTracker(mesh)
    for record in path_packets(mesh):
        tracker.consume(record)
    # Andando para o norte em 1x1, mas o destino está em outra coluna
    tracker.consume(packet(mesh, 200, (1, 1), MPSoCConfig.SOUTH0, (2, 2)))
    non_xy, anomalies = analysis.routing_summary(tracker)
    assert non_xy == {}
    assert [(violation.time, violation.router) for violation in anomalies] == [(200, at(mesh, 1, 1))]


def test_broadcast_service_is_not_reported_as_violation(mesh):
    tracker = analysis.TrafficTracker(mesh)
    # Inundação a partir de 0x0: aparece em roteadores fora do caminho XY até 0x1
    for time, router, port in ((10, (1, 0), MPSoCConfig.WEST1), (12, (2, 0), MPSoCConfig.WEST1),
                               (14, (1, 1), MPSoCConfig.SOUTH1), (16, (2, 1), MPSoCConfig.SOUTH1)):
        tracker.consume(packet(mesh, time, router, port, (0, 1), service=BROADCAST, source=-1, target_task=-1))
    non_xy, anomalies = analysis.routing_summary(tracker)
    assert BROADCAST in non_xy
    assert anomalies == []


# -------------------------------------------------------- parados e deadlock
def test_blocked_packets(mesh):
    tracker = analysis.TrafficTracker(mesh)
    records = path_packets(mesh)
    tracker.consume(records[0])
    tracker.consume(records[1])                  # parou em 1x0
    [blocked] = analysis.blocked_messages(tracker, now=20_000, threshold=10_000)
    assert blocked.last_router == at(mesh, 1, 0)
    assert blocked.hops_seen == 1
    assert analysis.blocked_messages(tracker, now=200, threshold=10_000) == []


def test_circular_wait_is_found(mesh):
    corners = [(0, 0), (1, 0), (1, 1), (0, 1)]    # cada pacote quer o enlace que o seguinte ocupa
    messages = []
    for index, corner in enumerate(corners):
        previous = corners[index - 1]
        following = corners[(index + 1) % 4]
        messages.append(analysis.Message(at(mesh, *previous), at(mesh, *following), REQUEST, 3, 0,
                                         last_router=at(mesh, *corner), last_time=0,
                                         prev_router=at(mesh, *previous), hops_seen=1))
    cycles = analysis.find_wait_cycles(mesh, messages)
    assert len(cycles) == 1
    assert len(cycles[0]) == 4


def test_no_cycle_for_independent_packets(mesh):
    tracker = analysis.TrafficTracker(mesh)
    tracker.consume(path_packets(mesh)[0])
    blocked = analysis.blocked_messages(tracker, now=50_000, threshold=1)
    assert analysis.find_wait_cycles(mesh, blocked) == []


# ------------------------------------------------------------ cenário exemplo
def test_example_routing_is_xy(config, packets):
    tracker = analysis.TrafficTracker(config)
    for record in packets:
        tracker.consume(record)
    non_xy, anomalies = analysis.routing_summary(tracker)
    assert anomalies == []
    names = {config.get_string_service_name(service) for service in non_xy}
    assert names == {"NEW_APP", "APP_ALLOCATION_REQUEST", "APP_MAPPING_COMPLETE", "ABORT_TASK"}


def test_example_latency(config, packets):
    tracker = analysis.TrafficTracker(config)
    for record in packets:
        tracker.consume(record)
    delivered = tracker.delivered()
    assert len(tracker.messages) == 1388          # 1398 injeções menos 10 registros sem destino na malha
    assert len(delivered) == 1388
    assert tracker.lost == 0
    assert analysis.median([message.latency for message in delivered]) < 50
    # O maior é o código da tarefa mais longa (TASK_ALLOCATION de 2907 flits de payload)
    assert max(message.latency for message in delivered) == 13483
    # Todos os pacotes com hops foram seguidos roteador a roteador
    multi_hop = [message for message in delivered if message.hops > 0]
    assert all(message.hops_seen == message.hops for message in multi_hop)
    assert analysis.blocked_messages(tracker, packets[-1].time, 10_000) == []


def test_example_timeline(config, packets):
    timelines, log_path = analysis.build_timelines(config, packets)
    assert log_path.endswith("log0x0.txt")
    by_app = {timeline.app: timeline for timeline in timelines}
    assert sorted(by_app) == [0, 1, 2, 3]

    synthetic = by_app[1]
    assert synthetic.name == "synthetic_default"
    assert synthetic.task_count == 4
    assert (synthetic.received, synthetic.mapped, synthetic.started, synthetic.terminated) == \
        (132778, 164297, 240840, 6037445)
    assert synthetic.admission_cycles == 240840 - 132778
    assert sorted(synthetic.task_allocated) == [256, 257, 258, 259]
    assert sorted(synthetic.task_terminated) == [256, 257, 258, 259]


def test_timeline_without_log(mesh):
    records = [PacketInformation(at(mesh, 1, 0), 10, 42, 100, 50, MPSoCConfig.SOUTH0, at(mesh, 1, 0), 256, -1)]
    timelines, log_path = analysis.build_timelines(mesh, records)
    assert log_path is None
    [timeline] = timelines
    assert timeline.task_allocated == {256: (60, at(mesh, 1, 0))}
    assert timeline.admission_cycles == 0
