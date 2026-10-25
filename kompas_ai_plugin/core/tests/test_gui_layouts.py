"""The three looks of the window: each one is built, each one shows a button
for every command of the program (one QAction behind each), and switching
keeps the drawing and the options."""

import os

import pytest


@pytest.fixture()
def window(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from kompas_ai.gui.app import MainWindow

    w = MainWindow()
    yield w
    w.close()
    w.deleteLater()
    app.processEvents()


# the commands every look must offer as a button of its own
COMMANDS = ["open", "from_model", "build", "model", "both", "refine", "dxf", "report", "check",
            "logs", "theme"]


def test_every_layout_offers_every_command(window):
    from PySide6.QtWidgets import QPushButton

    from kompas_ai.gui.layouts import LAYOUT_NAMES
    from kompas_ai.gui.widgets import ActionButton, ClickCard

    for key, _ in LAYOUT_NAMES:
        window.apply_layout(key)
        buttons = window.centralWidget().findChildren(QPushButton)
        actions = {b._action for b in buttons if isinstance(b, ActionButton)}
        actions |= {c._action for c in window.centralWidget().findChildren(ClickCard)
                    if hasattr(c, "_action")}
        missing = [c for c in COMMANDS if window.acts[c] not in actions]
        assert not missing, (key, missing)
        # the shared controls live in the look on screen
        for shared in (window.preview, window.mode, window.scale_box, window.dims_box,
                       window.param_box, window.marks_box, window.log, window.review):
            assert window.centralWidget().isAncestorOf(shared), (key, shared)


def test_switching_keeps_the_options(window):
    window.dims_box.setChecked(False)
    window.scale_box.setCurrentIndex(3)
    for key in ("wizard", "console", "engineer"):
        window.apply_layout(key)
        assert not window.dims_box.isChecked()
        assert window.scale_box.currentIndex() == 3
    assert window.settings.value("layout") == "engineer"
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


@pytest.mark.parametrize("size", [(1024, 700), (1280, 984), (1366, 728), (1920, 1040)])
def test_every_layout_fits_the_window(window, size):
    """On a laptop and on a big monitor alike nothing lies outside the window
    and no button cuts its own label."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QPushButton

    from kompas_ai.gui.layouts import LAYOUT_NAMES

    window.show()
    for key, _ in LAYOUT_NAMES:
        window.apply_layout(key)
        window.resize(*size)
        QApplication.processEvents()
        central = window.centralWidget()
        for b in central.findChildren(QPushButton):
            if not b.isVisibleTo(window) or b.objectName() == "link":
                continue
            inside_scroll = False
            p = b.parentWidget()
            while p is not None:
                inside_scroll |= isinstance(p, QAbstractScrollArea)
                p = p.parentWidget()
            corner = b.mapTo(central, QPoint(b.width(), b.height()))
            if not inside_scroll:
                assert corner.x() <= central.width() + 1, (key, size, b.text())
            if b.text():
                assert b.width() >= b.fontMetrics().horizontalAdvance(b.text()), (key, size, b.text())


def _with_orphans(window, tmp_path):
    from pathlib import Path

    from test_orphans import _shaft

    from kompas_ai.semantics.orphans import describe

    d = _shaft()
    d.orphans = describe(d)
    window.pdf = Path(tmp_path) / "shaft.pdf"
    window.drawing = d
    window.page_height = 297 / 25.4 * 72
    window.ui.show_drawing(window.info())
    return d


@pytest.mark.parametrize("size", [(1024, 700), (1920, 1040)])
def test_numbers_without_a_line_are_asked_in_every_layout(window, tmp_path, size):
    """«Ø30-0,2 — размер без размерной линии» with what it may measure, and the
    choice goes to the next recognition."""
    from PySide6.QtWidgets import QApplication, QPushButton

    from kompas_ai.gui.layouts import LAYOUT_NAMES

    window.show()
    _with_orphans(window, tmp_path)
    for key, _ in LAYOUT_NAMES:
        window.apply_layout(key)
        window.resize(*size)
        for _ in range(3):  # the cards are rebuilt when the column width settles
            QApplication.processEvents()
        central = window.centralWidget()
        texts = [b.text() for b in central.findChildren(QPushButton) if b.isVisibleTo(window)]
        assert "Это текст" in texts and any(t.startswith("Между линиями") for t in texts), key
        for b in central.findChildren(QPushButton):
            if b.isVisibleTo(window) and b.text():
                assert b.width() >= b.fontMetrics().horizontalAdvance(b.text()), (key, b.text())
    calls = []
    window.recognize = lambda: calls.append(dict(window.attach))
    window.attach_orphan("T1", 0)
    window.attach_orphan("T3", None)
    assert calls[-1]["T1"]["kind"] == "linear" and calls[-1]["T3"] is None


def test_sizes_dialog_lists_numbers_without_a_line(window, tmp_path):
    from kompas_ai.gui.refine import RefineDialog

    d = _with_orphans(window, tmp_path)
    dialog = RefineDialog(d, {}, window, focus="T2")
    assert len(dialog.combos) == 3
    dialog.combos[1].setCurrentIndex(2)  # T2: its first candidate (the hole)
    dialog.combos[2].setCurrentIndex(1)  # T3: just text
    dialog._apply()
    assert dialog.attach == {"T2": {"kind": "diameter", "refs": ["C1"]}, "T3": None}


def test_a_click_on_a_number_opens_its_row(window, tmp_path):
    from kompas_ai.report.preview import sheet_to_pixel
    from kompas_ai.semantics.orphans import text_center

    d = _with_orphans(window, tmp_path)
    opened = []
    window.refine = lambda focus=None: opened.append(focus)
    x, y = sheet_to_pixel(d, window.page_height, 100, text_center(d.get("T2")))
    window.preview_dpi = 100
    window.on_sheet_clicked(x, y)
    window.on_sheet_clicked(0, 0)  # nothing there
    assert opened == ["T2"]
