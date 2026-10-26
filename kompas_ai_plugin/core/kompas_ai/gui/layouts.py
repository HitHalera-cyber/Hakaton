"""Three looks of the window, one program behind them.

Every command is one QAction of the window (``win.acts``) and every control
that holds a state is one shared widget (``win.preview``, ``win.mode``…):
a layout only places them and shows the drawing's figures its own way, so
whatever one layout can do, the others can do too.

    Инженер — a CAD workplace: the drawing's contents on the left, the sheet
              with tabs in the middle, questions and building on the right.
    Мастер  — steps file → recognition → check → KOMPAS, the questions about
              sizes as cards, what will be built.
    Пульт   — a home screen with big actions and the recent drawings with
              their pictures, the drawing on its own page.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTabWidget,
                               QVBoxLayout, QWidget)

from .widgets import (ClickCard, ElidedLabel, Ring, StatCard, action_button, card, chip, label,
                      restyle)

PAGES = ["Чертёж", "Отчёт", "Проверка", "Журнал"]


def _clear(layout) -> None:
    """Every widget of a layout taken out and deleted (the lists that are
    filled again for each drawing)."""
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


def _section(text: str) -> QLabel:
    return label(text.upper(), "section")


def clamp(value: float, low: int, high: int) -> int:
    return int(max(low, min(high, value)))


class _Scroll(QScrollArea):
    """A column that scrolls down when its cards are taller than the window,
    and is never wider than itself: its content takes exactly its width, so
    the texts wrap instead of running out of sight."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.widget() is not None:
            self.widget().setFixedWidth(self.viewport().width())


def _scroll(inner: QWidget, width: int) -> QScrollArea:
    """A side column that scrolls when its cards are taller than the window:
    nothing in it is squeezed over its neighbour."""
    area = _Scroll(objectName="clear")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.viewport().setObjectName("clear")
    if not inner.objectName():  # a card keeps its own look
        inner.setObjectName("clear")
    area.setWidget(inner)
    area.setFixedWidth(width)
    return area


def _row(*widgets, stretch_at: int | None = None, spacing: int = 8) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(spacing)
    for i, w in enumerate(widgets):
        if i == stretch_at:
            row.addStretch(1)
        if w is not None:
            row.addWidget(w)
    if stretch_at is not None and stretch_at >= len(widgets):
        row.addStretch(1)
    return row


class Layout:
    """What every look provides to the window."""

    key = ""
    title = ""

    def __init__(self, win):
        self.win = win
        self.sheet_host: QWidget | None = None  # the waiting screen covers this
        self.ring: Ring | None = None

    # built once per switch; the shared widgets are moved into it
    def build(self) -> QWidget:
        raise NotImplementedError

    def show_drawing(self, info: dict | None) -> None:
        """The figures of the drawing (None: nothing open)."""

    def show_page(self, index: int) -> None:
        """One of PAGES."""

    def set_colors(self, colors: dict) -> None:
        if self.ring is not None:
            self.ring.colors = colors
            self.ring.update()

    def on_resize(self, width: int, height: int) -> None:
        """The look fitted to the window: columns in proportion, shorter
        labels on a narrow screen (a laptop, 1280 or 1024 wide)."""
        compact = width < 1300
        self.win.marks_box.setText("Нарушения" if compact else "Нарушения на листе")
        self.roomy = not compact
        if getattr(self, "contour_chip", None) is not None and compact:
            self.contour_chip.hide()
        # the format and scale are said by the sheet's own line too
        self.chip_room = width >= 1150
        sheet_chip = getattr(self, "sheet_chip", None)
        if sheet_chip is not None:
            sheet_chip.setVisible(self.chip_room and self.win.drawing is not None)
        box = self.win.layout_box  # «Вид: Инженер» → «Инженер»
        for i, (_, title) in enumerate(LAYOUT_NAMES):
            box.setItemText(i, title if compact else f"Вид: {title}")
        brand = getattr(self, "brand", None)
        if brand is not None:
            brand.setVisible(width >= 1150)
        head = getattr(self, "head", None)
        # the header's full labels only where they fit with room to spare
        # (Windows' fonts are wider than they look on another system)
        tight = width < 1500
        for key, short in (("open", "Открыть"), ("model", "По модели…"), ("theme", "icon")):
            if head and key in head and head[key].fixed_short is None:
                head[key].set_short(short if tight else None)

    # --- pieces several looks share -------------------------------------------------

    def _header_buttons(self) -> list[QWidget]:
        w = self.win
        recent = QPushButton("Недавние", objectName="secondary")
        recent.setMenu(w.recent_menu)
        recent.setCursor(Qt.PointingHandCursor)
        self.recent_button = recent
        self.head = {"model": action_button(w.acts["from_model"]),
                     "open": action_button(w.acts["open"]),
                     "theme": action_button(w.acts["theme"], "flat")}
        return [recent, self.head["model"], self.head["open"], w.layout_box, self.head["theme"]]

    def _log_page(self) -> QWidget:
        w = self.win
        frame, lay = card()
        lay.addLayout(_row(label("Журнал", "cardTitle"), None, action_button(w.acts["logs"]),
                           action_button(w.acts["check"]), action_button(w.acts["dxf"]),
                           action_button(w.acts["report"]), stretch_at=1))
        lay.addWidget(w.log, 1)
        return frame

    def _text_page(self, title: str, body: QWidget) -> QWidget:
        frame, lay = card()
        lay.addWidget(label(title, "cardTitle"))
        lay.addWidget(body, 1)
        return frame

    def _sheet_card(self) -> QFrame:
        """The sheet with its own tools above it."""
        w = self.win
        frame, lay = card()
        lay.setContentsMargins(14, 12, 14, 14)
        self.view_label = label("Чертёж", "cardTitle")
        self.contour_chip = chip("")
        self.contour_chip.hide()
        fit = action_button(w.acts["fit"], "icon", "⤢")
        fit.setToolTip("Весь лист (Ctrl+0, или двойной щелчок по листу)")
        fit.setMinimumWidth(40)
        ai = action_button(w.acts["ai"], "secondary", "ИИ…")
        ai.setToolTip("Спросить ИИ (Ctrl+I): локальная модель Ollama посмотрит на лист и "
                      "подскажет в спорных местах")
        lay.addLayout(_row(self.view_label, None, w.marks_box, self.contour_chip, fit,
                           action_button(w.acts["refine"], "secondary", "Размеры…"), ai,
                           stretch_at=1))
        lay.addWidget(w.preview, 1)
        self.sheet_host = frame
        return frame

    def _options(self, lay: QVBoxLayout) -> None:
        w = self.win
        for widget in (w.mode, w.scale_box, w.dims_box, w.param_box):
            lay.addWidget(widget)

    def _build_buttons(self, lay, vertical: bool = True) -> None:
        w = self.win
        main = action_button(w.acts["build"], "primary")
        model = action_button(w.acts["model"], "primary")
        both = action_button(w.acts["both"], "primary")
        if vertical:  # one under another: a narrow column keeps the whole words
            for b in (main, model, both):
                lay.addWidget(b)
        else:
            lay.addLayout(_row(main, model, both))

    def _show_sheet_head(self, info) -> None:
        if info is None:
            self.view_label.setText("Чертёж")
            self.contour_chip.hide()
            return
        self.view_label.setText(f"Лист {info['format']} · {info['scale']}")
        if info["exact"]:
            broken = info["issues"]
            self.contour_chip.setText("Есть нарушения" if broken else "Контур замкнут")
            restyle(self.contour_chip, "chipWarn" if broken else "chipOk")
            self.contour_chip.setVisible(getattr(self, "roomy", True))
        else:
            self.contour_chip.hide()

    def _narrow_questions(self, column: int) -> None:
        """Question buttons one under another in a column too narrow for two."""
        narrow = column < 330
        if narrow != getattr(self, "narrow_questions", False):
            self.narrow_questions = narrow
            self.show_drawing(self.win.info())

    def _questions(self, lay: QVBoxLayout, info, limit: int = 4, cards: bool = True) -> None:
        """The sizes not held, each with what can be done about it."""
        w = self.win
        _clear(lay)
        rows = info["questions"] if info else []
        if not info:
            empty = label("Откройте чертёж — здесь появятся размеры, которые нужно уточнить.",
                          "sub")
            empty.setWordWrap(True)
            lay.addWidget(empty)
            return
        if not rows:
            text = label("Вопросов нет: все размеры выдержаны точно." if info["dims"] else
                         ("На фото числа размеров не читаются — уточните формат и масштаб "
                          "или впишите числа в КОМПАС." if info["photo"] else
                          "Размеров на чертеже не найдено."), "subOk" if info["dims"] else "sub")
            text.setWordWrap(True)
            lay.addWidget(text)
            return
        for r in rows[:limit]:
            if r.get("orphan"):
                lay.addWidget(self._orphan_card(r, cards))
                continue
            box = QFrame(objectName="question" if cards else "questionFlat")
            inner = QVBoxLayout(box)
            inner.setContentsMargins(12, 10, 12, 10)
            inner.setSpacing(6)
            title = label(f"{r['id']} «{r['text']}» не выдержан", "questionTitle")
            title.setWordWrap(True)
            show = QPushButton("Показать", objectName="link")
            show.setMinimumWidth(show.fontMetrics().horizontalAdvance(show.text()) + 12)
            show.setToolTip("Показать этот размер на листе")
            show.clicked.connect(lambda _=False, i=r["id"]: w.point_at_entity(i))
            inner.addLayout(_row(title, show, spacing=6))
            lines = "—" if r["lines"] is None else f"{r['lines']:.2f}".replace(".", ",")
            note = label(f"Противоречит другим размерам; по линиям выходит {lines}.", "sub")
            note.setWordWrap(True)
            inner.addWidget(note)
            trust = QPushButton("По линиям", objectName="small")
            trust.setToolTip(f"Принять {lines} — то, что намерено по линиям")
            trust.clicked.connect(lambda _=False, i=r["id"]: w.trust_lines(i))
            own = QPushButton("Своё число…", objectName="small")
            own.setToolTip("Ввести значение этого размера самому")
            own.clicked.connect(lambda _=False, i=r["id"]: w.refine(i))
            for b in (trust, own, show):
                b.setCursor(Qt.PointingHandCursor)
                b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)  # whole words
            if getattr(self, "narrow_questions", False):  # one under another
                inner.addWidget(trust)
                inner.addWidget(own)
            else:
                inner.addLayout(_row(trust, own, stretch_at=2))
            lay.addWidget(box)
        if len(rows) > limit:
            more = QPushButton(f"Ещё {len(rows) - limit}…", objectName="flat")
            more.clicked.connect(lambda: w.refine())
            lay.addWidget(more)


    def _orphan_card(self, r: dict, cards: bool) -> QFrame:
        """A number without a dimension line: what it may measure, best first."""
        w = self.win
        box = QFrame(objectName="question" if cards else "questionFlat")
        inner = QVBoxLayout(box)
        inner.setContentsMargins(12, 10, 12, 10)
        inner.setSpacing(6)
        title = label(f"«{r['text']}» — размер без размерной линии", "questionTitle")
        title.setWordWrap(True)
        show = QPushButton("Показать на листе", objectName="link")
        show.setToolTip("Показать это число на листе")
        show.clicked.connect(lambda _=False, i=r["id"]: w.point_at_entity(i))
        inner.addWidget(title)  # the link under it: a long number wraps, the link stays whole
        cands = r["candidates"]
        note = label("Что он измеряет? Размер будет построен и выдержан." if cands else
                     "Подходящих линий не найдено — выберите в таблице или оставьте текстом.",
                     "sub")
        note.setWordWrap(True)
        inner.addWidget(note)
        picks = []
        for k, c in enumerate(cands[:2]):
            b = QPushButton(c["short"], objectName="small")
            b.setToolTip(c["label"])
            b.clicked.connect(lambda _=False, i=r["id"], k=k: w.attach_orphan(i, k))
            picks.append(b)
        more = QPushButton("Другое…", objectName="small")
        more.setToolTip("Все варианты — в таблице размеров")
        more.clicked.connect(lambda _=False, i=r["id"]: w.refine(i))
        text = QPushButton("Это текст", objectName="small")
        text.setToolTip("Оставить надписью, размер не строить")
        text.clicked.connect(lambda _=False, i=r["id"]: w.attach_orphan(i, None))
        for b in picks + [more, text, show]:
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        for b in picks:  # each on its own line: the labels are long
            inner.addWidget(b)
        if getattr(self, "narrow_questions", False):
            inner.addWidget(more)
            inner.addWidget(text)
        else:
            inner.addLayout(_row(more, text, stretch_at=2))
        inner.addLayout(_row(show, stretch_at=1))
        return box


# --- А · Инженер --------------------------------------------------------------------------

class Engineer(Layout):
    key = "engineer"
    title = "Инженер"

    def build(self) -> QWidget:
        w = self.win
        root = QWidget(objectName="root")
        col = QVBoxLayout(root)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        bar = QFrame(objectName="topbar")
        top = QHBoxLayout(bar)
        top.setContentsMargins(16, 10, 16, 10)
        top.setSpacing(10)
        self.brand = label(w.app_name, "topBrand")
        top.addWidget(self.brand)
        self.title = ElidedLabel("Чертёж не открыт", "topTitle")
        top.addWidget(self.title, 1)
        self.sheet_chip = chip("")
        self.sheet_chip.hide()
        top.addWidget(self.sheet_chip)
        for b in self._header_buttons():
            top.addWidget(b)
        col.addWidget(bar)

        body = QHBoxLayout()
        body.setContentsMargins(14, 14, 14, 8)
        body.setSpacing(14)

        left, ll = card("panel")
        left.setFixedWidth(280)
        self.left = left
        ll.addWidget(_section("Состав чертежа"))
        self.contents = QVBoxLayout()
        self.contents.setSpacing(4)
        ll.addLayout(self.contents)
        ll.addSpacing(8)
        ll.addWidget(_section("Точность"))
        self.ring = Ring()
        self.ring_note = label("откройте чертёж", "sub")
        self.ring_note.setWordWrap(True)
        ll.addLayout(_row(self.ring, self.ring_note, spacing=12))
        ll.addSpacing(8)
        ll.addWidget(_section("Параметры"))
        self.left_options = QVBoxLayout()
        self.left_options.setSpacing(8)
        ll.addLayout(self.left_options)
        self._options(self.left_options)
        ll.addStretch(1)
        ll.addWidget(w.kompas_note)
        body.addWidget(left)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._sheet_card(), "Чертёж")
        self.tabs.addTab(self._text_page("Результат распознавания", w.summary), "Отчёт")
        self.tabs.addTab(self._text_page("Нарушения и объекты под вопросом — щёлкните, покажу "
                                         "на листе", w.review), "Проверка")
        self.tabs.addTab(self._log_page(), "Журнал")
        body.addWidget(self.tabs, 1)

        right, rl = card("panel")
        rl.addWidget(_section("3D-модель"))
        self.verdict = label("откройте чертёж", "sub")
        self.verdict.setWordWrap(True)
        rl.addWidget(self.verdict)
        rl.addSpacing(6)
        rl.addWidget(_section("Уточнить размеры"))
        self.question_box = QVBoxLayout()
        self.question_box.setSpacing(6)
        rl.addLayout(self.question_box)
        rl.addWidget(action_button(w.acts["refine"], "secondary", "Все размеры…"))
        rl.addSpacing(6)
        # the options come here when the window is too narrow for the left panel
        self.right_options_title = _section("Параметры")
        self.right_options_title.hide()
        rl.addWidget(self.right_options_title)
        self.right_options = QVBoxLayout()
        self.right_options.setSpacing(8)
        rl.addLayout(self.right_options)
        rl.addWidget(_section("Нарушения"))
        self.issue_box = QVBoxLayout()
        self.issue_box.setSpacing(4)
        rl.addLayout(self.issue_box)
        rl.addStretch(1)
        self._build_buttons(rl)
        self.right_scroll = _scroll(right, 330)
        body.addWidget(self.right_scroll)
        col.addLayout(body, 1)

        foot = QFrame(objectName="footbar")
        self.chips = QHBoxLayout(foot)
        self.chips.setContentsMargins(16, 6, 16, 6)
        self.chips.setSpacing(6)
        col.addWidget(foot)
        self.show_drawing(None)
        return root

    def show_page(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        narrow = width < 1200
        if narrow != getattr(self, "narrow", None):
            # a narrow screen: the drawing's contents and the ring go (their
            # figures are in the line below the sheet), the options move right
            self.narrow = narrow
            self._options(self.right_options if narrow else self.left_options)
            self.left.setVisible(not narrow)
            self.right_options_title.setVisible(narrow)
        self.left.setFixedWidth(clamp(width * 0.2, 255, 300))
        column = clamp(width * (0.3 if narrow else 0.23), 280, 380)
        self.right_scroll.setFixedWidth(column)
        self._narrow_questions(column)

    def show_drawing(self, info) -> None:
        w = self.win
        self.title.setText(info["name"] if info else (w.pdf.name if w.pdf else "Чертёж не открыт"))
        if info:
            self.sheet_chip.setText(f"{info['format']} · {info['scale']}")
            self.sheet_chip.setVisible(getattr(self, "chip_room", True))
        else:
            self.sheet_chip.hide()
        self._show_sheet_head(info)
        _clear(self.contents)
        for name, count in (info["counts"] if info else []):
            self.contents.addLayout(_row(label(name), label(str(count), "mono"), stretch_at=1))
        if not info:
            self.contents.addWidget(label("—", "sub"))
        if info and info["dims"]:
            self.ring.set_value(info["held"], info["dims"])
            self.ring_note.setText("размеры выдержаны точно" if info["held"] == info["dims"]
                                   else f"не выдержано: {info['dims'] - info['held']}")
        else:
            self.ring.set_value(0, 0)
            self.ring_note.setText("размеров нет" if info else "откройте чертёж")
        self.verdict.setText(info["model_text"] if info else "откройте чертёж")
        restyle(self.verdict, "subWarn" if info and info["model_ok"] is False else "sub")
        self._questions(self.question_box, info, limit=3, cards=False)
        _clear(self.issue_box)
        issues = info["issue_list"] if info else []
        for number, text in issues[:5]:
            b = ClickCard("issueCard")  # the text wraps in a narrow column
            bl = QVBoxLayout(b)
            bl.setContentsMargins(10, 6, 10, 6)
            t = label(f"{number}. {text}", "issueText")
            t.setWordWrap(True)
            bl.addWidget(t)
            b.setToolTip("Показать на листе")
            b.clicked.connect(lambda t=text: w.point_at_issue(t))
            self.issue_box.addWidget(b)
        if info and len(issues) > 5:
            more = QPushButton(f"все {len(issues)}…", objectName="flat")
            more.clicked.connect(lambda: self.show_page(2))
            self.issue_box.addWidget(more)
        if info and not issues:
            self.issue_box.addWidget(label("нет — контур без нарушений" if info["exact"]
                                           else "выравнивание выключено", "subOk"))
        self.tabs.setTabText(2, f"Проверка · {info['to_check']}" if info and info["to_check"]
                             else "Проверка")
        _clear(self.chips)
        if info:
            for text, state in info["chips"]:
                self.chips.addWidget(chip(text, state))
            self.chips.addStretch(1)
            self.chips.addWidget(label(f"{info['objects']} объектов", "sub"))
        else:
            self.chips.addWidget(label("Откройте PDF или фото чертежа (Ctrl+O) или перетащите "
                                       "файл в окно", "sub"))


# --- Б · Мастер ---------------------------------------------------------------------------

STEPS = [("Файл", "PDF или фото"), ("Распознавание", "линии и размеры"),
         ("Проверка", "вопросы по размерам"), ("КОМПАС", "чертёж и модель")]


class Wizard(Layout):
    key = "wizard"
    title = "Мастер"

    def build(self) -> QWidget:
        w = self.win
        root = QWidget(objectName="root")
        col = QVBoxLayout(root)
        col.setContentsMargins(20, 16, 20, 8)
        col.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(10)
        self.brand = label(w.app_name, "brand")
        head.addWidget(self.brand)
        self.title = ElidedLabel("Чертёж не открыт", "title")
        head.addWidget(self.title, 1)
        self.sheet_chip = chip("")
        self.sheet_chip.hide()
        head.addWidget(self.sheet_chip)
        for b in self._header_buttons():
            head.addWidget(b)
        col.addLayout(head)

        steps = QGridLayout()
        steps.setSpacing(10)
        self.steps = []
        for i, (name, note) in enumerate(STEPS):
            frame = QFrame(objectName="step")
            lay = QHBoxLayout(frame)
            lay.setContentsMargins(14, 10, 14, 10)
            lay.setSpacing(12)
            badge = label(str(i + 1), "stepBadge")
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(30, 30)
            text = QVBoxLayout()
            text.setSpacing(0)
            title = label(f"{i + 1}. {name}", "stepTitle")
            sub = label(note, "sub")
            text.addWidget(title)
            text.addWidget(sub)
            lay.addWidget(badge)
            lay.addLayout(text, 1)
            steps.addWidget(frame, 0, i)
            self.steps.append((frame, badge, sub))
        col.addLayout(steps)

        body = QHBoxLayout()
        body.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(10)
        seg = QHBoxLayout()
        seg.setSpacing(4)
        self.seg = QButtonGroup(root)
        for i, name in enumerate(["Лист", "Отчёт", "Проверка", "Журнал"]):
            b = QPushButton(name, objectName="seg", checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            self.seg.addButton(b, i)
            seg.addWidget(b)
        seg.addStretch(1)
        self.seg.button(0).setChecked(True)
        left.addLayout(seg)
        self.stack = QStackedWidget()
        sheet = self._sheet_card()
        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.figures = {}
        for key, name in (("dims", "Размеров"), ("held", "Выдержано точно"),
                          ("conflicts", "Противоречат"), ("issues", "Нарушений контура")):
            box = QFrame(objectName="mini")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 8, 12, 8)
            bl.setSpacing(0)
            bl.addWidget(label(name, "sub"))
            value = label("—", "miniValue")
            bl.addWidget(value)
            stats.addWidget(box)
            self.figures[key] = value
        sheet.layout().addLayout(stats)
        self.stack.addWidget(sheet)
        self.stack.addWidget(self._text_page("Результат распознавания", w.summary))
        self.stack.addWidget(self._text_page("Нарушения и объекты под вопросом — щёлкните, "
                                             "покажу на листе", w.review))
        self.stack.addWidget(self._log_page())
        self.seg.idClicked.connect(self.stack.setCurrentIndex)
        left.addWidget(self.stack, 1)
        body.addLayout(left, 1)

        side = QWidget()
        right = QVBoxLayout(side)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(14)
        ask, al = card()
        al.addWidget(label("Вопросы перед построением", "cardHead"))
        self.question_box = QVBoxLayout()
        self.question_box.setSpacing(8)
        al.addLayout(self.question_box)
        self.all_sizes = action_button(w.acts["refine"], "secondary", "Уточнить все размеры…")
        al.addWidget(self.all_sizes)
        right.addWidget(ask)
        out, ol = card()
        ol.addWidget(label("Что получится в КОМПАС", "cardHead"))
        self.verdict = label("откройте чертёж", "sub")
        self.verdict.setWordWrap(True)
        ol.addWidget(self.verdict)
        self._options(ol)
        ol.addStretch(1)
        self._build_buttons(ol)
        right.addWidget(out, 1)
        self.side_scroll = _scroll(side, 440)
        body.addWidget(self.side_scroll)
        col.addLayout(body, 1)
        self.show_drawing(None)
        return root

    def show_page(self, index: int) -> None:
        self.seg.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        column = clamp(width * 0.3, 300, 470)
        self.side_scroll.setFixedWidth(column)
        self.all_sizes.set_short("Все размеры…" if column < 400 else None)
        self._narrow_questions(column - 40)
        for _, _, sub in self.steps:  # the steps' second lines only where they fit
            sub.setVisible(width >= 1150)

    def show_drawing(self, info) -> None:
        w = self.win
        self.title.setText(info["name"] if info else (w.pdf.name if w.pdf else "Чертёж не открыт"))
        if info:
            self.sheet_chip.setText(f"{info['format']} · {info['scale']}")
            self.sheet_chip.setVisible(getattr(self, "chip_room", True))
        else:
            self.sheet_chip.hide()
        self._show_sheet_head(info)
        conflicts = len(info["questions"]) if info else 0
        states = ["done" if w.pdf else "now",
                  "done" if info else ("now" if w.pdf else "todo"),
                  ("now" if conflicts or (info and info["issues"]) else "done") if info else "todo",
                  "now" if info and not conflicts else "todo"]
        notes = [w.pdf.name if w.pdf else "PDF или фото",
                 f"{info['objects']} объектов" if info else "линии и размеры",
                 (f"вопросов: {conflicts}" if conflicts else
                  f"нарушений: {info['issues']}" if info["issues"] else "всё точно") if info
                 else "вопросы по размерам",
                 "можно строить" if info else "чертёж и модель"]
        for (frame, badge, sub), state, note in zip(self.steps, states, notes):
            restyle(frame, {"done": "stepDone", "now": "stepNow"}.get(state, "step"))
            restyle(badge, {"done": "stepBadgeDone", "now": "stepBadgeNow"}.get(state, "stepBadge"))
            badge.setText("✓" if state == "done" else str(self.steps.index((frame, badge, sub)) + 1))
            sub.setText(note)
        if info:
            self.figures["dims"].setText(str(info["dims"]))
            self.figures["held"].setText(str(info["held"]))
            self.figures["conflicts"].setText(str(conflicts))
            self.figures["issues"].setText(str(info["issues"]) if info["exact"] else "—")
        else:
            for v in self.figures.values():
                v.setText("—")
        self.seg.button(2).setText(f"Проверка · {info['to_check']}" if info and info["to_check"]
                                   else "Проверка")
        self.verdict.setText(info["model_text"] if info else "Откройте чертёж: здесь будет, что "
                             "построится — лист и деталь.")
        restyle(self.verdict, "subWarn" if info and info["model_ok"] is False else "sub")
        self._questions(self.question_box, info, limit=3)


# --- В · Пульт ----------------------------------------------------------------------------

class Console(Layout):
    key = "console"
    title = "Пульт"
    NAV = ["Главная", "Чертёж", "Отчёт", "Проверка", "Журнал"]

    def build(self) -> QWidget:
        w = self.win
        root = QWidget(objectName="root")
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QFrame(objectName="rail")
        side.setFixedWidth(230)
        self.rail = side
        sl = QVBoxLayout(side)
        sl.setContentsMargins(16, 20, 16, 16)
        sl.setSpacing(6)
        sl.addWidget(label(w.app_name, "brand"))
        sl.addSpacing(16)
        self.nav = QButtonGroup(root)
        for i, name in enumerate(self.NAV):
            b = QPushButton(name, objectName="nav", checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            self.nav.addButton(b, i)
            sl.addWidget(b)
        self.nav.button(0).setChecked(True)
        self.nav.idClicked.connect(self._go)
        sl.addStretch(1)
        sl.addWidget(w.layout_box)
        self.head = {"theme": action_button(w.acts["theme"], "flat")}
        self.head["theme"].set_short("icon+Тема")  # a narrow menu: «☾  Тема»
        sl.addWidget(self.head["theme"])
        sl.addWidget(w.kompas_note)
        lay.addWidget(side)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._home())
        self.stack.addWidget(self._drawing())
        self.stack.addWidget(self._padded(self._text_page("Результат распознавания", w.summary)))
        self.stack.addWidget(self._padded(self._text_page(
            "Нарушения и объекты под вопросом — щёлкните, покажу на листе", w.review)))
        self.stack.addWidget(self._padded(self._log_page()))
        lay.addWidget(self.stack, 1)
        self.show_drawing(None)
        if w.pdf is not None:
            self._go(1)
        return root

    def _padded(self, inner: QWidget) -> QWidget:
        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(24, 24, 24, 12)
        pl.addWidget(inner)
        return page

    def _go(self, index: int) -> None:
        self.nav.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)
        if index == 0:
            self._fill_recent()

    def show_page(self, index: int) -> None:
        self._go(index + 1)

    recent_cols = 3

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        narrow = width < 1300
        self.rail_base = 170 if narrow else 230
        self._fit_rail()
        self.side_scroll.setFixedWidth(clamp(width * 0.3, 320, 390))
        self.rules_card.set_title("Контур" if narrow else "Правила контура")
        self.info_card.setFixedWidth(clamp(width * 0.22, 240, 330))
        cols = 2 if narrow else 4
        if cols != self.tile_cols:  # the big actions in two rows on a narrow screen
            self.tile_cols = cols
            for i, tile in enumerate(self.tiles):
                self.tile_grid.addWidget(tile, i // cols, i % cols)
        cols = 2 if width < 1400 else 3
        if cols != self.recent_cols:
            self.recent_cols = cols
            self._fill_recent()

    def _fit_rail(self) -> None:
        """The rail as narrow as the window wants, but no tab cut («Проверка · 12»)."""
        need = max(b.sizeHint().width() for b in self.nav.buttons()) + 32  # rail margins
        self.rail.setFixedWidth(max(getattr(self, "rail_base", 230), need))

    def _home(self) -> QWidget:
        w = self.win
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(28, 26, 28, 12)
        col.setSpacing(18)
        col.addWidget(label("Добрый день" if 9 <= time.localtime().tm_hour < 18 else "Здравствуйте",
                            "sub"))
        col.addWidget(label("С какого чертежа начнём?", "title"))
        tiles = QGridLayout()
        tiles.setSpacing(14)
        self.tiles, self.tile_grid, self.tile_cols = [], tiles, 4
        for i, (key, text, note) in enumerate((
                ("open", "Открыть PDF", "или перетащите файл в окно"),
                ("photo", "Чертёж с фото", "телефон, скан, скриншот"),
                ("from_model", "Чертёж по модели", "из файла .m3d"),
                ("check", "Проверить КОМПАС", "таблицы и связанные виды"))):
            b = ClickCard("tile")
            tl = QVBoxLayout(b)
            tl.setContentsMargins(16, 14, 16, 14)
            tl.setSpacing(4)
            tl.addWidget(label(text, "tileTitle"))
            tl.addWidget(label(note, "sub"))
            act = w.acts[key]
            b._action = act  # the command it stands for
            b.setToolTip(act.toolTip() if act.toolTip() != act.text() else "")
            b.clicked.connect(act.trigger)
            b.setEnabled(act.isEnabled())
            act.enabledChanged.connect(b.setEnabled)
            b.setMinimumHeight(80)
            tiles.addWidget(b, 0, i)
            self.tiles.append(b)
        col.addLayout(tiles)
        body = QHBoxLayout()
        body.setSpacing(20)
        recent = QVBoxLayout()
        recent.addWidget(label("Недавние чертежи", "cardHead"))
        self.recent_grid = QGridLayout()
        self.recent_grid.setSpacing(14)
        holder = QWidget(objectName="clear")
        holder.setLayout(self.recent_grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("clear")
        scroll.viewport().setObjectName("clear")
        scroll.setWidget(holder)
        recent.addWidget(scroll, 1)
        body.addLayout(recent, 1)
        info, il = card()
        info.setFixedWidth(300)
        self.info_card = info
        il.addWidget(label("Этот запуск", "cardHead"))
        self.session_figures = {}
        grid = QGridLayout()
        for i, (key, name) in enumerate((("opened", "открыто"), ("built", "построено"),
                                         ("refined", "уточнено размеров"), ("photos", "с фото"))):
            v = label("0", "miniValue")
            box = QVBoxLayout()
            box.setSpacing(0)
            box.addWidget(v)
            box.addWidget(label(name, "sub"))
            grid.addLayout(box, i // 2, i % 2)
            self.session_figures[key] = v
        il.addLayout(grid)
        il.addSpacing(8)
        tip = label("Совет: фото лучше снимать сверху при ровном свете. Рамка и штамп с фото "
                    "заменятся листом КОМПАС, а масштаб возьмётся из рамки.", "sub")
        tip.setWordWrap(True)
        il.addWidget(tip)
        il.addStretch(1)
        body.addWidget(info)
        col.addLayout(body, 1)
        return page

    def _fill_recent(self) -> None:
        w = self.win
        _clear(self.recent_grid)
        paths = w.recent_paths()
        if not paths:
            self.recent_grid.addWidget(label("Пока пусто — откройте первый чертёж.", "sub"), 0, 0)
            return
        for i, path in enumerate(paths[:6]):
            b = ClickCard()
            b.setToolTip(str(path))
            bl = QVBoxLayout(b)
            bl.setContentsMargins(0, 0, 0, 10)
            bl.setSpacing(6)
            pic = QLabel(objectName="thumb")
            pic.setAlignment(Qt.AlignCenter)
            pic.setFixedHeight(130)
            pix = thumbnail(path, 240, 130)
            if pix is not None:
                pic.setPixmap(pix)
            bl.addWidget(pic)
            name = ElidedLabel(path.name, "thumbName")
            name.setContentsMargins(12, 0, 12, 0)
            bl.addWidget(name)
            when = label(time.strftime("%d.%m %H:%M", time.localtime(path.stat().st_mtime))
                         + (" · фото" if path.suffix.lower() != ".pdf" else ""), "sub")
            when.setContentsMargins(12, 0, 12, 0)
            bl.addWidget(when)
            b.setFixedHeight(200)
            b.clicked.connect(lambda p=path: w.open_file(p))
            cols = self.recent_cols
            self.recent_grid.addWidget(b, i // cols, i % cols)
        for c in range(3):
            self.recent_grid.setColumnStretch(c, 1 if c < self.recent_cols else 0)
        self.recent_grid.setRowStretch(self.recent_grid.rowCount(), 1)

    def _drawing(self) -> QWidget:
        w = self.win
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(24, 20, 24, 8)
        col.setSpacing(14)
        head = QHBoxLayout()
        self.title = ElidedLabel("Чертёж не открыт", "title")
        head.addWidget(self.title, 1)
        self.sheet_chip = chip("")
        self.sheet_chip.hide()
        head.addWidget(self.sheet_chip)
        recent = QPushButton("Недавние", objectName="secondary")
        recent.setMenu(w.recent_menu)
        self.recent_button = recent
        head.addWidget(recent)
        head.addWidget(action_button(w.acts["open"]))
        col.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self._sheet_card(), 1)
        side = QWidget()
        right = QVBoxLayout(side)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)
        figures = QHBoxLayout()
        figures.setSpacing(12)
        self.rules_card = StatCard("Правила контура")
        self.rules_card.setCursor(Qt.PointingHandCursor)
        self.rules_card.clicked.connect(lambda: self._go(3))
        self.dims_card = StatCard("Размеров")
        self.dims_card.setCursor(Qt.PointingHandCursor)
        self.dims_card.clicked.connect(lambda: w.refine())
        figures.addWidget(self.rules_card)
        figures.addWidget(self.dims_card)
        right.addLayout(figures)
        build, bl = card()
        bl.addWidget(label("Построение", "cardHead"))
        self.verdict = label("откройте чертёж", "sub")
        self.verdict.setWordWrap(True)
        bl.addWidget(self.verdict)
        self.question_box = QVBoxLayout()  # sizes not held, numbers without their line
        self.question_box.setSpacing(6)
        bl.addLayout(self.question_box)
        self._options(bl)
        bl.addWidget(action_button(w.acts["refine"]))
        bl.addStretch(1)
        self._build_buttons(bl)
        right.addWidget(build, 1)
        self.side_scroll = _scroll(side, 350)
        body.addWidget(self.side_scroll)
        col.addLayout(body, 1)
        return page

    def show_drawing(self, info) -> None:
        w = self.win
        self.title.setText(info["name"] if info else (w.pdf.name if w.pdf else "Чертёж не открыт"))
        if info:
            self.sheet_chip.setText(f"{info['format']} · {info['scale']}")
            self.sheet_chip.setVisible(getattr(self, "chip_room", True))
        else:
            self.sheet_chip.hide()
        self._show_sheet_head(info)
        if info:
            if info["exact"]:
                self.rules_card.set_value(str(info["issues"]),
                                          "нарушений" if info["issues"] else "контур точный",
                                          "warn" if info["issues"] else "ok")
            else:
                self.rules_card.set_value("—", "выравнивание выключено")
            n = len(info["questions"])
            self.dims_card.set_value(str(info["dims"]), f"уточнить: {n}" if n else
                                     ("все выдержаны" if info["dims"] else "на листе нет"),
                                     "warn" if n else "ok")
        else:
            self.rules_card.set_value("—", "откройте чертёж")
            self.dims_card.set_value("—", "откройте чертёж")
        self.verdict.setText(info["model_text"] if info else "откройте чертёж")
        restyle(self.verdict, "subWarn" if info and info["model_ok"] is False else "sub")
        if info and info["questions"]:
            self._questions(self.question_box, info, limit=2, cards=False)
        else:
            _clear(self.question_box)
        self.nav.button(3).setText(f"Проверка · {info['to_check']}" if info and info["to_check"]
                                   else "Проверка")
        self._fit_rail()
        for key, v in self.session_figures.items():
            v.setText(str(w.counters.get(key, 0)))
        if self.stack.currentIndex() == 0:
            self._fill_recent()


LAYOUTS = {cls.key: cls for cls in (Engineer, Wizard, Console)}
LAYOUT_NAMES = [(cls.key, cls.title) for cls in (Engineer, Wizard, Console)]

_THUMBS: dict = {}


def thumbnail(path: Path, width: int, height: int) -> QPixmap | None:
    """A small picture of a drawing's first page (or of the photo), kept for
    the run."""
    try:
        key = (str(path), path.stat().st_mtime, width, height)
    except OSError:
        return None
    if key in _THUMBS:
        return _THUMBS[key]
    pix = None
    try:
        if path.suffix.lower() == ".pdf":
            import pymupdf

            with pymupdf.open(str(path)) as doc:
                page = doc[0]
                zoom = min(width / page.rect.width, height / page.rect.height) * 2
                png = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")
            image = QImage.fromData(png, "PNG")
        else:
            image = QImage(str(path))
        if not image.isNull():
            pix = QPixmap.fromImage(image.scaled(width, height, Qt.KeepAspectRatio,
                                                 Qt.SmoothTransformation))
    except Exception:  # a picture is a nicety: a broken file only has none
        pix = None
    _THUMBS[key] = pix
    return pix

