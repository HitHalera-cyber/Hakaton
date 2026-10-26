"""«Уточнить размеры»: every size of the drawing in one table — what is
written, what the lines measure, whether it was held, its tolerance and
limits — and the user's own value and tolerance for any of them; under them
the numbers whose dimension line was not found, each with what it may
measure, and the roughness marks of the sheet. The drawing is then recognised again
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
from ..semantics.tolerance import limits_text, middle, roughness, split_size
from .widgets import label

KINDS = {"linear": "линейный", "diameter": "диаметр", "radius": "радиус", "angular": "угол"}
VALUE_COLUMN, TOL_COLUMN, LIMITS_COLUMN = 5, 6, 7
HEADERS = ["Размер", "Вид", "На чертеже", "По линиям", "Состояние", "Значение", "Допуск",
           "Пределы"]


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
        _, _, tol = split_size(d.text)
        _, _, tol0 = split_size(getattr(d, "original_text", d.text))
        rows.append({"id": d.id, "kind": KINDS.get(d.dim_type, d.dim_type), "text": d.text,
                     "nominal": d.nominal, "lines": lines, "state": state,
                     "tol": tol, "original_tol": tol0,
                     "limits": limits_text(d.nominal, tol) if d.dim_type != "angular" else "",
                     # the number of the drawing itself, before any value of the user
                     "original": getattr(d, "original_nominal", d.nominal),
                     "conflict": d.id in skipped, "manual": "уточнён вручную" in d.notes})
    # the questionable first: they are what the user came for
    rows.sort(key=lambda r: (not r["conflict"], r["state"] == "выдержан", r["id"]))
    return rows


def orphan_rows(drawing: ir.Drawing) -> list[dict]:
    """The numbers kept as text for want of a dimension line."""
    return [dict(o, orphan=True) for o in getattr(drawing, "orphans", None) or []]


def roughness_rows(drawing: ir.Drawing) -> list[dict]:
    """The roughness marks written on the sheet (Ra 3,2; Rz 20 (√) — the rest)."""
    out = []
    for t in drawing.of_type(ir.Text):
        r = roughness(t.text)
        if r:
            out.append({"id": t.id, "text": t.text, "kind": r[0], "value": r[1],
                        "rest": "(" in t.text or "√" in t.text})
    return out


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
        self.table = QTableWidget(len(self.rows) + len(self.orphans), len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
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
            own = self.overrides.get(r["id"])
            value = own.get("value") if isinstance(own, dict) else own
            item = QTableWidgetItem(_number(value if value is not None else r["nominal"]))
            item.setToolTip("Двойной щелчок — ввести своё число")
            self.table.setItem(i, VALUE_COLUMN, item)
            tol = QTableWidgetItem(r["tol"])
            tol.setToolTip("Допуск: ±0,1  -0,2  +0,3  +0,2/-0,1  или поле: h12, H7, js9")
            self.table.setItem(i, TOL_COLUMN, tol)
            limits = QTableWidgetItem(r["limits"])
            limits.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(i, LIMITS_COLUMN, limits)
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
            for j in (TOL_COLUMN, LIMITS_COLUMN):
                item = QTableWidgetItem("")
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
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
        self.table.itemChanged.connect(self._limits)

        self.rough = roughness_rows(drawing)
        self.rough_table = QTableWidget(len(self.rough), 3)
        self.rough_table.setHorizontalHeaderLabels(["Надпись", "На чертеже", "Значение"])
        self.rough_table.verticalHeader().setVisible(False)
        self.rough_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.rough_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for i, r in enumerate(self.rough):
            for j, text in enumerate([r["id"], r["text"]]):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.rough_table.setItem(i, j, item)
            own = self.overrides.get(r["id"])
            item = QTableWidgetItem(own["text"] if isinstance(own, dict) and own.get("text")
                                    else r["text"])
            item.setToolTip("Например: Ra 3,2 · Rz 20 (√) — «(√)»: шероховатость остальных "
                            "поверхностей")
            self.rough_table.setItem(i, 2, item)
        if self.rough:
            lay.addWidget(label("Шероховатость поверхностей", "cardHead"))
            self.rough_table.setMaximumHeight(36 + 30 * min(len(self.rough), 4))
            lay.addWidget(self.rough_table)
        else:
            self.rough_table.hide()

        row = QHBoxLayout()
        lines = QPushButton("Верить линиям", objectName="secondary")
        lines.setToolTip("Для выбранных размеров взять значение, намеренное по линиям")
        lines.clicked.connect(self.trust_lines)
        mid = QPushButton("Середина допуска", objectName="secondary")
        mid.setToolTip("Для выбранных размеров строить по середине поля допуска "
                       "(так деталь изготавливают)")
        mid.clicked.connect(self.to_middle)
        reset = QPushButton("Как на чертеже", objectName="secondary")
        reset.setToolTip("Вернуть выбранным размерам числа с чертежа")
        reset.clicked.connect(self.reset_rows)
        row.addWidget(lines)
        row.addWidget(mid)
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
        apply.setEnabled(bool(self.rows or self.orphans or self.rough))
        row.addWidget(cancel)
        row.addWidget(apply)
        lay.addLayout(row)
        if not self.rows:
            lines.hide()
            mid.hide()
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
            self.table.item(i, TOL_COLUMN).setText(self.rows[i]["original_tol"])

    def to_middle(self) -> None:
        for i in self._selected():
            value = parse_value(self.table.item(i, VALUE_COLUMN).text())
            tol = self.table.item(i, TOL_COLUMN).text()
            m = middle(value, tol) if value else None
            if m is not None:
                self.table.item(i, VALUE_COLUMN).setText(_number(round(m, 3)))
                self.table.item(i, TOL_COLUMN).setText("")  # the middle is the size now

    def _limits(self, item) -> None:
        """The limits follow the value and the tolerance as they are typed."""
        i = item.row()
        if i >= len(self.rows) or item.column() not in (VALUE_COLUMN, TOL_COLUMN):
            return
        value = parse_value(self.table.item(i, VALUE_COLUMN).text())
        tol = self.table.item(i, TOL_COLUMN).text() if self.table.item(i, TOL_COLUMN) else ""
        cell = self.table.item(i, LIMITS_COLUMN)
        if cell is not None:
            self.table.blockSignals(True)
            cell.setText(limits_text(value, tol) if value else "")
            self.table.blockSignals(False)

    def _ask_photo(self) -> None:
        self.photo_requested = True
        self.accept()

    def _apply(self) -> None:
        out = {}
        for i, r in enumerate(self.rows):
            value = parse_value(self.table.item(i, VALUE_COLUMN).text())
            if value is not None and (value <= 0 or r["original"] is not None
                                      and abs(value - r["original"]) <= 1e-9):
                value = None  # what the drawing says is no override
            tol = self.table.item(i, TOL_COLUMN).text().strip()
            tol = tol if tol != r["original_tol"] else None
            if tol is None and value is not None:
                out[r["id"]] = value
            elif tol is not None:
                out[r["id"]] = {"value": value, "tol": tol}
        for i, r in enumerate(self.rough):
            text = self.rough_table.item(i, 2).text().strip()
            if text and text != r["text"]:
                out[r["id"]] = {"text": text}
        self.overrides = out
        for o, combo in zip(self.orphans, self.combos):
            k = combo.currentIndex()
            if k == 1:
                self.attach[o["id"]] = None
            elif k >= 2:
                self.attach[o["id"]] = key_of(o["candidates"][k - 2])
        self.accept()
