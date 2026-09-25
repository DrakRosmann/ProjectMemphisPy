# Roteiro da apresentação — Memphis-V Graphical Debugger (v0.1.0-alpha)

Slides: `documentation/apresentacao_memphis_debugger.pptx` (15 slides). O texto completo de cada fala está nas **notas do apresentador** de cada slide; este roteiro resume o tempo, os pontos-chave e os momentos de demonstração.

**Duração total:** ~20 minutos + perguntas.

---

## Antes de começar (checklist)

- [ ] Extrair o `DEBUG EXAMPLE.zip` e anotar o caminho de `LOGS/example_testcase/example_scenario/debug/`
- [ ] Abrir o debugger (`./dist/MemphisVDebugger/MemphisVDebugger` ou `uv run main.py`) e deixar minimizado
- [ ] Deixar o tema **claro** (Edit → Dark Mode desmarcado), para a demonstração começar igual aos slides
- [ ] Testar o projetor/compartilhamento de tela com a janela do debugger (a grade de roteadores precisa estar legível)
- [ ] Ter a release `v0.1.0-alpha` aberta no navegador, para mostrar no final

---

## Parte 1 — Contexto (≈ 3,5 min)

| Slide | Tempo | Pontos-chave |
|---|---|---|
| 1. Capa | 1 min | Refatoração Java → Python/PySide6; é uma **alpha**: muito já funciona, mas não tudo. A imagem é o sistema novo em execução. |
| 2. Memphis-V e o Graphical Debugger | 1,5 min | Memphis-V simula MPSoCs com NoC; o debugger reproduz os arquivos gravados pela simulação. Cenário de exemplo: 9 PEs, 3.101 pacotes, 11 tarefas. |
| 3. Por que migrar | 1 min | Os três objetivos do README: interface moderna, manutenção simples, execução sem JVM. |

## Parte 2 — Como o sistema funciona (≈ 7,5 min)

| Slide | Tempo | Pontos-chave |
|---|---|---|
| 4. Arquitetura | 2 min | Arquivos → `MPSoCConfig` / `ReadTrafficData` → `MPSoCInformation` → controlador e janelas. Leitura **sob demanda** e cache para voltar no tempo. Nomes das classes iguais aos do Java. |
| 5. traffic_router.txt | 1,5 min | Ler a linha de exemplo campo a campo. Abertura validada: sem os 3 arquivos, nada é carregado. |
| 6. Janela principal | 2 min | Os 5 elementos numerados. **→ Demonstração 1** |
| 7. Como a simulação funciona | 2 min | Ciclo de 4 passos; checkpoint de 0,5 ms; velocidades 1–98 vs. 99–100; QTimer no lugar da thread do Java. |

### 🎬 Demonstração 1 (no slide 6, ~2 min dentro do tempo do slide)

1. **File → New Debugging** → selecionar a pasta `debug/` do exemplo.
2. Clicar **>||** umas 5 vezes: mostrar a tabela *Current Packet* e o tempo mudando.
3. Colocar a velocidade em ~90 e dar **>** (play): mostrar as setas vermelhas se movendo.
4. **STOP**, olhar o tempo em ticks no *Speed Control*, digitar em **Back To** um valor menor que ele (ex.: metade) e clicar **Go**.
5. *(Opcional)* Mostrar o erro ao abrir uma pasta sem os arquivos (ex.: `LOGS/example_testcase/debug/`, que não tem `traffic_router.txt`).

## Parte 3 — Janelas de análise (≈ 5,5 min)

| Slide | Tempo | Pontos-chave |
|---|---|---|
| 8. Communication Overview | 1,5 min | Mapa de calor azul → vermelho; filtros de serviço e volume/banda; *Statistics*. **Novo:** acompanha a simulação (o Java era uma foto). |
| 9. Task Mapping e Message Log | 1,5 min | RUN/TER por PE, uma cor por aplicação, botão para congelar; Message Log com `---->>>` (envio) e `<<<----` (recebimento), 2.755 linhas no fim. |
| 10. Deloream | 1,5 min | Lê `log/`; formato `$$$_proc_app_tarefa_mensagem`; duplo clique na tarefa. Correções: `_` preservado, Exit não fecha o debugger. |
| 11. Modo escuro e melhorias | 1 min | **→ Demonstração 2** |

### 🎬 Demonstração 2 (no slide 11, ~1,5 min)

1. Com a simulação parada no meio, abrir **Tools → Communication Overview** e **Tools → Task Mapping Overview** lado a lado.
2. Dar **>** na janela principal e mostrar as duas janelas se atualizando sozinhas.
3. **Tools → Deloream** → duplo clique em `prod[769]`.
4. **Ctrl+T** para alternar para o modo escuro (e de volta).

## Parte 4 — Situação e próximos passos (≈ 4 min)

| Slide | Tempo | Pontos-chave |
|---|---|---|
| 12. Bugs corrigidos | 1,5 min | Seis exemplos; a lista completa está em `documentation/implementacoes.md` (seção 11). |
| 13. Status | 1,5 min | **10 já refatorados × 6 faltando** (contagem por funcionalidade). Deixar claro: por isso é alpha. |
| 14. Próximos passos | 1 min | Estabilizar (CI Linux + Windows) → filtros e detalhes do roteador → projetos → beta. |

## Encerramento (≈ 1 min + perguntas)

| Slide | Tempo | Pontos-chave |
|---|---|---|
| 15. Como experimentar | 1 min | Executável da release, `uv run main.py`, primeiro teste com o `DEBUG EXAMPLE.zip`. Pedir relatos nas Issues. Abrir para perguntas. |

---

## Perguntas prováveis

| Pergunta | Resposta curta |
|---|---|
| Funciona no Windows? | O código não tem nada específico de Linux, mas o executável atual é só Linux. O build de Windows (PyInstaller em uma máquina Windows ou no CI) é o primeiro item do roteiro. |
| Por que o Back To não avança para o futuro? | Ele só volta para tempos já lidos do arquivo — mesmo comportamento do original. Para avançar, usa-se o play em velocidade 99–100. |
| Os resultados batem com o debugger Java? | A lógica foi portada classe a classe. As diferenças são as correções de bugs listadas no slide 12 (e na documentação). |
| Arquivos grandes de tráfego ficam lentos? | O arquivo é lido sob demanda e as janelas redesenham no máximo 2×/s; o modo rápido processa lotes de 200 pacotes. Ainda não foi testado com cenários muito maiores que o exemplo. |
| O que acontece com cenários de outro tamanho (4×4, 8×8)? | A grade, as janelas e os cálculos usam `mpsoc_x`/`mpsoc_y` do `platform.cfg`; clusters são desenhados com borda. |
