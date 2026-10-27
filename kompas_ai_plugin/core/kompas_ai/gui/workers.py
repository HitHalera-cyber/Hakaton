"""Background jobs so the window stays responsive.

Recognition takes seconds, building a drawing in KOMPAS can take minutes;
both run in a QThread and report back through signals.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

import pymupdf
from PySide6.QtCore import QObject, Signal

from .. import ir
from ..pipeline import recognize_pdf
from ..report.preview import render_preview_png

PREVIEW_DPI = 150
PREVIEW_STAGE = "Рисую предпросмотр"
MODEL_STAGE = "Ищу профиль для 3D-модели"
PHOTO_STAGE = "Перевожу фото в линии"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
CANCELLED = "Распознавание отменено"


class Cancelled(Exception):
    """The user stopped the recognition."""


MAX_PREVIEW_PIXELS = 10_000_000  # an A1 sheet at 150 dpi is 17 million: hundreds of MB


def preview_dpi(width_pt: float, height_pt: float) -> int:
    """The preview's resolution: PREVIEW_DPI, less for a big sheet."""
    inches = (width_pt / 72.0) * (height_pt / 72.0)
    return max(60, min(PREVIEW_DPI, int((MAX_PREVIEW_PIXELS / max(inches, 1e-6)) ** 0.5)))


class RecognizeJob(QObject):
    finished = Signal(object, bytes, float)  # drawing, preview png, page height (pt)
    failed = Signal(str)
    stage = Signal(str)  # one of pipeline.STAGES, then PREVIEW_STAGE

    def __init__(self, pdf: Path, exact: bool, page: int = 0, sheet_mm=None,
                 scale: float | None = None, overrides: dict | None = None,
                 attach: dict | None = None):
        """``sheet_mm``, ``scale``: of a photo — its sheet format and the
        drawing's scale, as the user read them on the photo's title block.
        ``attach``: the user's choices for sizes without a dimension line."""
        super().__init__()
        self.pdf, self.exact, self.page = pdf, exact, page
        self.sheet_mm, self.scale = sheet_mm, scale
        self.overrides = overrides or {}  # dimension id → the user's value
        self.attach = attach or {}
        self.dpi = PREVIEW_DPI
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True  # seen at the next stage of the recognition

    def _stage(self, name: str) -> None:
        if self.cancelled:
            raise Cancelled()
        self.stage.emit(name)

    def run(self) -> None:
        try:
            raster = self.pdf.suffix.lower() in IMAGE_SUFFIXES
            if raster:
                # a photo or a scan: its lines into a PDF the recognition reads
                self._stage(PHOTO_STAGE)
                from ..raster.photo import photo_to_pdf

                vector = Path(tempfile.gettempdir()) / f"kompas_ai_photo_{self.pdf.stem}.pdf"
                photo = photo_to_pdf(self.pdf, vector, self.sheet_mm)
                self.pdf = vector
            try:
                drawing = recognize_pdf(self.pdf, self.page, exact=self.exact,
                                        progress=self._stage, raster=raster, scale=self.scale,
                                        overrides=self.overrides, attach=self.attach)
                if raster:
                    drawing.warnings.insert(0, photo.text() + ". Надписи с фото не читаются: "
                                            "числа размеров впишите в КОМПАС")
            except Cancelled:
                raise
            except Exception:
                if not self.exact:
                    raise
                # the drawing opens anyway: as in the PDF, without the exact fitting
                error = traceback.format_exc().strip().splitlines()[-1]
                drawing = recognize_pdf(self.pdf, self.page, exact=False,
                                        progress=self._stage, raster=raster, scale=self.scale,
                                        overrides=self.overrides, attach=self.attach)
                drawing.warnings.insert(0, "Точный режим не удался, чертёж открыт как в PDF "
                                           f"(без выравнивания): {error}")
            self._stage(MODEL_STAGE)
            drawing.model_verdict = judge_model(drawing, self.exact)
            self._stage(PREVIEW_STAGE)
            with pymupdf.open(str(self.pdf)) as doc:
                rect = doc[self.page].rect
            height = rect.height
            self.dpi = preview_dpi(rect.width, rect.height)
            png = render_preview_png(drawing, self.pdf, self.page, self.dpi, legend=False)
            self.finished.emit(drawing, png, height)
        except Cancelled:
            self.failed.emit(CANCELLED)
        except Exception:
            self.failed.emit(traceback.format_exc())


def judge_model(drawing, exact: bool):
    """(True/None/False, why): what 3D part can be made — a body of revolution
    (turned), else a prismatic part (the main view's outline extruded); False
    only when there is no closed outline at all."""
    try:
        from ..model3d.revolve import find_revolve_profile, revolve_verdict

        ok, why = revolve_verdict(drawing)
        found = ok is not False or not exact
        found = found and find_revolve_profile(drawing) is not None
        if found and ok is False:
            # without the fitting the model follows the lines, whatever the sizes say
            return None, "тело вращения; режим без выравнивания: модель строится по линиям"
        if found:
            return ok, "тело вращения: " + why
    except Exception as exc:  # the drawing stays usable whatever happens here
        why = f"тело вращения не проверено: {exc!r}"
    from ..model3d.prismatic import extrude_verdict

    ok2, why2 = extrude_verdict(drawing)
    return (True, why2) if ok2 else (False, why2)


class KompasJob(QObject):
    """The drawing in KOMPAS: a view at the drawing's scale, the part in true
    millimetres (KOMPAS measures the sizes itself; a number the PDF writes
    differently is written as in the PDF)."""

    progress = Signal(str)
    finished = Signal(str)  # report text
    failed = Signal(str)

    def __init__(self, drawing, out_cdw: Path, with_dimensions: bool = True,
                 view_scale: float | None = None):
        super().__init__()
        self.drawing, self.out = drawing, out_cdw
        self.with_dimensions = with_dimensions
        self.view_scale = view_scale

    def run(self) -> None:
        if sys.platform != "win32":
            self.failed.emit("Построение в КОМПАС возможно только в Windows с установленным КОМПАС-3D.")
            return
        try:
            import pythoncom

            pythoncom.CoInitialize()  # COM must be initialised in every thread that uses it
            try:
                self.finished.emit(write_drawing(self.drawing, self.out, self.with_dimensions,
                                                 self.progress.emit,
                                                 view_scale=self.view_scale))
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            self.failed.emit(traceback.format_exc())


LINK_MAIN_VIEW = False  # «Построить всё»: the main view as the model's associative view


def write_drawing(drawing, out: Path, with_dimensions: bool, log, model: Path | None = None,
                  link=None, view_scale: float | None = None) -> str:
    """The drawing built and saved. With ``model`` (a saved part) and ``link``
    (where its main view is on the sheet, from make_model) that view is the
    part's associative view: the lines it shows are not drawn by hand, and a
    change of the model rebuilds them on the drawing."""
    from ..kompas.api5 import Api5Backend
    from ..kompas.writer import DrawingWriter

    log("Подключение к КОМПАС (первый раз — до пары минут)…")
    # the drawing is not parametrised: constraints only ever move its lines
    backend = Api5Backend(log=log, parametric=False)
    log("Построение объектов…")
    writer = DrawingWriter(backend, mode="view", with_dimensions=with_dimensions,
                           view_scale=view_scale)
    linked = []
    # The model's associative view in place of the main view came out as an
    # empty frame on some installations (the drawing lost its outline), so
    # the main view is drawn by hand unless that is switched on.
    if not LINK_MAIN_VIEW:
        link = None
    if model is not None and link is not None:
        def on_sheet(b, d):
            old = d.scale.value or 1.0
            k = (view_scale or old) / old
            # where the main view lies on the sheet at the scale chosen
            placed = dict(link, origin=writer.place(link["origin"]), scale=link["scale"] * k)
            skip = _link_view(b, d, model, placed, log, source=link)
            linked.append(bool(skip))
            return skip

        writer.on_sheet = on_sheet
    report = writer.write(drawing)
    text = report.text()
    if linked:
        text += "\n" + (f"Главный вид — ассоциативный вид модели {model.name}: изменили модель — "
                         "вид на чертеже перестроится (Перестроить, F5)" if linked[0]
                         else "Ассоциативный вид модели не создан — главный вид нарисован линиями")
    saved = backend.save(str(out))
    return text + "\n" + (f"Сохранено: {out}" if saved else f"Не удалось сохранить {out}")


def _link_view(backend, drawing, model: Path, link, log, source=None) -> set:
    """The model's front view over the main view of the drawing; the ids of
    the drawn lines, arcs and hatches it replaces (empty when not made).
    ``source``: the link in the source's sheet mm, for finding those ids."""
    try:
        ok = backend.model_view(str(model), link["origin"], link["scale"], angle=link["angle"],
                                projection="#Спереди", hidden=True)
    except Exception as exc:
        log(f"Вид модели: {exc!r}")
        ok = False
    if not ok:
        return set()
    link = source or link
    if "box" in link:
        bx0, by0, bx1, by1 = link["box"]

        def inside(p):
            return bx0 - 0.5 <= p[0] <= bx1 + 0.5 and by0 - 0.5 <= p[1] <= by1 + 0.5
    else:
        (ox, oy), (ux, uy), k = link["origin"], link["u"], link["scale"]
        half = link["radius"] * k + 0.5

        def inside(p):
            vx, vy = p[0] - ox, p[1] - oy
            along = (vx * ux + vy * uy) / k
            return link["x_from"] - 0.5 / k <= along <= link["x_to"] + 0.5 / k \
                and abs(-vx * uy + vy * ux) <= half

    skip = set()
    for e in drawing.entities:
        style = getattr(e, "style", None)
        if isinstance(e, ir.Hatch):
            pts = [q for ring in e.contours for q in ring]
        elif style == ir.STYLE_MAIN and isinstance(e, ir.Line):
            pts = [e.p1, e.p2]
        elif style == ir.STYLE_MAIN and isinstance(e, (ir.Arc, ir.Circle)):
            r = e.radius
            pts = [(e.center[0] - r, e.center[1]), (e.center[0] + r, e.center[1]),
                   (e.center[0], e.center[1] - r), (e.center[0], e.center[1] + r)]
        else:
            continue
        if pts and all(inside(q) for q in pts):
            skip.add(e.id)
    return skip


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
                 with_dimensions: bool = True, view_scale: float | None = None):
        super().__init__()
        self.drawing, self.out, self.exact = drawing, out_cdw, exact
        self.parametric, self.with_dimensions = parametric, with_dimensions
        self.view_scale = view_scale

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
                text, saved, link = make_model(self.drawing, m3d, self.exact, self.parametric,
                                               self.progress.emit)
                self.progress.emit("— 2. Чертёж —")
                drawing_text = write_drawing(self.drawing, self.out, self.with_dimensions,
                                             self.progress.emit, model=m3d if saved else None,
                                             link=link, view_scale=self.view_scale)
                self.finished.emit(text + "\n\n" + drawing_text)
            finally:
                pythoncom.CoUninitialize()
        except Exception as exc:
            self.failed.emit(str(exc) if isinstance(exc, ModelError) else traceback.format_exc())


class CheckJob(QObject):
    """«Проверить КОМПАС»: which ways of making a linked view and a table
    this KOMPAS takes (kompas/diagnose.py)."""

    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def run(self) -> None:
        if sys.platform != "win32":
            self.failed.emit("Проверка КОМПАС возможна только в Windows с установленным КОМПАС-3D.")
            return
        try:
            import pythoncom

            pythoncom.CoInitialize()
            try:
                from ..kompas.diagnose import run

                report = run(self.progress.emit)
                self.finished.emit(f"Проверка КОМПАС закончена. Пришлите файл отчёта:\n{report}")
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            self.failed.emit(traceback.format_exc())


class ModelDrawingJob(QObject):
    """A drawing of a saved 3D part: its standard views, linked to it."""

    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, model: Path, out_cdw: Path, view_scale: float | None = None):
        super().__init__()
        self.model, self.out, self.view_scale = model, out_cdw, view_scale

    def run(self) -> None:
        if sys.platform != "win32":
            self.failed.emit("Построение в КОМПАС возможно только в Windows с установленным КОМПАС-3D.")
            return
        try:
            import pythoncom

            pythoncom.CoInitialize()
            try:
                self.finished.emit(drawing_of_model(self.model, self.out, self.view_scale,
                                                    self.progress.emit))
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            self.failed.emit(traceback.format_exc())


class AutoDimJob(QObject):
    """Sizes put on a finished drawing by ГОСТ 2.307, into a copy of it."""

    progress = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, source: Path, out: Path, replace: bool = False):
        super().__init__()
        self.source, self.out, self.replace = source, out, replace

    def run(self) -> None:
        try:
            if self.source.suffix.lower() == ".dxf":
                self.finished.emit(dimension_dxf(self.source, self.out, self.replace,
                                                 self.progress.emit))
                return
            if sys.platform != "win32":
                self.failed.emit("Чертёж .cdw открывает только КОМПАС-3D (Windows).")
                return
            import pythoncom

            pythoncom.CoInitialize()
            try:
                self.finished.emit(dimension_cdw(self.source, self.out, self.replace,
                                                 self.progress.emit))
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            self.failed.emit(traceback.format_exc())


def dimension_dxf(src: Path, out: Path, replace: bool, log) -> str:
    from .. import dimensioning

    log(f"Читаю {src.name}…")
    result = dimensioning.dimension(dimensioning.read_dxf(src), replace=replace)
    dimensioning.write_dxf(src, result, out)
    return (f"Образмерен {src.name}\n" + dimensioning.report(result)
            + f"\nСохранено: {out}")


def dimension_cdw(src: Path, out: Path, replace: bool, log) -> str:
    """The KOMPAS drawing opened, saved as DXF to be read, its sizes put in
    the sheet's own view (sheet millimetres) and the copy saved as ``out``."""
    from .. import dimensioning
    from ..kompas.api5 import Api5Backend
    from ..kompas.writer import DrawingWriter

    log("Подключение к КОМПАС…")
    backend = Api5Backend(log=log, parametric=False)
    backend.open_drawing(str(src))
    dxf = Path(tempfile.gettempdir()) / f"kompas_ai_{os.getpid()}_{src.stem}.dxf"
    try:
        if not backend.save_dxf(str(dxf)):
            raise RuntimeError("КОМПАС не сохранил чертёж в DXF — сохраните его как DXF сами "
                               "(Файл → Сохранить как → DXF) и образмерьте DXF")
        log("Ищу виды и расставляю размеры…")
        result = dimensioning.dimension(dimensioning.read_dxf(dxf), replace=replace)
    finally:
        try:
            dxf.unlink()
        except OSError:
            pass
    lines = [f"Образмерен {src.name}", dimensioning.report(result)]
    if replace:
        lines.append(f"Снято размеров в КОМПАС: {backend.delete_dimensions()}")
    backend.sheet_view()
    report = DrawingWriter(backend).write_dimensions(result.drawing, result.added)
    lines.append(report.text())
    lines.append("Размеры стоят в виде листа (не в видах) с числами, вписанными программой: "
                 "при изменении геометрии они сами не пересчитаются")
    saved = backend.save(str(out))
    lines.append(f"Сохранено: {out}" if saved else f"Не удалось сохранить {out}")
    return "\n".join(lines)


SHEETS = [(4, False, 210, 297), (3, True, 420, 297), (2, True, 594, 420), (1, True, 841, 594),
          (0, True, 1189, 841)]
STANDARD_SCALES = (10.0, 5.0, 4.0, 2.5, 2.0, 1.0, 0.5, 0.4, 0.25, 0.2, 0.1)


def lay_out_views(size, view_scale=None):
    """Sheet and places of the views of a part ``size`` = (Lx, Ly, Lz) mm by
    ГОСТ 2.305: the front view, the top view under it, the left view to its
    right, the isometry in the free corner. Returns (format, landscape, scale,
    {projection: centre on the sheet})."""
    lx, ly, lz = size
    gap = 25.0
    scales = [view_scale] if view_scale else STANDARD_SCALES
    # the biggest scale on A4/A3 down to 1:2, else the sheets that keep 1:2 or more
    tries = [(s, sh) for s in scales if s >= 0.5 or view_scale for sh in SHEETS[:2]] \
        + [(s, sh) for s in scales for sh in SHEETS]
    for s, (fmt, land, W, H) in tries:
        free_w, free_h = W - 20 - 5 - 20, H - 5 - 5 - 55 - 20  # frame, title block, margins
        w = (lx + lz) * s + gap
        h = (ly + lz) * s + gap
        if w <= free_w and h <= free_h:
            x0 = 20 + 10 + (free_w - w) / 2
            y0 = 5 + 55 + 10 + (free_h - h) / 2
            front = (x0 + lx * s / 2, y0 + lz * s + gap + ly * s / 2)
            top = (front[0], y0 + lz * s / 2)
            left = (x0 + lx * s + gap + lz * s / 2, front[1])
            iso = (left[0], top[1])
            return fmt, land, s, {"#Спереди": front, "#Сверху": top, "#Слева": left,
                                  "#Изометрия XYZ": iso}
    raise RuntimeError("Модель не помещается даже на листе A0 в масштабе 1:10")


def drawing_of_model(model: Path, out: Path, view_scale, log) -> str:
    """Views of the part drawn by the program from its mesh (KOMPAS saves it
    as STL); when KOMPAS cannot save the mesh, KOMPAS' own linked views."""
    from ..kompas.api5 import Api5Backend

    log("Подключение к КОМПАС…")
    backend = Api5Backend(log=log, parametric=False)
    stl = Path(tempfile.gettempdir()) / f"kompas_ai_{os.getpid()}_{model.stem}.stl"
    try:
        exported = backend.export_mesh(str(model), str(stl))
    except Exception as exc:
        log(f"  сетка модели не сохранена: {exc!r}")
        exported = False
    if exported:
        try:
            return _drawing_from_mesh(backend, model, stl, out, view_scale, log)
        except Exception as exc:
            log(f"Виды по сетке не построены: {exc!r}")
        finally:
            try:
                stl.unlink()
            except OSError:
                pass
    log("КОМПАС не сохранил сетку модели (STL) — виды, связанные с моделью")
    return _linked_views(backend, model, out, view_scale, log)


def _drawing_from_mesh(backend, model: Path, stl: Path, out: Path, view_scale, log) -> str:
    from ..kompas.writer import DrawingWriter
    from ..model3d.projection import model_drawing, read_stl

    log("Строю виды по сетке модели…")
    drawing, notes = model_drawing(read_stl(stl), view_scale, source=str(model))
    log(f"Лист {drawing.sheet.format}, масштаб {drawing.scale.text}, объектов {len(drawing.entities)}")
    report = DrawingWriter(backend, mode="view", with_dimensions=True).write(drawing)
    saved = backend.save(str(out))
    return ("Чертёж по модели " + model.name + "\n" + "\n".join(notes) + "\n" + report.text()
            + "\nВиды не связаны с моделью: после изменения модели постройте чертёж заново. "
            "Допуски, фаски, резьбу, шероховатость и выносные элементы добавьте в КОМПАС\n"
            + (f"Сохранено: {out}" if saved else f"Не удалось сохранить {out}"))


def _linked_views(backend, model: Path, out: Path, view_scale, log) -> str:
    x1, y1, z1, x2, y2, z2 = backend.model_gabarit(str(model))
    size = (x2 - x1, y2 - y1, z2 - z1)
    log(f"Габарит модели: {size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} мм")
    fmt, land, s, places = lay_out_views(size, view_scale)
    from ..kompas.writer import scale_name

    log(f"Лист A{fmt}{' альбомный' if land else ''}, масштаб {scale_name(s)}")
    backend.new_sheet(fmt, land)
    centre = ((x1 + x2) / 2, (y1 + y2) / 2, (z1 + z2) / 2)
    # where each view shows the model's centre (front: X, Y; top: X, Z; left: Z, Y)
    shown = {"#Спереди": (centre[0], centre[1]), "#Сверху": (centre[0], -centre[2]),
             "#Слева": (-centre[2], centre[1]), "#Изометрия XYZ": (0.0, 0.0)}
    made = []
    for projection, (cx, cy) in places.items():
        sc = s * (0.6 if projection.startswith("#Изометрия") else 1.0)
        u, v = shown[projection]
        at = (cx - u * sc, cy - v * sc)
        ok = backend.model_view(str(model), at, sc, projection=projection,
                                hidden=False)  # no hidden lines: the drawing stays readable
        made.append(f"{projection.lstrip('#')}: {'да' if ok else 'нет'}")
    saved = backend.save(str(out))
    return ("Чертёж по модели " + model.name + "\nВиды (связаны с моделью): " + ", ".join(made)
            + ("\nЕсли виды на листе пустые — пришлите журнал (вкладка «Журнал») и файл "
               "проверки КОМПАС: в этой версии КОМПАС связанные виды не строятся через API"
               if not any(m.endswith("да") for m in made) else "")
            + "\nРазмеры на виды ставятся в КОМПАС (Авторазмеры или вручную)\n"
            + (f"Сохранено: {out}" if saved else f"Не удалось сохранить {out}"))


class ModelError(RuntimeError):
    """The model cannot be made from this drawing (said in plain words)."""


def make_model(drawing, out: Path, exact: bool, parametric: bool, log):
    """Build and save the part. Returns (report, saved, (length, diameter) in mm)."""
    from ..model3d.revolve import find_revolve_profile

    if not exact:
        drawing = geometry_only(drawing)
        log("Модель по геометрии чертежа (без выравнивания по размерам): "
            "концы контура сомкнуты, размеры не используются")
    profile = None
    from ..model3d.revolve import revolve_verdict

    if revolve_verdict(drawing)[0] is not False or not exact:
        profile = find_revolve_profile(drawing)
    if profile is None:
        return make_extruded(drawing, out, parametric, log)
    log(profile.summary())
    from ..kompas.api5 import Api5Backend
    from ..model3d.endview import find_flange
    from ..model3d.revolve import drawing_radii, profile_segments, shift_loops, thread_specs

    log("Подключение к КОМПАС…")
    backend = Api5Backend(log=log)
    log("Эскиз профиля и операция вращения…")
    loops = profile_segments(profile, drawing_radii(drawing) if exact else ())
    if getattr(drawing, "raster", False):
        # a photo: radii onto the end view's circles, edges square, round sizes
        from ..model3d.revolve import end_view_radii, tidy_photo_profile

        loops = tidy_photo_profile(loops, end_view_radii(drawing, profile))
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
    holes = []
    try:
        from ..model3d.holes import find_axial_holes

        holes = find_axial_holes(drawing, profile)
    except Exception as exc:
        log(f"Отверстия вдоль оси не разобраны: {exc!r}")
    for h in holes:
        log("Отверстие вдоль оси: " + h.text())
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
    link = _view_link(profile, loops, shift if flange is not None else 0.0)
    saved = backend.revolve_part(loops, str(out), threads, log=log, flange=flange,
                                 fillets=fillets, channels=channels, parametric=parametric,
                                 holes=holes)
    return (profile.summary() + "\n" + (f"3D-деталь сохранена: {out}" if saved
                                        else f"Не удалось сохранить {out}"), saved, link)


def make_extruded(drawing, out: Path, parametric: bool, log):
    """A part that is not a body of revolution: the main view's outline with
    its through cuts, extruded to the thickness."""
    from ..kompas.api5 import Api5Backend
    from ..model3d.prismatic import find_extrude_profile

    prof = find_extrude_profile(drawing)
    if prof is None:
        raise ModelError("Не найден замкнутый контур детали: ни тело вращения, ни контур "
                         "для выдавливания.")
    log(prof.summary())
    log("Подключение к КОМПАС…")
    backend = Api5Backend(log=log)
    log("Эскиз контура и выдавливание…")
    saved = backend.extrude_part(prof.loops, prof.thickness, str(out), log=log,
                                 parametric=parametric)
    x0, y0, x1, y1 = prof.sheet_box
    # the part's front view lies on the main view: its origin at the outline's corner
    link = {"origin": (x0, y0), "angle": 0.0, "scale": prof.scale, "box": prof.sheet_box}
    return (prof.summary() + "\n" + (f"3D-деталь сохранена: {out}" if saved
                                     else f"Не удалось сохранить {out}"), saved, link)


def _view_link(profile, loops, shift: float):
    """Where the part's front view goes to lie over the main view of the
    drawing: the sheet point of the model's origin, the turn of its axis, the
    scale, and the stretch of the axis the part takes (model mm)."""
    import math

    from ..model3d.revolve import GRID

    if not profile.sheet_rings:
        return None
    (ax, ay), (bx, by) = profile.axis
    n = math.hypot(bx - ax, by - ay) or 1.0
    ux, uy, k = (bx - ax) / n, (by - ay) / n, profile.scale
    x0 = min(((p[0] - ax) * ux + (p[1] - ay) * uy) / k for ring in profile.sheet_rings
             for p in ring)
    x0 = round(x0 / GRID) * GRID  # as profile_segments puts the part's end at 0
    origin_x = x0 - shift
    pts = [p for loop in loops for seg in loop for p in _seg_points(seg)]
    if not pts:
        return None
    return {"origin": (ax + ux * origin_x * k, ay + uy * origin_x * k),
            "angle": math.degrees(math.atan2(uy, ux)), "scale": k, "u": (ux, uy),
            "x_from": min(x for x, _ in pts), "x_to": max(x for x, _ in pts),
            "radius": max(abs(y) for _, y in pts)}


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
