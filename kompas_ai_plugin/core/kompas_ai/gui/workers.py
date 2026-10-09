"""Background jobs so the window stays responsive.

Recognition takes seconds, building a drawing in KOMPAS can take minutes;
both run in a QThread and report back through signals.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import pymupdf
from PySide6.QtCore import QObject, Signal

from ..pipeline import recognize_pdf
from ..report.preview import render_preview_png

PREVIEW_DPI = 150


class RecognizeJob(QObject):
    finished = Signal(object, bytes, float)  # drawing, preview png, page height (pt)
    failed = Signal(str)

    def __init__(self, pdf: Path, exact: bool, page: int = 0):
        super().__init__()
        self.pdf, self.exact, self.page = pdf, exact, page

    def run(self) -> None:
        try:
            drawing = recognize_pdf(self.pdf, self.page, exact=self.exact)
            png = render_preview_png(drawing, self.pdf, self.page, PREVIEW_DPI, legend=False)
            with pymupdf.open(str(self.pdf)) as doc:
                height = doc[self.page].rect.height
            self.finished.emit(drawing, png, height)
        except Exception:
            self.failed.emit(traceback.format_exc())


class KompasJob(QObject):
    progress = Signal(str)
    finished = Signal(str)  # report text
    failed = Signal(str)

    def __init__(self, drawing, out_cdw: Path, mode: str, with_dimensions: bool = True):
        super().__init__()
        self.drawing, self.out, self.mode = drawing, out_cdw, mode
        self.with_dimensions = with_dimensions

    def run(self) -> None:
        if sys.platform != "win32":
            self.failed.emit("Построение в КОМПАС возможно только в Windows с установленным КОМПАС-3D.")
            return
        try:
            import pythoncom

            pythoncom.CoInitialize()  # COM must be initialised in every thread that uses it
            try:
                from ..kompas.api5 import Api5Backend
                from ..kompas.writer import DrawingWriter

                self.progress.emit("Подключение к КОМПАС (первый раз — до пары минут)…")
                backend = Api5Backend(log=self.progress.emit)
                self.progress.emit("Построение объектов…")
                report = DrawingWriter(backend, mode=self.mode,
                                       with_dimensions=self.with_dimensions).write(self.drawing)
                saved = backend.save(str(self.out))
                text = report.text() + ("\n" + (f"Сохранено: {self.out}" if saved
                                                 else f"Не удалось сохранить {self.out}"))
                self.finished.emit(text)
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            self.failed.emit(traceback.format_exc())


class RevolveJob(QObject):
    """3D part (body of revolution) from the recognised drawing."""

    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, drawing, out_m3d: Path):
        super().__init__()
        self.drawing, self.out = drawing, out_m3d

    def run(self) -> None:
        if sys.platform != "win32":
            self.failed.emit("Построение в КОМПАС возможно только в Windows с установленным КОМПАС-3D.")
            return
        try:
            from ..model3d.revolve import find_revolve_profile

            profile = find_revolve_profile(self.drawing)
            if profile is None:
                self.failed.emit("Не найден профиль тела вращения: нужна осевая линия вдоль детали "
                                 "и контур (лучше — разрез со штриховкой) по одну сторону от неё.")
                return
            self.progress.emit(profile.summary())
            import pythoncom

            pythoncom.CoInitialize()
            try:
                from ..kompas.api5 import Api5Backend

                self.progress.emit("Подключение к КОМПАС…")
                backend = Api5Backend(log=self.progress.emit)
                self.progress.emit("Эскиз профиля и операция вращения…")
                saved = backend.revolve_part(profile.rings, str(self.out))
                self.finished.emit(profile.summary() + "\n" + (
                    f"3D-деталь сохранена: {self.out}" if saved else f"Не удалось сохранить {self.out}"))
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            self.failed.emit(traceback.format_exc())
