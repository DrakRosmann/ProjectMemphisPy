"""Exportação CSV/PNG."""

import csv

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem

import export


def test_write_csv(qapp, tmp_path):
    table = QTableWidget(2, 2)
    table.setHorizontalHeaderLabels(["Router", "Flits"])
    for row, values in enumerate((("0x0", "10"), ("1x0", "20, with comma"))):
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))

    path = tmp_path / "table.csv"
    assert export.write_csv(table.model(), str(path)) == 2
    with open(path, newline="", encoding="utf-8") as csv_file:
        assert list(csv.reader(csv_file)) == [["Router", "Flits"], ["0x0", "10"], ["1x0", "20, with comma"]]


def test_save_png(qapp, tmp_path):
    label = QLabel("Memphis")
    label.resize(120, 40)
    path = tmp_path / "label.png"
    export.save_png(label, str(path))
    image = QImage(str(path))
    assert not image.isNull()
    assert image.width() >= 120
