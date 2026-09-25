# Implementações — Memphis-V Graphical Debugger (Python)

Este documento descreve as funcionalidades portadas do [GraphicalDebugger original em Java](https://github.com/gaph-pucrs/GraphicalDebugger) para a versão Python/PySide6: o que cada módulo faz, como as peças se conectam e quais diferenças existem em relação ao original.

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Estrutura de arquivos](#2-estrutura-de-arquivos)
3. [Abrindo um debug](#3-abrindo-um-debug)
4. [Configuração da plataforma — `util/MPSoCConfig.py`](#4-configuração-da-plataforma--utilmpsocconfigpy)
5. [Task List e Services List](#5-task-list-e-services-list)
6. [Modelo de tráfego — pacote `information/`](#6-modelo-de-tráfego--pacote-information)
7. [Matriz de roteadores — `router_matrix.py`](#7-matriz-de-roteadores--router_matrixpy)
8. [Simulação — `simulation.py`](#8-simulação--simulationpy)
9. [Interface da simulação — `main.py`](#9-interface-da-simulação--mainpy)
10. [Communication Overview, Task Mapping e Message Log — `overview_windows.py`](#10-communication-overview-task-mapping-e-message-log--overview_windowspy)
11. [Diferenças e correções em relação ao Java](#11-diferenças-e-correções-em-relação-ao-java)
12. [Limitações e próximos passos](#12-limitações-e-próximos-passos)
13. [Como testar](#13-como-testar)

---

## 1. Visão geral

O debugger lê os arquivos que o Memphis-V gera no diretório `debug/` de um cenário e reproduz, pacote a pacote, o tráfego da NoC sobre uma grade de roteadores.

```
diretório debug/
 ├─ platform.cfg        ──►  MPSoCConfig        (dimensões, clock, tarefas)
 ├─ services.cfg        ──►  MPSoCConfig        (nomes/códigos dos serviços)
 └─ traffic_router.txt  ──►  ReadTrafficData ──► MPSoCInformation ──► SimulationController
                                                   (estado por roteador)   (play, stop, go…)
                                                                               │
                                                                               ▼
                                                                    RouterMatrixWidget
                                                                    (setas e % de uso)
```

## 2. Estrutura de arquivos

| Arquivo | Papel | Equivalente Java |
|---|---|---|
| `main.py` | Janela principal: menus, botões, tabelas, ligação com a simulação | `MainFrame.java` |
| `simulation.py` | Controle da simulação e janelas de checkpoint | `MainFrame.java` (parte de simulação), `CheckpointController.java` |
| `overview_windows.py` | Janelas Communication Overview, Task Mapping Overview e Message Log, atualizadas durante a simulação | `CommunicationOverview.java`, `TaskMappingFrame.java`, `MainFrame.showMessageList` |
| `slave_matrix.py` / `pe_matrix.py` | Células das grades das duas janelas acima | — |
| `router_info_window.py` | Janela "Router Information" (clique num roteador): abas Log, Applications, Scheduling e Traffic, janela Task Information e gráfico de escalonamento | `RouterInfoFrame.java`, `PETextLog.java`, `SchedulingTab.java`, `scheduling/SchedulingPanel.java`, `TaskInfoFrame.java` |
| `platform_setup.py` | Janela Platform Setup (menu Edit): flit size, período de clock e largura da janela de checkpoint | `PlatformSetupFrame.java` |
| `filter_window.py` | Janela Service and PE Filter (menu Filters, Ctrl+F): escolhe quais pacotes a simulação processa, por serviço (Only/Except) e por PE | `FilterForm.java` |
| `projects.py` | Projetos salvos (`.hdf`): File → Save / Open / Delete Project | `MainFrame.java` (save/open/deleteMenuItem) |
| `help_dialogs.py` | Help → About e Help → Packet Format | `util/AboutFrame.java`, `MainFrame.packetFormatMenuItemActionPerformed` |
| `deloream.py` | Deloream: leitor das mensagens `$$$` das tarefas nos logs dos processadores | `deloream/DeloreamMainFrame.java`, `deloream/TaskMessage.java` |
| `theme.py` | Paletas dos temas claro/escuro, cores da grade e preferência salva | — |
| `router_matrix.py` | Desenho da grade e de cada roteador (imagens, setas, %) | `Roteador.java`, `UJPanelImagem.java`, `MainFrame.createNoCPanel` |
| `util/MPSoCConfig.py` | Leitura de `platform.cfg` e `services.cfg`, constantes e endereçamento | `util/MPSoCConfig.java` |
| `information/packet_information.py` | Um pacote do `traffic_router.txt` | `PacketInformation.java` |
| `information/task_information.py` | Um evento de tarefa em um PE | `TaskInformation.java` |
| `information/port_information.py` | Volume/banda acumulados por porta | `PortInformation.java` |
| `information/router_information.py` | Pacotes, portas e tarefas de um roteador | `RouterInformation.java` |
| `information/router_neighbors.py` | Vizinhos e conversão XY ↔ hamiltoniano | `RouterNeighbors.java` |
| `information/read_traffic_data.py` | Leitura sob demanda do `traffic_router.txt` | `ReadTrafficData.java` |
| `information/mpsoc_information.py` | Estado de todos os roteadores do MPSoC | `MPSoCInformation.java` |
| `Roteador.py` / `ui_mainwindow.py` | Interfaces geradas a partir dos `.ui` (não editar à mão) | — |

---

## 3. Abrindo um debug

**Menu:** `File → New Debugging` (Ctrl+N) → `MinhaJanela.open_file()`

- Abre um seletor de **diretório** (não mais de arquivo `.cfg`).
- Verifica se o diretório contém os três arquivos obrigatórios, definidos em `MinhaJanela.REQUIRED_FILES`:
  - `platform.cfg`
  - `services.cfg`
  - `traffic_router.txt`
- Se faltar algum, mostra uma caixa de erro e **nada é carregado**: `filePath` não é alterado, os menus não são habilitados e a grade não é montada.
- Se estiver tudo certo:
  1. Habilita os menus de ferramentas.
  2. Cria o `MPSoCConfig` e o `MPSoCInformation` (fechando o `traffic_router.txt` do debug anterior, se houver).
  3. Monta a matriz de roteadores (`build_router_matrix`).
  4. Cria o controlador da simulação (`start_simulation`).

> No `DEBUG EXAMPLE.zip`, o diretório válido é `LOGS/example_testcase/example_scenario/debug/`. O `LOGS/example_testcase/debug/` não possui `traffic_router.txt` e é recusado.

---

## 4. Configuração da plataforma — `util/MPSoCConfig.py`

### 4.1 Leitura do `platform.cfg`

| Chave | Atributo |
|---|---|
| `router_addressing` | `router_addressing` (`XY` ou `HAMILTONIAN`) |
| `mpsoc_x`, `mpsoc_y` | Dimensão total da malha |
| `cluster_x`, `cluster_y` | Dimensão de um cluster |
| `manager_position_x`, `manager_position_y` | Posição do gerente dentro do cluster |
| `global_manager_cluster` | Cluster do gerente global |
| `flit_size` | Tamanho do flit (bits) |
| `clock_period_ns` | `clock_period_in_ns` |
| `channel_number` | Número de canais físicos (padrão **2**, igual ao Java) |
| `BEGIN_task_name_relation` … `END_task_name_relation` | `task_name_hash` (ID → nome da tarefa) |

Depois da leitura, `discovery_global_xy_position()` calcula `global_position_x/y` (posição XY do gerente global).

### 4.2 Leitura do `services.cfg`

Formato: `NOME CÓDIGO`, com código **decimal** (o mesmo valor usado na coluna de serviço do `traffic_router.txt`).

```
DATA_AV 40
MESSAGE_REQUEST 41
...
$TASK_ALLOCATION_SERVICE 42 23
$TASK_TERMINATED_SERVICE 06 23
```

| Linha | Destino |
|---|---|
| `NOME CÓDIGO` | `services_hash[código] = nome` |
| `$TASK_ALLOCATION_SERVICE …` | `task_allocation_services` (lista de códigos) |
| `$TASK_TERMINATED_SERVICE …` | `task_terminated_services` (lista de códigos) |

`service_reference` guarda a lista ordenada dos códigos conhecidos.

### 4.3 Constantes

| Grupo | Constantes |
|---|---|
| Portas físicas (índice da coluna de porta no tráfego) | `EAST0=0`, `EAST1=1`, `WEST0=2`, `WEST1=3`, `NORTH0=4`, `NORTH1=5`, `SOUTH0=6`, `SOUTH1=7`, `LOCAL0=8`, `LOCAL1=9`, `NPORT=10` |
| Canais | `HIGH=0`, `LOW=0x100` (portas pares são HIGH) |
| Tipos de PE | `GLOBAL_MASTER=0`, `CLUSTER_MASTER=1`, `SLAVE=2` |
| Setas do desenho do roteador | `EAST_IN_HIGH` … `SOUTH_OUT_LOW`, `LOCAL_IN`, `LOCAL_OUT` |
| Endereçamento | `HAMILTONIAN=0`, `XY=1` |

### 4.4 Métodos

| Método | Descrição |
|---|---|
| `get_channel(port)` | `HIGH` para portas pares, `LOW` para ímpares |
| `get_port_string(port)` | `"EAST 0"`, `"LOCAL 1"` etc. |
| `get_string_service_name(code)` | Nome do serviço ou `"---"` |
| `get_service_value(name)` | Código do serviço ou `-1` |
| `xy_to_ham_addr(xy)` / `ham_to_xy_addr(ham)` | Conversão de endereços (XY = `x << 8 \| y`) |
| `ham_address_to_xy_label(ham)` | `"1x2"` |
| `xy_label_to_ham_address("1x2")` | Endereço hamiltoniano |
| `get_pe_type(ham)` | `SLAVE`, `CLUSTER_MASTER` ou `GLOBAL_MASTER` |
| `get_pe_number()` | `mpsoc_x * mpsoc_y` |
| `get_testcase_path()` | Caminho do testcase (antes de `/debug`) |
| `get_frequency_in_hz/khz/mhz()`, `get_link_bandwidth_in_mbps()` | Derivados do clock e do flit |
| `get_task_name_hash()`, `get_services_hash()` | Acesso para a interface |

---

## 5. Task List e Services List

**Menus:** `Tools → Task List` e `Tools → Services List`

As duas janelas usam o mesmo construtor, `MinhaJanela.create_table_window(title, headers, rows)`, garantindo aparência idêntica (janela 500×500, tabela de duas colunas, fecha liberando memória).

| Janela | Colunas | Fonte dos dados | Ordenação |
|---|---|---|---|
| Current Task List | Task Name, ID | `task_name_hash` (`platform.cfg`) | ID |
| Services List | Service Name, ID | `services_hash` (`services.cfg`) | Código |

As linhas `$TASK_…` do `services.cfg` não aparecem na Services List (não são serviços, e sim listas de códigos).

---

## 6. Modelo de tráfego — pacote `information/`

### 6.1 Formato do `traffic_router.txt`

Uma linha por pacote capturado em um roteador, separada por **tabulação**:

| Coluna | Campo | Observação |
|---|---|---|
| 0 | `time` | Tempo em ticks (ciclos de clock) |
| 1 | `router_address` | Roteador onde o pacote foi capturado |
| 2 | `service` | Código do serviço (decimal) |
| 3 | `size` | Tamanho do payload em flits |
| 4 | `bandwidth_cycles` | Ciclos ocupados no enlace |
| 5 | `input_port` | Porta de entrada (0–9). Com `channel_number 1`, vira `porta * 2 + 1` |
| 6 | `target_router` | Roteador de destino |
| 7 | `task_source` | *(opcional)* Tarefa de origem |
| 8 | `task_target` | *(opcional)* Tarefa de destino |

Com `router_addressing XY`, os endereços das colunas 1 e 6 são convertidos para hamiltoniano na leitura. Todo o modelo interno trabalha com **endereços hamiltonianos**.

### 6.2 Classes

**`PacketInformation`** (dataclass) — campos acima + `channel`, calculado a partir da porta de entrada. Métodos: `get_input_port_string()`, `get_channel_string()`, `print_packet()`.

**`TaskInformation`** (dataclass) — `id`, `service` (`"ALLOCATED"`, `"TERMINATED"`, `"MESSAGE_DELIVERY"`, `"MESSAGE_REQUEST"`), `time`, `remote_task_id` (padrão `-1`). Propriedades `task_id` (`id & 0xFF`) e `app_id` (`id >> 8`).

**`PortInformation`** — acumula, por porta:
- `total_volume` (flits, `size + 1` por causa do header) e `total_bandwidth` (ciclos);
- `throughput` e `bandwidth_throughput`, zerados a cada janela de checkpoint;
- volume e banda por serviço (`get_service_volume_in_flits`, `get_service_bandwidth_in_cycles`).

**`RouterInformation`** — um roteador:
- `add_packet(packet)` guarda o pacote, atualiza a porta de entrada e os eventos de tarefa;
- eventos de tarefa:
  - pacote **chegando** ao PE (`target_router == router_address`): serviço em `task_allocation_services` → `ALLOCATED`; `MESSAGE_DELIVERY` → `MESSAGE_DELIVERY`;
  - pacote **saindo** do PE (porta `LOCAL0`/`LOCAL1`): serviço em `task_terminated_services` → `TERMINATED`; `MESSAGE_REQUEST` → `MESSAGE_REQUEST`;
- totais por roteador e por porta (volume, banda, throughput, filtrados por serviço);
- `reset_throughput()` / `reset_bandwidth_throughput()`.

**`RouterNeighbors`** — vizinhos pelo endereço hamiltoniano: `get_vizinho_cima/baixo/esquerda/direita` (retornam `-1` na borda), `get_x_coordinate`, `get_y_coordinate`, conversões XY ↔ hamiltoniano. Pode ser criado com `RouterNeighbors.from_config(mpsoc_config)`.

**`ReadTrafficData`** — lê o arquivo **sob demanda** (não carrega tudo na memória de uma vez):
- `get_next_packet()` devolve o próximo pacote; os já lidos ficam em `all_packets`, permitindo voltar no tempo sem reler o arquivo;
- `reset_packet_counter()` volta a leitura para o início de `all_packets`;
- `get_packet_counter_by_time(t)` devolve quantos pacotes já lidos têm `time <= t` (busca binária), ou `-1` se `t` estiver fora do intervalo já lido;
- linhas mal formatadas geram um `WARNING` no terminal e são ignoradas;
- `close()` fecha o arquivo.

**`MPSoCInformation`** — estado global:
- `pe_information`: um `RouterInformation` por endereço (`0 … PE-1`);
- `get_next_packet(packet_filter=None, limit_time=0)`: lê o próximo pacote e o registra no roteador. `packet_filter` é uma função `packet -> bool`; pacotes rejeitados são pulados enquanto `time < limit_time` (ou sempre, com `limit_time = 0`). Pacotes com serviço desconhecido são devolvidos sem atualizar os roteadores;
- `get_router_information(addr)`, `get_router_information_xy(x, y)`;
- totais da NoC: `get_total_noc_volume/bandwidth()`, `get_total_noc_service_volume/bandwidth(services)`;
- `get_packet_counter_by_time(t)`, `initialize_pe_information()`, `close()`.

---

## 7. Matriz de roteadores — `router_matrix.py`

### 7.1 `RouterMatrixWidget`

- Organiza `mpsoc_x × mpsoc_y` roteadores, com o roteador `0x0` no canto inferior esquerdo.
- Desenha uma borda a cada bloco `cluster_x × cluster_y` (apenas visual).
- Recebe `mpsoc_config` para calcular endereço, tipo de PE e layout de canal de cada roteador.
- `get_router(x, y)`, `get_router_by_address(ham)` e `reset_routers()` (apaga as setas vermelhas de todos os roteadores que foram pintados).

### 7.2 `RouterWidget`

Reaproveita o layout do `Roteador.py` (gerado de `Roteador.ui`) e acrescenta:

| Recurso | Descrição |
|---|---|
| Imagem do roteador | `Router.png` (slave), `Router_cluster_master.png`, `Router_master.png` (global), conforme `get_pe_type` |
| Setas | `reset_arrows()` desenha as setas cinzas apenas nos lados que têm vizinho; nas bordas elas ficam vazias |
| `paint_arrow(arrow)` | Pinta de vermelho a seta indicada (`EAST_IN_HIGH`, `LOCAL_OUT` etc.) |
| `update_throughput(port, value)` | Atualiza o rótulo de % da porta física (limitado a `99.99%`) |
| Rótulo central | `XxY` com endereçamento XY; número hamiltoniano com endereçamento HAMILTONIAN |
| Canal único | Com `channel_number 1`, reposiciona as setas LOW para o centro de cada lado |
| Clique | Emite o sinal `clicked(router_address)` ao clicar no corpo do roteador |
| Fonte dos % | Monoespaçada de 10 px, para o `00.00%` caber no rótulo mesmo sem a fonte "Andale Mono" |

As imagens (pasta `images/`) são desenhadas pelo `_ImagePainter`, um *event filter* que pinta a imagem esticada sobre os `QWidget` vazios do `.ui`, substituindo o `UJPanelImagem` do Java. As imagens ficam em cache (`_pixmap_cache`).

Os PNGs das setas não têm canal alfa (fundo branco sólido). Ao carregar, `_white_to_alpha` converte o fundo e o serrilhado da borda em transparência, mantendo a cor da seta, para que elas funcionem sobre o fundo escuro. As imagens do corpo do roteador (`Router*.png`) são usadas como estão.

As cores da grade vêm de uma única folha de estilo aplicada no `RouterMatrixWidget` (`apply_theme(dark)`): fundo da área, texto do % da porta local e borda dos clusters seguem o tema; os rótulos dentro do corpo do roteador são sempre pretos, porque o corpo tem cor clara nos dois temas.

---

## 8. Simulação — `simulation.py`

### 8.1 `SimulationController`

Reproduz os pacotes sobre a matriz. Usa um `QTimer` no lugar da `Thread` + `sleep()` do Java, pois só a thread principal do Qt pode alterar a interface.

**Sinais**

| Sinal | Quando |
|---|---|
| `time_changed(int)` | A cada pacote processado (tempo em ticks) |
| `packet_changed(object)` | A cada pacote processado |
| `running_changed(bool)` | Play/stop |
| `finished()` | Fim do `traffic_router.txt` |
| `unknown_service(object)` | Pacote com serviço fora do `services.cfg` (a simulação para) |

**Controles**

| Método | Descrição |
|---|---|
| `play()` / `stop()` | Inicia/para o timer |
| `step()` | Processa um pacote, sempre redesenhando |
| `set_speed(0–100)` | Intervalo do timer = `400 - velocidade × 4` ms. Em `0` fica parado; acima de `98` (`MAX_REPAINT_SPEED`) processa lotes de 200 pacotes (`FAST_BATCH_SIZE`) sem redesenhar as setas |
| `go_to_time(ticks)` | Zera os roteadores e reprocessa os pacotes até o tempo pedido, desenhando só os últimos 50 (`GO_REPAINT_LAST_PACKETS`). Gera `ValueError` para tempos inválidos |
| `reset_graphical_path()` | Apaga as setas vermelhas |

**Desenho do caminho (`repaint_router`)**

| Porta de entrada | Seta no roteador atual | Seta no vizinho |
|---|---|---|
| `EAST0` / `EAST1` | `EAST_IN_HIGH` / `EAST_IN_LOW` | `WEST_OUT_*` do vizinho da direita |
| `WEST0` / `WEST1` | `WEST_IN_*` | `EAST_OUT_*` do vizinho da esquerda |
| `NORTH0` / `NORTH1` | `NORTH_IN_*` | `SOUTH_OUT_*` do vizinho de cima |
| `SOUTH0` / `SOUTH1` | `SOUTH_IN_*` | `NORTH_OUT_*` do vizinho de baixo |
| `LOCAL0` / `LOCAL1` | `LOCAL_IN` (pacote saindo do PE) | — |

- Quando o pacote chega ao destino (`router_address == target_router`), pinta também `LOCAL_OUT`.
- `unfinished_packets` guarda os **destinos** dos pacotes que saíram de um PE e ainda não chegaram. Quando um novo pacote sai de um PE e essa lista está vazia, o caminho anterior é apagado. Destinos fora da malha (ex.: periféricos) não são aguardados.

**Taxa de uso dos enlaces (`checkpoint_reached`)**

A cada janela de simulação, para cada roteador e porta (lados com vizinho + locais):

```
uso (%) = ciclos ocupados na janela × 100 / (tamanho da janela em ns / clock_period_ns)
```

Depois do cálculo, o throughput das portas é zerado para a próxima janela.

### 8.2 `CheckpointController`

Divide o tempo em janelas de **0,5 ms** (`window_size_ms`). `set_time(ticks)` converte para ms usando o `clock_period_ns` e chama `checkpoint_reached` quando a janela fecha.

### 8.3 `ticks_to_ms(ticks, clock_period_ns)`

`ticks × clock_period_ns / 1.000.000`.

---

## 9. Interface da simulação — `main.py`

| Elemento | Ação | Método |
|---|---|---|
| **Simulation Control** `>\|\|` | Próximo pacote | `next_packet` |
| **Simulation Control** `>` | Play | `play_simulation` |
| **Simulation Control** `STOP` | Parar | `stop_simulation` |
| **Speed Control** | Slider 0–100 (padrão 98); velocidade no canto superior direito; tempo em **ms** (esquerda) e em **ticks** (direita) embaixo, como no original | `update_slide`, `build_speed_control`, `update_simulation_time` |
| **Back To** | Campo "Time in ticks" + botão **Go** (ou Enter) | `go_to_time` |
| **Current Packet Information** | Current, Target, Service, Size (`size \| bandwidth`) | `update_current_packet_table`, `reset_current_packet_table` |
| `File → Reset Simulation` | Recarrega o debug e volta ao início | `reset_simulation` |
| `File → Rest Graphical Path` | Apaga as setas vermelhas | `reset_graphical_path` |

**Estados dos botões** (`set_simulation_buttons`):

| Situação | `>\|\|` | `>` | `STOP` | Back To |
|---|---|---|---|---|
| Nenhum debug carregado | ✗ | ✗ | ✗ | ✗ |
| Parado | ✓ | ✓ | ✗ | ✓ |
| Rodando | ✗ | ✗ | ✓ | ✗ |

`Reset Simulation` e `Rest Graphical Path` ficam desabilitados até um debug ser carregado.

### 9.1 Reset Simulation

`reset_simulation()`:

1. Para a simulação.
2. Confere se os três arquivos obrigatórios ainda existem; se não, mostra quais faltam e mantém a simulação atual.
3. Relê `platform.cfg`, `services.cfg` e `traffic_router.txt` (alterações nos arquivos passam a valer).
4. Recria a grade (setas e % zerados) e o controlador (tempo `0.00000 ms` / `0 ticks`, tabela com `-`).
5. Limpa o campo **Back To**.
6. Mostra *"The project has been successfully loaded!"*.

### 9.2 Tema claro/escuro

**Menu:** `Edit → Dark Mode` (Ctrl+T), item marcável.

- `theme.py` define as paletas do Fusion para os dois temas, incluindo as cores de itens **desabilitados** e do texto de *placeholder* (sem elas, botões desabilitados ficavam ilegíveis no modo escuro).
- `MinhaJanela.set_dark_mode(dark)` aplica a paleta na aplicação inteira, atualiza a marcação do menu e recolore a grade (`RouterMatrixWidget.apply_theme`). Uma grade criada depois (novo debug ou reset) já nasce com o tema atual.
- A escolha é salva com `QSettings` (organização `GAPH`, aplicação `MemphisGraphicalDebugger`) e restaurada ao abrir o programa.
- As células das janelas Communication Overview e Task Mapping mantêm suas cores próprias (mapa de calor e cores das aplicações); o restante da janela segue o tema.

### 9.3 Mensagens

| Situação | Mensagem |
|---|---|
| Diretório sem os arquivos obrigatórios | Caixa de erro "Diretório invalido" |
| Tempo inválido no Back To | "Enter only numbers and valid times! It is only possible to go to a time already simulated." |
| Serviço desconhecido | "ERROR: Service \<código\> packet unidentified. Router: … Input port: …" |
| Fim do tráfego | "End of traffic_router.txt reached" na barra de status |

---

## 10. Communication Overview, Task Mapping e Message Log — `overview_windows.py`

**Menus:** `Tools → Communication Overview`, `Tools → Task Mapping Overview` e `Tools → Message Log`

As três janelas mostram o estado da simulação **até o tempo atual** e se atualizam sozinhas enquanto ela avança (play, `>||`, **Back To**).

### 10.1 Atualização durante a simulação (`_LiveOverview`)

- A janela se conecta ao sinal `time_changed` do `SimulationController` e só **marca** que os dados mudaram.
- Um `QTimer` redesenha no máximo a cada **500 ms** (`REFRESH_INTERVAL_MS`), e só se a janela estiver visível e houver mudança. Assim o modo rápido (velocidade 99–100) não é travado pelas janelas abertas. No Java era uma `Thread` com `sleep(1000)`.
- Abrir o menu de novo com a janela já aberta só a traz para frente (não cria outra).
- **New Debugging** e **Reset Simulation** chamam `set_information(...)` nas janelas abertas: elas recriam a grade e passam a seguir o novo debug/controlador.

### 10.2 Communication Overview (`CommunicationOverviewWindow`)

Mapa de calor do tráfego acumulado em cada roteador.

| Controle | Efeito |
|---|---|
| **All Services** (padrão) | Considera todos os serviços; desabilita os filtros abaixo |
| Lista de serviços | Considera só o serviço escolhido |
| **Global** | % = tráfego do serviço no roteador / tráfego do serviço em toda a NoC |
| **All traffic** | % = tráfego do serviço no roteador / todo o tráfego da NoC |
| **Router** | % = tráfego do serviço no roteador / todo o tráfego do próprio roteador |
| **Volume** (padrão) / **Bandwidth** | Mede em flits (`size + 1`) ou em ciclos de enlace |

- Cada célula mostra o tipo do PE (`Global M`, `Cluster M`, `Slave`), o rótulo do roteador, a porcentagem com 3 casas e a unidade (`flits`/`cycles`).
- Cor: mesma escala do Java, matiz HSB de `0.65` (azul, 0%) até `0` (vermelho, 100%), saturação 1 e brilho 0.8. A barra **Color Length** mostra a escala.
- **Statistics:** roteador com a maior porcentagem (**Bigger**), média entre todos os roteadores (**Average**) e roteador com a menor (**Small**).
- O fundo da célula é desenhado em `SlaveWidget.paintEvent` (trocar a folha de estilo do próprio widget não repintava o fundo).

### 10.3 Task Mapping Overview (`TaskMappingWindow`)

Tarefas de cada PE, montadas a partir dos eventos de `RouterInformation.get_tasks_information()`:

- `ALLOCATED` → **RUN**, `TERMINATED` → **TER** (vale o último evento de cada tarefa).
- Cada tarefa aparece como `nome  ID  STATUS`; o nome vem do `platform.cfg` (`BEGIN_task_name_relation`) ou, se não existir, `app  tarefa`.
- Cor por aplicação (`task_id >> 8`), sorteada com semente fixa (20, como no Java), então cada aplicação mantém a cor. O texto fica preto ou branco conforme a claridade do fundo.

| Controle | Efeito |
|---|---|
| **All tasks status** | Todas as tarefas |
| **Only Running** (padrão) | Só as que estão rodando |
| **Only Terminated** | Só as terminadas (o `.ui` repetia "All tasks status" neste botão) |
| **Updating / Update** | Ligado: atualiza sozinho. Desligado: congela a visão; ao religar, atualiza na hora |
| **Without Task ID** | Esconde o ID numérico (no Java a opção existia, mas o botão não atualizava a tela) |

Se o `platform.cfg` não tiver nomes de tarefas, a janela avisa uma vez que os IDs serão mostrados como números.

### 10.4 Message Log (`MessageLogWindow`)

Lista (500×600, como no original) das mensagens entre PEs, na ordem do `traffic_router.txt`:

| Condição do pacote | Linha |
|---|---|
| Entrou pela porta `LOCAL0`/`LOCAL1` (saindo do PE) | `---->>> <origem> send message to <destino> service <SERVIÇO>` |
| `router_address == target_router` (chegou ao destino) | `<<<---- <destino> receive message with service  <SERVIÇO>` |

Se as duas condições valem (mensagem para o próprio PE), fica a linha de recebimento, como no Java.

- Mostra todos os pacotes **já lidos** e acrescenta os novos conforme a simulação avança. Voltar no tempo não apaga linhas, pois os pacotes continuam lidos (mesmo comportamento do original).
- A lista acompanha o fim automaticamente, a menos que o usuário tenha rolado para cima.
- Os roteadores aparecem como `XxY` com endereçamento XY (o Java mostrava o endereço hamiltoniano numérico) ou pelo número com endereçamento HAMILTONIAN, igual ao resto da interface.

### 10.5 Deloream (`deloream.py`)

**Menu:** `Tools → Deloream` — *Debug Log Reader for MPSoCs*. Janela independente (800×700) que lê a pasta do cenário, a que contém o diretório `debug/` aberto (`MPSoCConfig.get_testcase_path()`):

```
<cenário>/
 ├─ debug/platform.cfg   nomes das tarefas (BEGIN_task_name_relation) e das aplicações (BEGIN_app_name_relation)
 └─ log/log<X>x<Y>.txt   saída de cada processador
```

- **Árvore** `Applications → aplicação[id] → tarefa[id]`; a tarefa pertence à aplicação `id >> 8`.
- **Duplo clique** (ou Enter) numa tarefa: procura em todos os arquivos de `log/` as linhas no formato

  ```
  $$$_<processador>_<app>_<tarefa>_<mensagem>
  ```

  com a aplicação e a tarefa escolhidas, e mostra as mensagens agrupadas por processador (`-- Processor: 1x1`), na ordem dos arquivos e das linhas.
- Sem mensagens (ou sem a pasta `log/`): *"Log file not created yet or no message found!"* em vermelho.
- **Options → New testcase** (Ctrl+N) abre outro cenário; **Reload** (F5) relê o `platform.cfg`; **Exit** (Ctrl+E) fecha só a janela.
- Abrir o menu de novo reaproveita a janela; se o debug carregado for de outro cenário, a árvore é recarregada.

Classes/funções: `TaskMessage.parse(line)`, `read_name_relations(platform_path)`, `read_task_messages(log_dir, app_id, task_id)` e `DeloreamWindow`.

---

## 11. Diferenças e correções em relação ao Java

| Local | Java | Python |
|---|---|---|
| `getChannel` / `PacketInformation` | Testava `EAST0` duas vezes e esquecia `WEST0` (WEST 0 virava LOW) | Portas pares são HIGH |
| `PacketInformation.getInput_portString` | Comparava a porta com constantes de canal; quase sempre `null` | `get_input_port_string()` e `get_channel_string()` separados |
| `ReadTrafficData.getPacketCounterByTime` | Estourava o índice quando o tempo era igual ao do último pacote | Busca binária com `bisect` |
| `PortInformation` | `NullPointerException` para serviços desconhecidos | Contadores começam em zero |
| `MPSoCInformation.getNextPacket` | Recebia a janela `FilterForm` | Recebe uma função `packet -> bool` |
| Pacotes em trânsito (`unfinished_packet_list`) | Guardava a origem e comparava com o destino; os caminhos vermelhos nunca eram apagados | Guarda o destino; o caminho some quando o pacote chega |
| Setas de borda | Uma seta de periférico pintada de vermelho nunca era apagada | É apagada no reset do caminho |
| Tempo em ms | Clock fixo de 10 ns | Usa o `clock_period_ns` do `platform.cfg` |
| Play ao fim do arquivo | Continuava em loop | Para e avisa na barra de status |
| Thread de simulação | `Thread` + `sleep()` alterando a interface | `QTimer` na thread principal |
| Getters/setters | Métodos `getX()`/`setX()` | Atributos e `dataclass` |
| `TaskInformation.remote_task_id` | `0` quando ausente | `-1` quando ausente |
| Task Mapping: atualização | `Thread` recriando todos os painéis a cada 1 s | `QTimer` que só redesenha se chegou pacote novo, reaproveitando os widgets |
| Task Mapping: ordem das tarefas | Ordem do `HashMap` (aleatória) | Ordenadas pelo ID |
| Task Mapping: cor do texto | Sempre preto (ilegível em cores escuras) | Preto ou branco conforme o fundo |
| Communication Overview: atualização | Calculado só ao abrir ou ao mudar um filtro | Acompanha a simulação |
| Deloream: mensagem | Juntava as partes sem os `_` (`valor_de_x` virava `valordex`) | Mantém a mensagem inteira |
| Deloream: busca | Procurava `_app_tarefa_` em qualquer ponto da linha (podia casar com o texto da mensagem) | Compara os campos de aplicação e tarefa |
| Deloream: Exit / New testcase | `Exit` fechava o debugger inteiro (`System.exit`); `New testcase` lia um caminho `null` | Fecha só a janela; abre um seletor de pasta |
| `get_testcase_path` | Cortava o caminho na primeira ocorrência de "debug" (quebrava em pastas como `debugger/`) | Pasta pai do diretório `debug` |
| Message Log | Retrato dos pacotes lidos no momento em que a janela abria; endereço hamiltoniano | Acrescenta as mensagens novas durante a simulação; endereço `XxY` com endereçamento XY |

---

## 12. Limitações e próximos passos

- **Back To** só vai até tempos já simulados (mesmo comportamento do Java).
- **Filtro de serviços/PEs** (`Filters → Service and PE Filter`): ainda não implementado. O controlador já aceita `SimulationController.packet_filter`.
- O relatório de uso de link por roteador (`printRouterTotalLinkUsage`, oculto no Java) não foi portado.

---

## 13. Como testar

1. Extraia o `DEBUG EXAMPLE.zip`.
2. Execute `uv run main.py` (ou `.venv/bin/python main.py`).
3. `File → New Debugging` → selecione `DEBUG EXAMPLE/LOGS/example_testcase/example_scenario/debug`.
4. Use `>||` para avançar pacote a pacote, `>` para rodar e o slider para a velocidade (99–100 = modo rápido).
5. Digite um tempo já simulado em **Back To** e clique em **Go**.
6. `File → Reset Simulation` volta ao início.
7. Abra `Tools → Communication Overview`, `Tools → Task Mapping Overview` e `Tools → Message Log` e rode a simulação: as porcentagens, as tarefas e as mensagens mudam conforme os pacotes avançam (2 755 mensagens ao fim do exemplo).

Resultados esperados com o exemplo: 3 101 pacotes, último pacote em 6 251 176 ticks (62,51176 ms com clock de 10 ns), 42 serviços e 11 tarefas.
