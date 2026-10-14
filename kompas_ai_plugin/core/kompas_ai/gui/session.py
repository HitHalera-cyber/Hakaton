"""What the window keeps between runs and leaves behind for a bug report:
the program's folder, the journal of each run as a file, the recently
opened drawings.

    %APPDATA%/KompasAI/            (the home folder elsewhere)
        logs/session-YYYYMMDD-HHMMSS.txt   — the journal, one file per run
        crash.log, kompas_check.txt, plane_axes.json
"""

from __future__ import annotations

import os
import time
from pathlib import Path

KEEP_LOGS = 20  # journals of the last runs kept
RECENT = 8  # drawings in the «Недавние» list


def app_folder() -> Path:
    folder = Path(os.environ.get("APPDATA") or Path.home()) / "KompasAI"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


class SessionLog:
    """The journal of this run, line by line, into a file: what to send when
    something goes wrong (a screenshot shows only the end of it)."""

    def __init__(self, folder: Path | None = None):
        self.folder = folder or app_folder() / "logs"
        self.path: Path | None = None
        self._file = None
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            old = sorted(self.folder.glob("session-*.txt"))
            for p in old[:max(0, len(old) - KEEP_LOGS + 1)]:
                p.unlink(missing_ok=True)
            self.path = self.folder / time.strftime("session-%Y%m%d-%H%M%S.txt")
            self._file = open(self.path, "a", encoding="utf-8")
        except OSError:
            self._file = None  # no journal file: the window works without it

    def write(self, text: str) -> None:
        if self._file is None:
            return
        try:
            self._file.write(text.rstrip("\n") + "\n")
            self._file.flush()
        except OSError:
            pass


def stamped(text: str) -> str:
    """A journal line with the time it was written."""
    return time.strftime("[%H:%M:%S] ") + text


def recent_files(settings) -> list[Path]:
    """The drawings opened last, newest first, those still on disk."""
    raw = settings.value("recent", []) or []
    if isinstance(raw, str):  # QSettings gives one value as a plain string
        raw = [raw]
    return [Path(p) for p in raw if Path(p).exists()][:RECENT]


def remember_file(settings, path: Path) -> list[Path]:
    paths = [path] + [p for p in recent_files(settings) if p != path]
    settings.setValue("recent", [str(p) for p in paths[:RECENT]])
    return paths[:RECENT]
