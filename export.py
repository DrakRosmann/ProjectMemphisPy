"""
Exportação de tabelas (CSV) e janelas/gráficos (PNG).

Qualquer QTableWidget/QTableView exporta o que está visível (com filtros e
ordenação aplicados). install_export_actions() coloca "Export CSV…" e/ou
"Save as PNG…" no menu de contexto (botão direito) de um widget.
"""

import csv
import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMessageBox

_SETTINGS_KEY = "export/last_dir"


def _settings():
    return QSettings("GAPH", "MemphisGraphicalDebugger")


def _ask_path(parent, title, default_name, file_filter, extension):
    directory = _settings().value(_SETTINGS_KEY, os.path.expanduser("~"))
    path, _ = QFileDialog.getSaveFileName(parent, title, os.path.join(directory, default_name), file_filter)
    if not path:
        return None
    if not path.lower().endswith(extension):
        path += extension
    _settings().setValue(_SETTINGS_KEY, os.path.dirname(path))
    return path


def model_rows(model):
    """Cabeçalhos e linhas (texto exibido) de um modelo de tabela."""
    columns = range(model.columnCount())
    headers = [str(model.headerData(column, Qt.Orientation.Horizontal) or "") for column in columns]
    rows = [[str(model.data(model.index(row, column)) or "") for column in columns]
            for row in range(model.rowCount())]
    return headers, rows


def write_csv(model, path):
    headers, rows = model_rows(model)
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headers)
        writer.writerows(rows)
    return len(rows)


def save_png(widget, path):
    # Vistas com zoom/rolagem (ex.: a malha) exportam o conteúdo inteiro
    image = widget.to_image() if hasattr(widget, "to_image") else widget.grab()
    if not image.save(path, "PNG"):
        raise OSError(f"could not write {path}")


def export_csv(parent, view, default_name):
    """Pergunta o arquivo e salva a tabela `view` (QTableWidget ou QTableView)."""
    path = _ask_path(parent, "Export CSV", default_name + ".csv", "CSV (*.csv)", ".csv")
    if path is None:
        return None
    try:
        write_csv(view.model(), path)
    except OSError as error:
        QMessageBox.critical(parent, "Export CSV", f"Could not save the file:\n{error}")
        return None
    return path


def export_png(parent, widget, default_name):
    """Pergunta o arquivo e salva uma imagem do `widget` como ele aparece na tela."""
    path = _ask_path(parent, "Save as PNG", default_name + ".png", "PNG image (*.png)", ".png")
    if path is None:
        return None
    try:
        save_png(widget, path)
    except OSError as error:
        QMessageBox.critical(parent, "Save as PNG", f"Could not save the image:\n{error}")
        return None
    return path


def install_export_actions(widget, default_name, csv_view=None, png_widget=None):
    """Menu de contexto com as exportações disponíveis para o widget."""
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
    if csv_view is not None:
        action = QAction("Export CSV…", widget)
        action.triggered.connect(lambda: export_csv(widget.window(), csv_view, default_name))
        widget.addAction(action)
    if png_widget is not None:
        action = QAction("Save as PNG…", widget)
        action.triggered.connect(lambda: export_png(widget.window(), png_widget, default_name))
        widget.addAction(action)
