"""Periféricos do YAML do testcase."""

from testcase_files import Peripheral, find_testcase_yaml, parse_peripherals, read_peripherals

YAML = """
hw:                         # Hardware properties
  mpsoc_dimension: [3,3]
  Peripherals:              # Attached peripherals
    - name: MA_INJ          # comentário
      pe: 0,0
      port: S
    - name: APP_INJ
      pe: [2,2]
      port: North
    - name: BROKEN          # sem porta: ignorado
      pe: 1,1
  parameters:
    - TRAFFIC_DEBUG: yes
"""


def test_parse_peripherals():
    assert parse_peripherals(YAML) == [Peripheral("MA_INJ", 0, 0, "S"), Peripheral("APP_INJ", 2, 2, "N")]


def test_no_peripherals_section():
    assert parse_peripherals("hw:\n  mpsoc_dimension: [3,3]\n") == []


def test_example_testcase(config):
    peripherals, path = read_peripherals(config)
    assert path.endswith("example_testcase.yaml")
    assert peripherals == [Peripheral("MA_INJ", 0, 0, "S"), Peripheral("APP_INJ", 2, 2, "N")]


def test_missing_yaml(tmp_path):
    from util.MPSoCConfig import MPSoCConfig
    debug = tmp_path / "scenario" / "debug"
    debug.mkdir(parents=True)
    (debug / "platform.cfg").write_text("mpsoc_x 2\nmpsoc_y 2\n")
    (debug / "services.cfg").write_text("")
    config = MPSoCConfig(str(debug))
    assert find_testcase_yaml(config) is None
    assert read_peripherals(config) == ([], None)
