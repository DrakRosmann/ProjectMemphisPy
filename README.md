# Memphis-V Graphical Debugger (Python/PySide6)

Este projeto é uma refatoração completa em **Python** do [Debugger Gráfico original](https://github.com/gaph-pucrs/GraphicalDebugger) desenvolvido em Java para o framework [Memphis-V](https://github.com/gaph-pucrs/Memphis-V). 

A nova versão utiliza **PySide6** (Qt for Python) para entregar uma interface gráfica moderna, responsiva e com integração facilitada, aproveitando a versatilidade do ecossistema Python.

---

##  Objetivo

O Memphis-V é um framework para avaliação e simulação de *Many-core Systems-on-Chip* (NoC-based). O objetivo deste depurador gráfico é permitir a visualização intuitiva e o acompanhamento do fluxo de execução, tráfego da rede em chip e comportamento dos processadores dentro do ambiente do Memphis-V.

A migração de Java para Python visa:
* **Modernizar a UI/UX** utilizando os componentes nativos e de alta performance do Qt6.
* **Facilitar a manutenção** e a contribuição da comunidade com um código mais conciso.
* **Simplificar a execução** em ambientes Linux, eliminando a dependência da JVM.

---

## Fluxo de contribuição com Git

* **Branches:** use um nome curto e descritivo, baseado no título de uma issue do GitHub ou no que está sendo implementado. Escreva em letras minúsculas e separe as palavras com hífens. Exemplo: `corrigir-decode`.
* **Commits:** termine a mensagem com uma das categorias entre colchetes: `[enhancement]` para melhorias, `[feature]` para novas funcionalidades ou `[bugfix]` para correções. Exemplo: `Fixed error on Decode. [bugfix]`.
* **Merges:** de preferência, abra um Pull Request (Merge Request) para integrar a branch. Descreva resumidamente o que foi implementado usando bullet points.
* **Documentação:** coloque explicações mais extensas ou complexas no diretório `documentation/` e inclua um link para elas no Pull Request, quando pertinente.

---

##  Tecnologias Utilizadas

* **Linguagem:** [Python 3.10+](https://www.python.org/)
* **Interface Gráfica:** [PySide6](https://doc.qt.io/qtforpython-6/) (Qt6)

---
