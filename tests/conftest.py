"""
Configuração comum dos testes.

- Qt roda sem janela (QT_QPA_PLATFORM=offscreen).
- QSettings e a pasta de projetos vão para um diretório temporário, para
  não mexer no tema, nos projetos e nas pastas salvos pelo usuário.
- O cenário de exemplo é extraído do "DEBUG EXAMPLE.zip" versionado no repositório.
"""

import os
import tempfile
import zipfile
from pathlib import Path

_SANDBOX = tempfile.mkdtemp(prefix="memphis-tests-")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = os.path.join(_SANDBOX, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_SANDBOX, "data")

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_ZIP = ROOT / "DEBUG EXAMPLE.zip"
SCENARIO_IN_ZIP = "DEBUG EXAMPLE/LOGS/example_testcase/example_scenario/"
TESTCASE_YAML_IN_ZIP = "DEBUG EXAMPLE/LOGS/example_testcase/example_testcase.yaml"


@pytest.fixture(scope="session")
def scenario_dir(tmp_path_factory):
    """Pasta do cenário de exemplo (contém debug/ e log/)."""
    if not EXAMPLE_ZIP.exists():
        pytest.skip("DEBUG EXAMPLE.zip not found")
    target = tmp_path_factory.mktemp("example")
    with zipfile.ZipFile(EXAMPLE_ZIP) as archive:
        members = [name for name in archive.namelist()
                   if name.startswith(SCENARIO_IN_ZIP) or name == TESTCASE_YAML_IN_ZIP]
        archive.extractall(target, members)
    return target / SCENARIO_IN_ZIP


@pytest.fixture(scope="session")
def debug_dir(scenario_dir):
    return str(scenario_dir / "debug")


@pytest.fixture(scope="session")
def config(debug_dir):
    from util.MPSoCConfig import MPSoCConfig
    return MPSoCConfig(debug_dir)


@pytest.fixture(scope="session")
def packets(config):
    """Todos os pacotes do traffic_router.txt do exemplo."""
    from information.read_traffic_data import ReadTrafficData
    from information.router_neighbors import RouterNeighbors
    reader = ReadTrafficData(config, RouterNeighbors.from_config(config))
    try:
        result = []
        while (packet := reader.get_next_packet()) is not None:
            result.append(packet)
        return result
    finally:
        reader.close()


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialogs(monkeypatch):
    """
    Substitui as caixas de diálogo modais (que travariam o teste) e registra
    as mensagens mostradas. `dialogs.answers` / `dialogs.texts` são as
    respostas das próximas perguntas / entradas de texto.
    """
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    class Recorder:
        def __init__(self):
            self.shown = []
            self.answers = []
            self.texts = []
            self.items = []

    recorder = Recorder()

    def show(kind):
        return staticmethod(lambda *args, **kwargs: recorder.shown.append((kind, args[1], args[2])))

    for kind in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, kind, show(kind))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *args, **kwargs: recorder.answers.pop(0) if recorder.answers else QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *args, **kwargs: recorder.texts.pop(0)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *args, **kwargs: recorder.items.pop(0)))
    return recorder
