"""Names used but never defined (a NameError only KOMPAS would have shown)."""

from pathlib import Path

import pytest


def test_no_undefined_names():
    pyflakes = pytest.importorskip("pyflakes.api")
    from pyflakes import messages
    from pyflakes.reporter import Reporter

    class Collect(Reporter):
        def __init__(self):
            self.found = []

        def flake(self, message):
            if isinstance(message, (messages.UndefinedName, messages.UndefinedLocal)):
                self.found.append(str(message))

        def unexpectedError(self, filename, msg):
            self.found.append(f"{filename}: {msg}")

        def syntaxError(self, filename, msg, lineno, offset, text):
            self.found.append(f"{filename}:{lineno}: {msg}")

    rep = Collect()
    root = Path(__file__).resolve().parents[1] / "kompas_ai"
    for path in root.rglob("*.py"):
        pyflakes.check(path.read_text(encoding="utf-8"), str(path), rep)
    assert rep.found == []
