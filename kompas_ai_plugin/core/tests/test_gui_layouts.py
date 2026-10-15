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
