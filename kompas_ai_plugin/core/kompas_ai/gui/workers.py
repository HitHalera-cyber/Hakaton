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

from .. import ir
from ..pipeline import recognize_pdf
from ..report.preview import render_preview_png

PREVIEW_DPI = 150
PREVIEW_STAGE = "Рисую предпросмотр"


class RecognizeJob(QObject):
    finished = Signal(object, bytes, float)  # drawing, preview png, page height (pt)
    failed = Signal(str)
    stage = Signal(str)  # one of pipeline.STAGES, then PREVIEW_STAGE

    def __init__(self, pdf: Path, exact: bool, page: int = 0):
        super().__init__()
        self.pdf, self.exact, self.page = pdf, exact, page

    def run(self) -> None:
        try:
            try:
                drawing = recognize_pdf(self.pdf, self.page, exact=self.exact,
                                        progress=self.stage.emit)
            except Exception:
                if not self.exact:
                    raise
                # the drawing opens anyway: as in the PDF, without the exact fitting
                error = traceback.format_exc().strip().splitlines()[-1]
                drawing = recognize_pdf(self.pdf, self.page, exact=False,
                                        progress=self.stage.emit)
                drawing.warnings.insert(0, "Точный режим не удался, чертёж открыт как в PDF "
                                           f"(без выравнивания): {error}")
            self.stage.emit(PREVIEW_STAGE)
            png = render_preview_png(drawing, self.pdf, self.page, PREVIEW_DPI, legend=False)
            with pymupdf.open(str(self.pdf)) as doc:
                height = doc[self.page].rect.height
            self.finished.emit(drawing, png, height)
        except Exception:
            self.failed.emit(traceback.format_exc())


class KompasJob(QObject):
    """The drawing in KOMPAS: a view at the drawing's scale, the part in true
    millimetres (KOMPAS measures the sizes itself; a number the PDF writes
    differently is written as in the PDF)."""

    progress = Signal(str)
    finished = Signal(str)  # report text
    failed = Signal(str)

    def __init__(self, drawing, out_cdw: Path, with_dimensions: bool = True):
        super().__init__()
        self.drawing, self.out = drawing, out_cdw
        self.with_dimensions = with_dimensions

    def run(self) -> None:
        if sys.platform != "win32":
            self.failed.emit("Построение в КОМПАС возможно только в Windows с установленным КОМПАС-3D.")
            return
        try:
            import pythoncom

            pythoncom.CoInitialize()  # COM must be initialised in every thread that uses it
            try:
                self.finished.emit(write_drawing(self.drawing, self.out, self.with_dimensions,
                                                 self.progress.emit))
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            self.failed.emit(traceback.format_exc())


def write_drawing(drawing, out: Path, with_dimensions: bool, log, model: Path | None = None,
                  model_size=None) -> str:
    """The drawing built and saved; with ``model`` (a saved part) a view of
    that part is put on the sheet too, linked to it."""
    from ..kompas.api5 import Api5Backend
    from ..kompas.writer import DrawingWriter, free_spot

    log("Подключение к КОМПАС (первый раз — до пары минут)…")
    # the drawing is not parametrised: constraints only ever move its lines
    backend = Api5Backend(log=log, parametric=False)
    log("Построение объектов…")
    report = DrawingWriter(backend, mode="view", with_dimensions=with_dimensions).write(drawing)
    text = report.text()
    if model is not None:
        try:
            length, diameter = model_size or (50.0, 50.0)
            spot = free_spot(drawing, max(length, diameter))
            if spot is None:
                log("На листе нет свободного места для вида модели — пропущен")
            else:
                (x, y), scale = spot
                ok = backend.model_view(str(model), (x, y), scale)
                text += "\n" + (f"Вид модели (изометрия, {scale:g}:1 → связан с {model.name})"
                                 if ok else "Вид модели не создан")
        except Exception as exc:
            text += f"\nВид модели не создан: {exc!r}"
    saved = backend.save(str(out))
    return text + "\n" + (f"Сохранено: {out}" if saved else f"Не удалось сохранить {out}")


class RevolveJob(QObject):
    """3D part (body of revolution) from the recognised drawing."""

    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, drawing, out_m3d: Path, exact: bool = True, parametric: bool = True):
        super().__init__()
        self.drawing, self.out, self.exact = drawing, out_m3d, exact
        self.parametric = parametric

    def run(self) -> None:
        if sys.platform != "win32":
            self.failed.emit("Построение в КОМПАС возможно только в Windows с установленным КОМПАС-3D.")
            return
        try:
            import pythoncom

            pythoncom.CoInitialize()
            try:
                text, _, _ = make_model(self.drawing, self.out, self.exact, self.parametric,
                                        self.progress.emit)
                self.finished.emit(text)
            finally:
                pythoncom.CoUninitialize()
        except Exception as exc:
            self.failed.emit(str(exc) if isinstance(exc, ModelError) else traceback.format_exc())


class BothJob(QObject):
    """The model, then the drawing with a view linked to it."""

    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, drawing, out_cdw: Path, exact: bool = True, parametric: bool = True,
                 with_dimensions: bool = True):
        super().__init__()
        self.drawing, self.out, self.exact = drawing, out_cdw, exact
        self.parametric, self.with_dimensions = parametric, with_dimensions

    def run(self) -> None:
        if sys.platform != "win32":
            self.failed.emit("Построение в КОМПАС возможно только в Windows с установленным КОМПАС-3D.")
            return
        try:
            import pythoncom

            pythoncom.CoInitialize()
            try:
                m3d = self.out.with_suffix(".m3d")
                self.progress.emit("— 1. Модель —")
                text, saved, size = make_model(self.drawing, m3d, self.exact, self.parametric,
                                               self.progress.emit)
                self.progress.emit("— 2. Чертёж —")
                drawing_text = write_drawing(self.drawing, self.out, self.with_dimensions,
                                             self.progress.emit, model=m3d if saved else None,
                                             model_size=size)
                self.finished.emit(text + "\n\n" + drawing_text)
            finally:
                pythoncom.CoUninitialize()
        except Exception as exc:
            self.failed.emit(str(exc) if isinstance(exc, ModelError) else traceback.format_exc())


class ModelError(RuntimeError):
    """The model cannot be made from this drawing (said in plain words)."""


def make_model(drawing, out: Path, exact: bool, parametric: bool, log):
    """Build and save the part. Returns (report, saved, (length, diameter) in mm)."""
    from ..model3d.revolve import find_revolve_profile

    if not exact:
        drawing = geometry_only(drawing)
        log("Модель по геометрии чертежа (без выравнивания по размерам): "
            "концы контура сомкнуты, размеры не используются")
    profile = find_revolve_profile(drawing)
    if profile is None:
        raise ModelError("Не найден профиль тела вращения: нужна осевая линия вдоль детали "
                         "и контур (лучше — разрез со штриховкой) по одну сторону от неё.")
    log(profile.summary())
    from ..kompas.api5 import Api5Backend
    from ..model3d.endview import find_flange
    from ..model3d.revolve import drawing_radii, profile_segments, shift_loops, thread_specs

    log("Подключение к КОМПАС…")
    backend = Api5Backend(log=log)
    log("Эскиз профиля и операция вращения…")
    loops = profile_segments(profile, drawing_radii(drawing) if exact else ())
    threads = thread_specs(drawing, profile, loops)
    flange = None
    try:
        flange = find_flange(drawing, profile, loops)
    except Exception as exc:
        log(f"Вид с торца не разобран: {exc!r}")
    channels = []
    try:
        from ..model3d.channels import find_channels

        channels = find_channels(drawing, profile)
    except Exception as exc:
        log(f"Каналы поперёк оси не разобраны: {exc!r}")
    for ch in channels:
        log("Сверление: " + ch.text())
    fillets = []
    if flange is not None:
        log(flange.summary())
        from ..model3d.endview import fillets_after_milling

        # the milling runs through the fillets at the flange faces
        _, cut = fillets_after_milling(loops, flange)
        flange.cut_extra = max((f.radius for f in cut), default=0.0)
        for h in flange.holes or []:
            log(f"Отверстие Ø{2 * h.radius:g} под {h.tilt:.0f}° к оси "
                f"из точки ({h.u:g}; {h.v:g}) торца")
        # the flange in the middle of the YOZ plane (see Api5Backend._flange)
        shift = -(flange.x0 + flange.x1) / 2
        loops = shift_loops(loops, shift)
        flange.x0, flange.x1 = flange.x0 + shift, flange.x1 + shift
        for t in threads:
            t.x += shift
        for ch in channels:
            ch.x += shift
        for f in fillets:
            f.x += shift
    pts = [p for loop in loops for seg in loop for p in _seg_points(seg)]
    size = (max(x for x, _ in pts) - min(x for x, _ in pts), 2 * max(abs(y) for _, y in pts)) \
        if pts else (50.0, 50.0)
    saved = backend.revolve_part(loops, str(out), threads, log=log, flange=flange,
                                 fillets=fillets, channels=channels, parametric=parametric)
    return (profile.summary() + "\n" + (f"3D-деталь сохранена: {out}" if saved
                                        else f"Не удалось сохранить {out}"), saved, size)


def _seg_points(seg):
    if seg[0] == "line":
        return [seg[1], seg[2]]
    (cx, cy), r = seg[1], seg[2]
    return [(cx - r, cy - r), (cx + r, cy + r)]


def geometry_only(drawing: ir.Drawing) -> ir.Drawing:
    """A copy of the drawing whose contour is closed by its own geometry —
    ends that nearly meet are joined, near-straight lines straightened — with
    no fitting to the dimensions: the model follows the lines as drawn."""
    import copy

    from ..geometry.regularize import close_contour

    out = copy.deepcopy(drawing)
    close_contour(out)
    return out
