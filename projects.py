"""
Projetos de debug salvos (File -> Save / Open / Delete Project).

Como no Java (MainFrame.saveMenuItemActionPerformed e afins), um projeto é
um arquivo <nome>.hdf ("HeMPS Debugging File") cuja primeira linha é o
caminho do diretório de debug. O Java gravava em <diretório atual>/projects,
que muda conforme de onde o programa é executado (e não existe no
executável do PyInstaller); aqui a pasta fica nos dados do usuário.
"""

import os

from PySide6.QtCore import QStandardPaths

PROJECT_EXTENSION = ".hdf"
PROJECT_FILTER = "HeMPS Debugging File (*.hdf)"


def projects_dir():
    """Pasta dos projetos, criada se ainda não existir."""
    # Local fixo, independente do nome dado ao QApplication (~/.local/share no Linux)
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    path = os.path.join(base, "GAPH", "MemphisGraphicalDebugger", "projects")
    os.makedirs(path, exist_ok=True)
    return path


def project_path(name):
    return os.path.join(projects_dir(), name + PROJECT_EXTENSION)


def validate_name(name):
    """Mensagem de erro para o nome informado, ou None se ele for válido."""
    if not name:
        return "Name is empty"
    if " " in name:
        return "Name contains space"
    if os.sep in name or (os.altsep and os.altsep in name) or name in (".", ".."):
        return "Name contains invalid characters"
    return None


def save_project(name, debug_dir):
    with open(project_path(name), "w", encoding="utf-8") as project:
        project.write(os.path.abspath(debug_dir) + "\n")


def read_project(path):
    """Diretório de debug guardado no projeto (primeira linha do arquivo)."""
    with open(path, "r", encoding="utf-8") as project:
        return project.readline().strip()


def project_name(path):
    return os.path.splitext(os.path.basename(path))[0]
