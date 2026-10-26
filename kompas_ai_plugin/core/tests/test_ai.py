"""«Спросить ИИ» against a fake Ollama server: the models listed, the sheet
and the recognition sent, the answer checked against the drawing."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from test_orphans import _shaft

from kompas_ai.ai import assistant, ollama
from kompas_ai.semantics.orphans import describe

ANSWER = {
    "body": "вращения", "body_why": "ось и диаметры",
    "orphans": [{"id": "T1", "choice": 1, "why": "Ø между образующими"},
                {"id": "T2", "choice": 1, "why": "отверстие"},
                {"id": "T3", "choice": "text", "why": "надпись"},
                {"id": "T9", "choice": 1}, {"id": "T2", "choice": 7}],  # unknown / no such choice
    "notes": ["Допуск h12 на Ø26"], "questions": ["Материал детали?"],
}


@pytest.fixture()
def server():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, data):
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send({"models": [{"name": "llama3:8b"}, {"name": "qwen2.5vl:7b"}]})

        def do_POST(self):
            seen["chat"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self._send({"message": {"content": "Вот ответ:\n" + json.dumps(ANSWER)}})

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", seen
    httpd.shutdown()


def test_models_and_the_one_that_sees(server):
    url, _ = server
    names = ollama.models(url)
    assert names == ["llama3:8b", "qwen2.5vl:7b"]
    assert ollama.pick_model(names) == "qwen2.5vl:7b"


def test_no_server_is_a_clear_message():
    with pytest.raises(ollama.OllamaError, match="Ollama не отвечает"):
        ollama.models("http://127.0.0.1:9", timeout=1)


def test_suggestions_only_among_the_candidates(server):
    url, seen = server
    d = _shaft()
    d.orphans = describe(d)
    items = assistant.ask(d, b"\x89PNG fake", "qwen2.5vl:7b", url)
    chat = seen["chat"]
    assert chat["format"] == "json" and chat["messages"][-1]["images"]
    assert "Ø30-0,2" in chat["messages"][-1]["content"]  # the recognition went along
    apply = [s for s in items if s.applicable]
    assert [(s.target, s.payload["attach"]) for s in apply] == [
        ("T1", {"kind": "linear", "refs": ["L1", "L2"]}),
        ("T2", {"kind": "diameter", "refs": ["C1"]}),
        ("T3", None)]
    infos = [s.label for s in items if not s.applicable]
    assert any("тело вращения" in t for t in infos) and any("Материал" in t for t in infos)


def test_the_dialog_applies_what_is_ticked(server, monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import QApplication

    from kompas_ai.gui.ai_dialog import AiDialog

    QApplication.instance() or QApplication([])
    url, _ = server
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    settings.setValue("ollama_url", url)
    d = _shaft()
    d.orphans = describe(d)
    dialog = AiDialog(d, None, settings)
    assert dialog.model.currentText() == "qwen2.5vl:7b" and dialog.check.isEnabled()
    dialog.show_suggestions(assistant.ask(d, None, "qwen2.5vl:7b", url))
    dialog.list.item(1).setCheckState(Qt.Unchecked)  # T2: not agreed
    dialog._apply()
    assert set(dialog.attach) == {"T1", "T3"} and dialog.attach["T3"] is None


def test_too_little_memory_is_explained():
    msg = ollama.explain("model requires more system memory (12.5 GiB) than is available "
                         "(10.1 GiB)", "qwen2.5vl:7b")
    assert "12.5 ГБ" in msg and "10.1 ГБ" in msg and "qwen2.5vl:3b" in msg
