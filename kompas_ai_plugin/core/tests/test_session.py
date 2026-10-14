"""The journal file of a run and the recent drawings (gui/session.py)."""

from kompas_ai.gui.session import KEEP_LOGS, RECENT, SessionLog, recent_files, remember_file


class FakeSettings(dict):
    def value(self, key, default=None):
        return self.get(key, default)

    def setValue(self, key, value):
        self[key] = value


def test_journal_is_written_and_old_ones_go(tmp_path):
    for i in range(KEEP_LOGS + 5):
        (tmp_path / f"session-2026010{i:03d}.txt").write_text("old")
    log = SessionLog(tmp_path)
    log.write("[10:00:00] Распознавание: чертёж.pdf")
    assert log.path.read_text(encoding="utf-8").strip().endswith("чертёж.pdf")
    assert len(list(tmp_path.glob("session-*.txt"))) == KEEP_LOGS


def test_recent_files_newest_first_without_repeats(tmp_path):
    settings = FakeSettings()
    files = []
    for i in range(RECENT + 2):
        f = tmp_path / f"d{i}.pdf"
        f.write_text("x")
        files.append(f)
        remember_file(settings, f)
    remember_file(settings, files[RECENT])  # opened again: to the top, once
    got = recent_files(settings)
    assert got[0] == files[RECENT] and len(got) == RECENT and len(set(got)) == RECENT
    files[-1].unlink()  # a file gone from the disk is not offered
    assert files[-1] not in recent_files(settings)
