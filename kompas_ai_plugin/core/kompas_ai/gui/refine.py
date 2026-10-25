"""«Уточнить размеры»: every size of the drawing in one table — what is
written, what the lines measure, whether it was held — and the user's own
value for any of them; under them the numbers whose dimension line was not
found, each with what it may measure. The drawing is then recognised again
with those values and choices (pipeline: ``recognize_pdf(..., overrides=...,
attach=...)``)."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from .. import ir
from ..semantics.orphans import key_of
from .widgets import label

KINDS = {"linear": "линейный", "diameter": "диаметр", "radius": "радиус", "angular": "угол"}
VALUE_COLUMN = 5


def dimension_rows(drawing: ir.Drawing) -> list[dict]:
    """The sizes of the drawing with what the window shows about them."""
    skipped = set(getattr(drawing, "dims_skipped", ()) or ())
    scale = drawing.scale.value or 1.0
    rows = []
    for d in drawing.of_type(ir.Dimension):
        lines = None
        if d.measured is not None:
            lines = d.measured if d.dim_type == "angular" else d.measured / scale
        if d.id in skipped:
            state = "не выдержан: противоречит другим"
        elif d.confidence < ir.REVIEW_THRESHOLD:
            state = "прочитан с сомнением"
        else:
            state = "выдержан"
        rows.append({"id": d.id, "kind": KINDS.get(d.dim_type, d.dim_type), "text": d.text,
                     "nominal": d.nominal, "lines": lines, "state": state,
                     # the number of the drawing itself, before any value of the user
                     "original": getattr(d, "original_nominal", d.nominal),
                     "conflict": d.id in skipped, "manual": "уточнён вручную" in d.notes})
    # the questionable first: they are what the user came for
    rows.sort(key=lambda r: (not r["conflict"], r["state"] == "выдержан", r["id"]))
    return rows


def orphan_rows(drawing: ir.Drawing) -> list[dict]:
    """The numbers kept as text for want of a dimension line."""
    return [dict(o, orphan=True) for o in getattr(drawing, "orphans", None) or []]


def questions(drawing: ir.Drawing) -> list[dict]:
    """What the window asks about before building: the sizes not held, then
    the numbers without a dimension line (they would silently not hold)."""
    return [r for r in dimension_rows(drawing) if r["conflict"]] + orphan_rows(drawing)


KEEP, AS_TEXT = "— не трогать", "это просто текст"


def _number(value) -> str:
    if value is None:
        return "—"
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def parse_value(text: str) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", text or "")
    return float(m.group(0).replace(",", ".")) if m else None


class RefineDialog(QDialog):
    """The table of sizes; ``overrides`` (dimension id → value, model mm) after
    «Пересчитать»."""

    def __init__(self, drawing: ir.Drawing, overrides: dict, parent=None, photo: bool = False,
                 focus: str | None = None, attach: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Уточнить размеры")
        self.resize(860, 560)
        self.overrides = dict(overrides)
        self.attach = dict(attach or {})  # text id → {"kind", "refs"} | None (just text)
        self.photo_requested = False
        self.rows = dimension_rows(drawing)
        self.orphans = orphan_rows(drawing)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        intro = ("Введите своё число в столбце «Значение» — чертёж пересчитается так, чтобы "
                 "линии ему соответствовали. «Верить линиям» берёт то, что намерено по линиям.")
        if photo and not self.rows:
            intro = ("На фото числа размеров не читаются, поэтому уточнять пока нечего. "
                     "Размеры детали задаются форматом листа и масштабом фото — их можно "
                     "изменить, а точные числа вписать в КОМПАС после построения.")
        note = label(intro, "sub")
        note.setWordWrap(True)
        lay.addWidget(note)

        if self.orphans:
            intro += (" Ниже — числа без размерной линии: выберите, что каждое из них измеряет "
                      "(или «это просто текст»).")
            note.setText(intro)
        self.table = QTableWidget(len(self.rows) + len(self.orphans), 6)
        self.table.setHorizontalHeaderLabels(["Размер", "Вид", "На чертеже", "По линиям",
                                              "Состояние", "Значение"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        warn = QColor("#B45309")
        for i, r in enumerate(self.rows):
            cells = [r["id"], r["kind"], r["text"], _number(r["lines"]), r["state"]]
            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                if r["conflict"] and j == 4:
                    item.setForeground(warn)
                self.table.setItem(i, j, item)
            value = self.overrides.get(r["id"], r["nominal"])
            item = QTableWidgetItem(_number(value))
            item.setToolTip("Двойной щелчок — ввести своё число")
            self.table.setItem(i, VALUE_COLUMN, item)
            if focus and r["id"] == focus:
                self.table.selectRow(i)
        self.combos: list[QComboBox] = []
        for k, o in enumerate(self.orphans):
            i = len(self.rows) + k
            cells = [o["id"], "без размерной линии", o["text"], "—", "не привязан"]
            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                if j == 4:
                    item.setForeground(warn)
                self.table.setItem(i, j, item)
            combo = QComboBox()
            combo.addItems([KEEP, AS_TEXT] + [c["label"] for c in o["candidates"]])
            combo.setToolTip("Что измеряет это число — размер будет построен и выдержан")
            self.table.setCellWidget(i, VALUE_COLUMN, combo)
            self.combos.append(combo)
            if focus and o["id"] == focus:
                self.table.selectRow(i)
        if focus:
            for i in range(self.table.rowCount()):
                if self.table.item(i, 0).text() == focus:
                    self.table.scrollToItem(self.table.item(i, 0))
        lay.addWidget(self.table, 1)
        if not self.rows and not self.orphans:
            self.table.hide()

        row = QHBoxLayout()
        lines = QPushButton("Верить линиям", objectName="secondary")
        lines.setToolTip("Для выбранных размеров взять значение, намеренное по линиям")
        lines.clicked.connect(self.trust_lines)
        reset = QPushButton("Как на чертеже", objectName="secondary")
        reset.setToolTip("Вернуть выбранным размерам числа с чертежа")
        reset.clicked.connect(self.reset_rows)
        row.addWidget(lines)
        row.addWidget(reset)
        if photo:
            sheet = QPushButton("Формат и масштаб фото…", objectName="secondary")
            sheet.clicked.connect(self._ask_photo)
            row.addWidget(sheet)
        row.addStretch(1)
        cancel = QPushButton("Отмена", objectName="secondary")
        cancel.clicked.connect(self.reject)
        apply = QPushButton("Пересчитать", objectName="primary")
        apply.clicked.connect(self._apply)
        apply.setEnabled(bool(self.rows or self.orphans))
        row.addWidget(cancel)
        row.addWidget(apply)
        lay.addLayout(row)
        if not self.rows:
            lines.hide()
            reset.hide()

    def _selected(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectedIndexes() if i.row() < len(self.rows)})

    def trust_lines(self) -> None:
        for i in self._selected():
            lines = self.rows[i]["lines"]
            if lines is not None:
                self.table.item(i, VALUE_COLUMN).setText(_number(round(lines, 2)))

    def reset_rows(self) -> None:
        for i in self._selected():
            self.table.item(i, VALUE_COLUMN).setText(_number(self.rows[i]["original"]))

    def _ask_photo(self) -> None:
        self.photo_requested = True
        self.accept()

    def _apply(self) -> None:
        out = {}
        for i, r in enumerate(self.rows):
            value = parse_value(self.table.item(i, VALUE_COLUMN).text())
            if value is None or value <= 0:
                continue
            if r["original"] is None or abs(value - r["original"]) > 1e-9:
                out[r["id"]] = value  # what the drawing says is no override
        self.overrides = out
        for o, combo in zip(self.orphans, self.combos):
            k = combo.currentIndex()
            if k == 1:
                self.attach[o["id"]] = None
            elif k >= 2:
                self.attach[o["id"]] = key_of(o["candidates"][k - 2])
        self.accept()
