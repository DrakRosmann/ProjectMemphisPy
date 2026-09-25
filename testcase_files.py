"""
Leitura do YAML do testcase do Memphis-V (<testcase>/<testcase>.yaml).

Só a seção de periféricos é usada:

    hw:
      Peripherals:
        - name: APP_INJ
          pe: 2,2
          port: N

O arquivo é simples o bastante para ser lido linha a linha, sem depender do
PyYAML.
"""

import os
from dataclasses import dataclass

SIDES = {"N": "north", "S": "south", "E": "east", "W": "west"}


@dataclass(frozen=True)
class Peripheral:
    name: str
    x: int
    y: int
    side: str          # "N", "S", "E" ou "W"


def find_testcase_yaml(mpsoc_config):
    """
    <testcase>/<testcase>.yaml. O diretório de debug fica em
    <testcase>/<cenário>/debug, então o testcase é dois níveis acima.
    """
    scenario = mpsoc_config.get_testcase_path()
    if scenario is None:
        return None
    testcase = os.path.dirname(os.path.normpath(scenario))
    path = os.path.join(testcase, os.path.basename(testcase) + ".yaml")
    return path if os.path.isfile(path) else None


def _value(line):
    return line.split(":", 1)[1].strip().strip("\"'")


def parse_peripherals(text):
    """Periféricos declarados em hw → Peripherals (linhas inválidas são ignoradas)."""
    peripherals = []
    in_section = False
    section_indent = 0
    current = {}

    def flush():
        try:
            x, y = (int(value) for value in current["pe"].replace("[", "").replace("]", "").split(","))
            side = current["port"].upper()[:1]
            if side in SIDES:
                peripherals.append(Peripheral(current.get("name", "Peripheral"), x, y, side))
        except (KeyError, ValueError):
            pass

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if stripped.lower().startswith("peripherals:"):
            in_section, section_indent, current = True, indent, {}
            continue
        if not in_section:
            continue
        if indent <= section_indent:           # fim da seção
            break

        if stripped.startswith("- "):
            if current:
                flush()
            current = {}
            stripped = stripped[2:].strip()
        if ":" in stripped:
            current[stripped.split(":", 1)[0].strip().lower()] = _value(stripped)

    if in_section and current:
        flush()
    return peripherals


def read_peripherals(mpsoc_config):
    """(periféricos, caminho do YAML) — lista vazia e None se o YAML não existir."""
    path = find_testcase_yaml(mpsoc_config)
    if path is None:
        return [], None
    try:
        with open(path, "r", encoding="utf-8") as yaml_file:
            return parse_peripherals(yaml_file.read()), path
    except OSError:
        return [], None
