"""«Спросить ИИ»: a local model (Ollama) looks at the sheet and what was
recognised, and suggests; the user ticks what to apply. A free question
about the drawing can be asked too. The model runs in a thread — it takes
from tens of seconds to minutes on a computer without a graphics card."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QPushButton, QVBoxLayout)

from ..ai import assistant, ollama
from .widgets import label

HELP = ("Нужна Ollama с моделью, которая понимает картинки. В командной строке один раз:\n"
        f"    ollama pull {ollama.SUGGESTED}\n"
        "(на слабом компьютере — ollama pull gemma3:4b). Потом нажмите «Обновить».")


class _Call(QObject):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self.fn())
        except ollama.OllamaError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit(traceback.format_exc().strip().splitlines()[-1])


class AiDialog(QDialog):
    """``attach`` and ``overrides`` (as the sizes window has them) after
    «Применить отмеченное»."""

    def __init__(self, drawing, image: bytes | None, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Спросить ИИ")
        self.resize(760, 600)
        self.drawing, self.image, self.settings = drawing, image, settings
        self.attach: dict = {}
        self.overrides: dict = {}
        self.items: list[assistant.Suggestion] = []
        self._threads: list[QThread] = []

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        intro = label("Локальная модель ИИ посмотрит на лист и на то, что распознала программа, и "
                      "подскажет в спорных местах: к чему относятся размеры без размерной линии, "
                      "каким из противоречащих размеров верить, что за деталь. Геометрию "
                      "программа строит сама — ИИ только советует, применяете вы.", "sub")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        top = QHBoxLayout()
        top.addWidget(label("Модель:", "sub"))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setMinimumWidth(220)
        top.addWidget(self.model, 1)
        top.addWidget(label("Адрес:", "sub"))
        self.url = QLineEdit(str(settings.value("ollama_url", ollama.DEFAULT_URL)))
        self.url.setMinimumWidth(180)
        top.addWidget(self.url)
        refresh = QPushButton("Обновить", objectName="secondary")
        refresh.clicked.connect(self.load_models)
        top.addWidget(refresh)
        lay.addLayout(top)

        self.status = label("", "sub")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.status)

        self.check = QPushButton("Проверить чертёж", objectName="primary")
        self.check.clicked.connect(self.run_check)
        lay.addWidget(self.check)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        lay.addWidget(self.list, 2)

        ask = QHBoxLayout()
        self.question = QLineEdit()
        self.question.setPlaceholderText("Свой вопрос о чертеже, например: какая это деталь и "
                                         "как её изготовить?")
        self.question.returnPressed.connect(self.run_question)
        ask.addWidget(self.question, 1)
        self.ask_button = QPushButton("Спросить", objectName="secondary")
        self.ask_button.clicked.connect(self.run_question)
        ask.addWidget(self.ask_button)
        lay.addLayout(ask)
        self.answer = QPlainTextEdit(readOnly=True)
        self.answer.setPlaceholderText("Ответ появится здесь")
        lay.addWidget(self.answer, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = QPushButton("Закрыть", objectName="secondary")
        close.clicked.connect(self.reject)
        self.apply_button = QPushButton("Применить отмеченное", objectName="primary")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        bottom.addWidget(close)
        bottom.addWidget(self.apply_button)
        lay.addLayout(bottom)
        self.load_models()

    # --- the model server ---------------------------------------------------------------

    def load_models(self) -> None:
        try:
            names = ollama.models(self.url.text().strip())
        except ollama.OllamaError as exc:
            self.status.setText(f"{exc}\n\n{HELP}")
            self._ready(False)
            return
        self.model.clear()
        self.model.addItems(names)
        saved = str(self.settings.value("ollama_model", "") or "")
        pick = saved if saved in names else ollama.pick_model(names)
        if pick:
            self.model.setCurrentText(pick)
        if not names:
            self.status.setText("В Ollama нет ни одной модели.\n\n" + HELP)
        elif not ollama.sees_images(self.model.currentText()):
            self.status.setText("Выбранная модель не видит картинок — она получит только "
                                "текст распознавания. Лучше модель с картинками.\n\n" + HELP)
        else:
            self.status.setText(f"Готово: {len(names)} моделей. Проверка занимает от 20 секунд "
                                "до нескольких минут.")
        self._ready(bool(names))

    def _ready(self, ok: bool) -> None:
        self.check.setEnabled(ok)
        self.ask_button.setEnabled(ok)

    def _remember(self) -> tuple[str, str]:
        model, url = self.model.currentText().strip(), self.url.text().strip()
        self.settings.setValue("ollama_model", model)
        self.settings.setValue("ollama_url", url)
        return model, url

    def _call(self, fn, done, what: str) -> None:
        self._ready(False)
        self.status.setText(f"{what}… (модель думает, окно можно не закрывать)")
        # the thread belongs to the main window: a closed dialog does not
        # destroy a thread still waiting for the model
        thread = QThread(self.parent() or self)
        job = _Call(fn)
        job.moveToThread(thread)
        thread.started.connect(job.run)
        job.done.connect(done)
        job.failed.connect(lambda msg: self.status.setText("Не получилось: " + msg))
        for s in (job.done, job.failed):
            s.connect(thread.quit)
            s.connect(lambda *_: self._ready(True))
        thread.finished.connect(lambda: thread in self._threads and self._threads.remove(thread))
        thread._job = job  # alive while the thread runs
        self._threads.append(thread)
        thread.start()

    # --- the questions ------------------------------------------------------------------

    def run_check(self) -> None:
        model, url = self._remember()
        drawing, image = self.drawing, self.image
        self._call(lambda: assistant.ask(drawing, image, model, url), self.show_suggestions,
                   "Модель смотрит на чертёж")

    def show_suggestions(self, items) -> None:
        self.items = list(items)
        self.list.clear()
        for s in self.items:
            text = s.label + (f" — {s.why}" if s.why else "")
            item = QListWidgetItem(("" if s.applicable else "• ") + text)
            if s.applicable:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            self.list.addItem(item)
        n = sum(1 for s in self.items if s.applicable)
        self.status.setText(f"Подсказок: {len(self.items)}, из них можно применить: {n}. "
                            "Снимите галочки с тех, с чем не согласны." if self.items else
                            "Модель ничего не предложила (или ответила не по форме).")
        self.apply_button.setEnabled(n > 0)

    def run_question(self) -> None:
        q = self.question.text().strip()
        if not q:
            return
        model, url = self._remember()
        drawing, image = self.drawing, self.image
        self.answer.setPlainText("…")
        self._call(lambda: assistant.free_question(drawing, image, q, model, url),
                   lambda text: (self.answer.setPlainText(text), self.status.setText("Готово")),
                   "Модель отвечает")

    def _apply(self) -> None:
        for i, s in enumerate(self.items):
            item = self.list.item(i)
            if not s.applicable or item.checkState() != Qt.Checked:
                continue
            if s.kind == "attach":
                self.attach[s.target] = s.payload["attach"]
            elif s.kind == "value":
                self.overrides[s.target] = s.payload["value"]
        self.accept()
