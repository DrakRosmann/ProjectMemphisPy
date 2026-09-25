"""
Análises sobre o tráfego e os logs, inspiradas nas métricas do artigo do
Memphis (Ruaro et al., DAES 2019, Seções 3.4, 5 e 6):

  - aplicação de cada pacote (filtro por aplicação)
  - latência de cada mensagem: da injeção na NoC até a entrega no destino
  - vazão em Mbps e taxa de injeção (% da capacidade do enlace)
  - linha do tempo da admissão de cada aplicação

Não depende de Qt, para poder ser testado sem interface.
"""

import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from util.MPSoCConfig import MPSoCConfig

# ID usado para "tarefa" do kernel/injetor nos campos de tarefa do traffic_router.txt
KERNEL_TASK_ID = 0xFFFF

LOCAL_PORTS = (MPSoCConfig.LOCAL0, MPSoCConfig.LOCAL1)

# Lado de onde o pacote chega em cada porta de entrada: (dx, dy) do vizinho
_PORT_SIDE = {
    MPSoCConfig.EAST0: (1, 0), MPSoCConfig.EAST1: (1, 0),
    MPSoCConfig.WEST0: (-1, 0), MPSoCConfig.WEST1: (-1, 0),
    MPSoCConfig.NORTH0: (0, 1), MPSoCConfig.NORTH1: (0, 1),
    MPSoCConfig.SOUTH0: (0, -1), MPSoCConfig.SOUTH1: (0, -1),
}


# ==========================================
# APLICAÇÕES
# ==========================================
def known_app_ids(mpsoc_config):
    """IDs de aplicação conhecidos (platform.cfg); vazio = aceitar qualquer um."""
    ids = set(mpsoc_config.app_name_hash)
    ids.update(task_id >> 8 for task_id in mpsoc_config.task_name_hash)
    return ids


def app_label(mpsoc_config, app_id):
    name = mpsoc_config.app_name_hash.get(app_id)
    return f"{app_id} - {name}" if name else f"App {app_id}"


def task_app(task_id, known_apps=None):
    """Aplicação dona da tarefa, ou None para campo vazio/kernel/ID desconhecido."""
    if task_id is None or task_id < 0 or task_id >= KERNEL_TASK_ID:
        return None
    app = task_id >> 8
    if known_apps and app not in known_apps:
        return None
    return app


def packet_apps(packet, known_apps=None):
    """Aplicações envolvidas no pacote (pela tarefa de origem e/ou de destino)."""
    apps = {task_app(packet.task_source, known_apps), task_app(packet.task_target, known_apps)}
    apps.discard(None)
    return apps


# ==========================================
# GEOMETRIA
# ==========================================
def xy(mpsoc_config, address):
    xy_address = mpsoc_config.ham_to_xy_addr(address)
    return xy_address >> 8, xy_address & 0xFF


def hops(mpsoc_config, source, target):
    (sx, sy), (tx, ty) = xy(mpsoc_config, source), xy(mpsoc_config, target)
    return abs(sx - tx) + abs(sy - ty)


def is_peripheral_input(mpsoc_config, router, port):
    """Porta de borda sem roteador vizinho: o pacote veio de um periférico."""
    side = _PORT_SIDE.get(port)
    if side is None:
        return False
    x, y = xy(mpsoc_config, router)
    nx, ny = x + side[0], y + side[1]
    return not (0 <= nx < mpsoc_config.mpsoc_x and 0 <= ny < mpsoc_config.mpsoc_y)


def _came_from(mpsoc_config, source, target, port):
    """Com roteamento XY, o pacote de source chega em target por esta porta?"""
    side = _PORT_SIDE.get(port)
    if side is None:
        return source == target
    (sx, sy), (tx, ty) = xy(mpsoc_config, source), xy(mpsoc_config, target)
    if sy == ty:                      # mesma linha: chega pelo lado de X
        return side[1] == 0 and (sx - tx) * side[0] > 0
    return side[0] == 0 and (sy - ty) * side[1] > 0


def median(values):
    """Mediana (robusta às poucas latências distorcidas por registros faltando no trace)."""
    ordered = sorted(values)
    if not ordered:
        return 0
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def link_capacity_mbps(mpsoc_config):
    """Um flit por ciclo: flit_size bits a cada clock_period ns."""
    if not mpsoc_config.clock_period_in_ns:
        return 0.0
    return mpsoc_config.flit_size * 1000.0 / mpsoc_config.clock_period_in_ns


def mbps(mpsoc_config, flits, cycles):
    """Vazão média de `flits` transmitidos em `cycles` ciclos."""
    if cycles <= 0 or not mpsoc_config.clock_period_in_ns:
        return 0.0
    return flits * mpsoc_config.flit_size * 1000.0 / (cycles * mpsoc_config.clock_period_in_ns)


def neighbor(mpsoc_config, address, port):
    """Roteador vizinho do lado da porta de entrada (None na borda ou porta local)."""
    side = _PORT_SIDE.get(port)
    if side is None:
        return None
    x, y = xy(mpsoc_config, address)
    nx, ny = x + side[0], y + side[1]
    if 0 <= nx < mpsoc_config.mpsoc_x and 0 <= ny < mpsoc_config.mpsoc_y:
        return mpsoc_config.xy_to_ham_addr((nx << 8) | ny)
    return None


def next_hop(mpsoc_config, address, target):
    """Próximo roteador pelo roteamento XY (primeiro X, depois Y); None se já chegou."""
    (x, y), (tx, ty) = xy(mpsoc_config, address), xy(mpsoc_config, target)
    if x != tx:
        x += 1 if tx > x else -1
    elif y != ty:
        y += 1 if ty > y else -1
    else:
        return None
    return mpsoc_config.xy_to_ham_addr((x << 8) | y)


def xy_consistent(mpsoc_config, address, port, target):
    """
    Um pacote que entrou em `address` pela porta `port` indo para `target`
    está de acordo com o roteamento XY? (Andando em X, o destino tem que
    estar à frente em X; andando em Y, já tem que estar na coluna certa.)
    """
    side = _PORT_SIDE.get(port)
    if side is None:
        return True
    (x, y), (tx, ty) = xy(mpsoc_config, address), xy(mpsoc_config, target)
    dx, dy = -side[0], -side[1]       # sentido do movimento
    if dy == 0:
        return (tx - x) * dx >= 0
    return tx == x and (ty - y) * dy >= 0


# ==========================================
# RASTREAMENTO DOS PACOTES (LATÊNCIA E ROTEAMENTO)
# ==========================================
@dataclass
class Message:
    source: int              # roteador de origem
    target: int
    service: int
    flits: int               # payload + header
    injected: int            # tick em que o header entrou na NoC
    delivered: int = -1      # tick em que o último flit saiu do roteador de destino
    task_source: int = -1
    task_target: int = -1
    from_peripheral: bool = False
    apps: frozenset = frozenset()
    hops: int = 0
    # Último roteador em que o pacote foi visto (para achar pacotes parados)
    last_router: int = -1
    last_time: int = -1
    prev_router: int = -1    # roteador anterior ao último (-1 = ainda na origem)
    hops_seen: int = 0
    # Registros do caminho: (roteador, porta de entrada, tick), a partir da injeção
    path: list = field(default_factory=list)

    @property
    def latency(self):
        return self.delivered - self.injected if self.delivered >= 0 else -1


@dataclass
class RoutingViolation:
    """Registro em que o pacote entrou por uma porta incompatível com o XY."""
    time: int
    router: int
    port: int
    target: int
    service: int
    task_source: int = -1
    task_target: int = -1
    message: "Message" = None     # pacote ao qual o registro pertence, se identificado


class TrafficTracker:
    """
    Acompanha cada pacote do traffic_router.txt pela NoC.

    - Injeção: entrada pela porta local ou por um periférico na borda.
    - Cada registro seguinte (um por roteador do caminho) é associado ao
      pacote em trânsito com o mesmo serviço e tamanho visto mais
      recentemente no roteador vizinho do lado da porta de entrada.
    - Chegada: registro em que roteador == destino. Dá a latência.
    - Todo registro intermediário é conferido contra o roteamento XY.

    O traffic_router.txt não tem ID de pacote, e os campos de tarefa podem
    mudar entre os hops de um mesmo pacote; por isso o casamento usa só
    serviço, tamanho, o roteador vizinho e o tempo. Quando o trace omite
    registros, a chegada é casada com a injeção mais recente cuja origem
    seja compatível com a porta de entrada; injeções mais antigas do mesmo
    fluxo que ficaram para trás são contadas como sem entrega registrada.
    """

    MAX_VIOLATIONS = 5000    # guardadas para a tabela (as contagens não têm limite)

    def __init__(self, mpsoc_config):
        self.mpsoc_config = mpsoc_config
        self.known_apps = known_app_ids(mpsoc_config)
        self.reset()

    def reset(self):
        self.messages = []           # na ordem de injeção
        self._pending = defaultdict(list)
        self.lost = 0                # injeções sem chegada registrada
        self.consumed = 0            # pacotes do traffic_router.txt já analisados
        self.hop_records = Counter()         # serviço -> registros intermediários conferidos
        self.hop_violations = Counter()      # serviço -> registros fora do XY
        self.violations = []

    @staticmethod
    def _key(packet):
        # Sem as tarefas: no Memphis-V os campos de tarefa podem mudar de um
        # hop para outro do mesmo pacote (valem os da injeção)
        return packet.service, packet.size

    def consume(self, packet):
        self.consumed += 1
        config = self.mpsoc_config
        router = packet.router_address

        injected_locally = packet.input_port in LOCAL_PORTS
        from_peripheral = not injected_locally and is_peripheral_input(config, router, packet.input_port)

        if not 0 <= packet.target_router < config.get_pe_number():
            # Destino fora da malha: não é um pacote na NoC (ex.: TASK_TERMINATED
            # de tamanho 0 e destino -1 registrado pelo kernel na porta local)
            return

        if injected_locally or from_peripheral:
            message = Message(router, packet.target_router, packet.service, packet.size + 1,
                              packet.time, task_source=packet.task_source, task_target=packet.task_target,
                              from_peripheral=from_peripheral,
                              apps=frozenset(packet_apps(packet, self.known_apps)),
                              last_router=router, last_time=packet.time,
                              path=[(router, packet.input_port, packet.time)])
            self.messages.append(message)
            if router == packet.target_router:
                # Destino é o próprio roteador: entra e sai no mesmo registro
                message.delivered = packet.time + packet.bandwidth_cycles
            else:
                self._pending[self._key(packet)].append(message)
            return

        violation = self._check_routing(packet)

        candidates = self._pending.get(self._key(packet))
        if not candidates:
            return

        # Pacote em trânsito visto por último no vizinho de onde este veio
        previous = neighbor(config, router, packet.input_port)
        match = None
        for message in candidates:
            if message.last_router == previous and message.last_time <= packet.time:
                if match is None or message.last_time > match.last_time:
                    match = message
        if match is not None:
            match.prev_router = match.last_router
            match.last_router = router
            match.last_time = packet.time
            match.hops_seen += 1
            match.path.append((router, packet.input_port, packet.time))
            if violation is not None:
                violation.message = match

        if router != packet.target_router:
            return

        if match is None:
            # Faltaram registros no caminho: casa pela origem compatível com a porta
            for message in reversed(candidates):
                if message.injected <= packet.time and _came_from(config, message.source, router,
                                                                   packet.input_port):
                    match = message
                    break
            if match is None:
                return

        # Mensagens do mesmo fluxo chegam em ordem: as anteriores não foram registradas
        stale = [message for message in candidates
                 if message.source == match.source and message.injected < match.injected]
        for message in stale:
            candidates.remove(message)
        self.lost += len(stale)
        candidates.remove(match)

        match.target = router
        match.hops = hops(config, match.source, router)
        match.last_router, match.last_time = router, packet.time
        match.delivered = packet.time + packet.bandwidth_cycles

    def _check_routing(self, packet):
        """Confere o registro contra o XY; retorna a violação guardada, se houver."""
        self.hop_records[packet.service] += 1
        if xy_consistent(self.mpsoc_config, packet.router_address, packet.input_port, packet.target_router):
            return None
        self.hop_violations[packet.service] += 1
        if len(self.violations) >= self.MAX_VIOLATIONS:
            return None
        violation = RoutingViolation(packet.time, packet.router_address, packet.input_port,
                                     packet.target_router, packet.service, packet.task_source, packet.task_target)
        self.violations.append(violation)
        return violation

    def delivered(self):
        return [message for message in self.messages if message.delivered >= 0]

    def in_flight(self):
        """Injetadas que ainda podem chegar (sem contar as dadas como perdidas)."""
        return [message for queue in self._pending.values() for message in queue]

    def pending_count(self):
        return sum(len(queue) for queue in self._pending.values())


def read_all_packets(mpsoc_config):
    """Todos os pacotes do traffic_router.txt, com um leitor próprio (não mexe na simulação)."""
    from information.read_traffic_data import ReadTrafficData
    from information.router_neighbors import RouterNeighbors

    reader = ReadTrafficData(mpsoc_config, RouterNeighbors.from_config(mpsoc_config))
    packets = []
    try:
        while (packet := reader.get_next_packet()) is not None:
            packets.append(packet)
    finally:
        reader.close()
    return packets


def track_all(mpsoc_config, packets):
    tracker = TrafficTracker(mpsoc_config)
    for packet in packets:
        tracker.consume(packet)
    return tracker


# Um pacote que acabou de chegar gera a interrupção logo depois: os pacotes
# entregues um pouco antes do início do trecho também são listados
SLICE_LOOKBACK = 100


def messages_in_slice(messages, pe, start, finish, lookback=SLICE_LOOKBACK):
    """
    Pacotes de um PE durante um trecho do escalonamento: [(mensagem, "received" | "sent")],
    em ordem de tempo. Recebidos: entregues ao PE entre start - lookback e finish.
    Enviados: injetados pelo PE entre start e finish.
    """
    result = []
    for message in messages:
        if message.target == pe and message.delivered >= 0 and start - lookback <= message.delivered <= finish:
            result.append((message.delivered, message, "received"))
        if message.source == pe and not message.from_peripheral and start <= message.injected <= finish:
            result.append((message.injected, message, "sent"))
    result.sort(key=lambda item: item[0])
    return [(message, direction) for _time, message, direction in result]


# ==========================================
# VALIDAÇÃO DO ROTEAMENTO E DEADLOCK
# ==========================================
# Um serviço com pelo menos esta fração de registros fora do XY não é uma
# falha pontual: é tráfego que não usa XY (ex.: inundação da rede de
# broadcast de gerência, no canal LOW do Memphis-V)
NON_XY_RATIO = 0.3
NON_XY_MIN_RECORDS = 3


def routing_summary(tracker):
    """
    Retorna (serviços não-XY {serviço: (fora do XY, total)}, violações
    pontuais dos demais serviços).
    """
    non_xy = {service: (count, tracker.hop_records[service])
              for service, count in tracker.hop_violations.items()
              if count >= NON_XY_MIN_RECORDS and count / tracker.hop_records[service] >= NON_XY_RATIO}
    anomalies = [violation for violation in tracker.violations if violation.service not in non_xy]
    return non_xy, anomalies


def blocked_messages(tracker, now, threshold):
    """Pacotes em trânsito sem avançar há pelo menos `threshold` ciclos, do mais antigo ao mais novo."""
    stuck = [message for message in tracker.in_flight() if now - message.last_time >= threshold]
    stuck.sort(key=lambda message: message.last_time)
    return stuck


def _held_link(message):
    """Enlace ocupado pelo header: (roteador anterior, roteador atual)."""
    return (message.prev_router if message.hops_seen else "PE", message.last_router)


def _wanted_link(mpsoc_config, message):
    """Próximo enlace que o pacote precisa, pelo XY."""
    following = next_hop(mpsoc_config, message.last_router, message.target)
    return (message.last_router, following if following is not None else "PE")


def find_wait_cycles(mpsoc_config, messages):
    """
    Espera circular entre pacotes parados: A espera o enlace que B ocupa,
    B espera o de C, ..., até voltar a A. Com roteamento XY isso não deveria
    acontecer; um ciclo indica deadlock. Retorna listas de mensagens.
    """
    holders = defaultdict(list)
    for message in messages:
        holders[_held_link(message)].append(message)

    waits = {id(message): holders.get(_wanted_link(mpsoc_config, message), []) for message in messages}
    by_id = {id(message): message for message in messages}

    cycles, seen = [], set()
    for start in messages:
        path, index = [], {}
        current = start
        while current is not None and id(current) not in seen:
            if id(current) in index:
                cycle = path[index[id(current)]:]
                cycles.append(cycle)
                break
            index[id(current)] = len(path)
            path.append(current)
            blockers = waits.get(id(current), [])
            current = by_id.get(id(blockers[0])) if blockers else None
        seen.update(id(message) for message in path)
    return cycles


@dataclass
class AppTraffic:
    app: int
    messages: int = 0
    flits: int = 0
    first_injection: int = -1
    last_delivery: int = -1
    latency_sum: int = 0
    latency_max: int = 0
    hops_sum: int = 0
    latencies: list = field(default_factory=list)

    @property
    def active_cycles(self):
        return self.last_delivery - self.first_injection if self.messages else 0

    @property
    def average_latency(self):
        return self.latency_sum / self.messages if self.messages else 0.0

    @property
    def median_latency(self):
        return median(self.latencies)

    @property
    def average_hops(self):
        return self.hops_sum / self.messages if self.messages else 0.0


def traffic_by_app(messages):
    """Totais por aplicação sobre as mensagens entregues."""
    stats = {}
    for message in messages:
        if message.delivered < 0:
            continue
        for app in message.apps:
            entry = stats.setdefault(app, AppTraffic(app))
            entry.messages += 1
            entry.flits += message.flits
            if entry.first_injection < 0 or message.injected < entry.first_injection:
                entry.first_injection = message.injected
            entry.last_delivery = max(entry.last_delivery, message.delivered)
            entry.latency_sum += message.latency
            entry.latency_max = max(entry.latency_max, message.latency)
            entry.hops_sum += message.hops
            entry.latencies.append(message.latency)
    return stats


# ==========================================
# LINHA DO TEMPO DA ADMISSÃO DE APLICAÇÕES
# ==========================================
@dataclass
class AppTimeline:
    """
    Etapas do protocolo de admissão (Seção 3.4 do artigo) de uma aplicação.
    Tempos em ticks; -1 = etapa não encontrada.
    """
    app: int
    name: str = ""
    task_count: int = 0
    received: int = -1         # mapper recebeu o pedido (NEW APP)
    requester: str = ""
    mapped: int = -1           # mapeamento concluído
    started: int = -1          # TASK_RELEASE enviado: aplicação liberada para executar
    terminated: int = -1
    task_allocated: dict = field(default_factory=dict)    # tarefa -> (tick, PE) da chegada do código
    task_terminated: dict = field(default_factory=dict)   # tarefa -> tick
    task_confirmed: set = field(default_factory=set)      # TASK_ALLOCATED recebidos pelo mapper

    @property
    def first_allocation(self):
        return min((time for time, _pe in self.task_allocated.values()), default=-1)

    @property
    def last_allocation(self):
        return max((time for time, _pe in self.task_allocated.values()), default=-1)

    @property
    def last_termination(self):
        return max(self.task_terminated.values(), default=-1)

    @property
    def end(self):
        return self.terminated if self.terminated >= 0 else self.last_termination

    @property
    def start(self):
        return self.started if self.started >= 0 else self.last_allocation

    @property
    def admission_cycles(self):
        """Do pedido até a liberação (o artigo cita ~40 mil ciclos para o MPEG)."""
        begin = self.received if self.received >= 0 else self.first_allocation
        return self.start - begin if begin >= 0 and self.start >= 0 else -1

    @property
    def mapping_cycles(self):
        return self.mapped - self.received if self.received >= 0 and self.mapped >= 0 else -1

    @property
    def execution_cycles(self):
        return self.end - self.start if self.start >= 0 and self.end >= 0 else -1

    @property
    def first_event(self):
        times = [t for t in (self.received, self.mapped, self.started, self.first_allocation) if t >= 0]
        return min(times, default=-1)


# Mensagens do mapper_task no log do processador (prefixo $$$_<PE>_<app>_<task>_)
_NEW_APP = re.compile(r"New app received at (\d+) from (\w+) with (\d+) tasks")
_MAPPED = re.compile(r"Mapped with score .*? at (\d+)")
_TASK_ALLOCATED = re.compile(r"Received task allocated from id (\d+)")
_RELEASE = re.compile(r"Sending TASK_RELEASE for app (\d+)")
_STARTED = re.compile(r"App (\d+) started at (\d+)")
_TERMINATED = re.compile(r"App (\d+) terminated at time (\d+)")


def _log_dir(mpsoc_config):
    testcase = mpsoc_config.get_testcase_path() or os.path.dirname(os.path.normpath(mpsoc_config.debug_file_path))
    return os.path.join(testcase, "log")


def read_mapper_log(mpsoc_config, timelines):
    """
    Completa as linhas do tempo com o log do mapper_task. Retorna o caminho
    do log usado, ou None se nenhum log tiver mensagens do mapper.
    """
    log_dir = _log_dir(mpsoc_config)
    try:
        names = sorted(name for name in os.listdir(log_dir) if name.endswith(".txt"))
    except OSError:
        return None

    for name in names:
        path = os.path.join(log_dir, name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as log_file:
                lines = [line for line in log_file if "New app received" in line or "App " in line
                         or "Mapped with" in line or "task allocated" in line or "TASK_RELEASE for app" in line]
        except OSError:
            continue
        if not any(_NEW_APP.search(line) for line in lines):
            continue

        # O pedido ainda não tem ID de aplicação: ele só aparece no TASK_RELEASE
        pending = None
        for line in lines:
            if match := _NEW_APP.search(line):
                pending = {"received": int(match[1]), "requester": match[2], "tasks": int(match[3]),
                           "mapped": -1, "confirmed": set()}
            elif (match := _MAPPED.search(line)) and pending is not None:
                pending["mapped"] = int(match[1])
            elif (match := _TASK_ALLOCATED.search(line)) and pending is not None:
                pending["confirmed"].add(int(match[1]))
            elif match := _RELEASE.search(line):
                timeline = timelines.setdefault(int(match[1]), AppTimeline(int(match[1])))
                if pending is not None:
                    timeline.received = pending["received"]
                    timeline.requester = pending["requester"]
                    timeline.task_count = pending["tasks"]
                    timeline.mapped = pending["mapped"]
                    timeline.task_confirmed = pending["confirmed"]
                    pending = None
            elif match := _STARTED.search(line):
                timelines.setdefault(int(match[1]), AppTimeline(int(match[1]))).started = int(match[2])
            elif match := _TERMINATED.search(line):
                timelines.setdefault(int(match[1]), AppTimeline(int(match[1]))).terminated = int(match[2])
        return path
    return None


def build_timelines(mpsoc_config, packets):
    """
    Linha do tempo de cada aplicação a partir de todos os pacotes do
    traffic_router.txt (chegada do código das tarefas e término) e do log
    do mapper_task (pedido, mapeamento, liberação e término da aplicação).

    Retorna (timelines ordenadas por ID, caminho do log do mapper ou None).
    """
    known_apps = known_app_ids(mpsoc_config)
    timelines = {}

    for packet in packets:
        if packet.router_address != packet.target_router:
            continue
        # Tarefa chegando ao PE de destino (mesma regra do RouterInformation)
        if packet.service in mpsoc_config.task_allocation_services:
            app = task_app(packet.task_source, known_apps)
            if app is not None:
                timeline = timelines.setdefault(app, AppTimeline(app))
                timeline.task_allocated.setdefault(
                    packet.task_source, (packet.time + packet.bandwidth_cycles, packet.router_address))

    for packet in packets:
        if packet.input_port in LOCAL_PORTS and packet.service in mpsoc_config.task_terminated_services:
            task = packet.task_source if packet.task_source >= 0 else packet.task_target
            app = task_app(task, known_apps)
            if app is not None:
                timelines.setdefault(app, AppTimeline(app)).task_terminated.setdefault(task, packet.time)

    log_path = read_mapper_log(mpsoc_config, timelines)

    for app, timeline in timelines.items():
        timeline.name = mpsoc_config.app_name_hash.get(app, "")
        if not timeline.task_count:
            timeline.task_count = len(timeline.task_allocated)
    return [timelines[app] for app in sorted(timelines)], log_path
