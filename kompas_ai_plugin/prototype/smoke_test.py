"""Smoke test of the KOMPAS-3D v23 API (API7 via COM).

Creates a new drawing, adds a line, a circle, an arc, an axial line, a text and
a linear dimension, then saves the document as .cdw.

Each step runs independently: a failing step is reported and the script goes
on, so a single run shows which API names work in the installed version.
Everything printed is also written to ``smoke_test_report.txt`` next to this
script — that file is what should be sent back for analysis.

Run on Windows with KOMPAS-3D v23 installed:
    pip install -r requirements.txt
    python smoke_test.py
"""

from __future__ import annotations

import datetime
import os
import platform
import sys
import traceback
from pathlib import Path

REPORT_PATH = Path(__file__).with_name("smoke_test_report.txt")
OUTPUT_DIR = Path(os.environ.get("TEMP", str(Path.home()))) / "kompas_ai_smoke"
OUTPUT_FILE = OUTPUT_DIR / "kompas_ai_smoke.cdw"

# Numeric fallbacks used only when the constant is missing from the type library.
DOCUMENT_DRAWING_FALLBACK = 1  # DocumentTypeEnum.ksDocumentDrawing
STYLE_MAIN = 1  # system line style "основная"
STYLE_THIN = 2  # system line style "тонкая"
STYLE_AXIAL = 3  # system line style "осевая"

_report: list[str] = []


def log(message: str = "") -> None:
    print(message)
    _report.append(message)


def save_report() -> None:
    REPORT_PATH.write_text("\n".join(_report) + "\n", encoding="utf-8")
    print(f"\nОтчёт сохранён: {REPORT_PATH}")


class Context:
    """Objects shared between steps; filled as the steps succeed."""

    app = None
    doc = None
    doc2d = None
    view = None
    drawing = None
    symbols = None
    api5 = None
    api5_module = None
    last_api5 = None


def constant(name: str, fallback=None):
    """Return a constant from the generated KOMPAS type libraries."""
    from win32com.client import constants

    try:
        return getattr(constants, name)
    except AttributeError:
        if fallback is None:
            raise
        log(f"    константа {name} не найдена, использую {fallback}")
        return fallback


def cast(obj, interface: str):
    """QueryInterface a COM object to a named KOMPAS interface."""
    from win32com.client import CastTo

    return CastTo(obj, interface)


def step_connect(ctx: Context) -> None:
    from win32com.client import gencache

    print("    (первый запуск может занять 1-3 минуты: генерируются обёртки API"
          " и запускается КОМПАС)", flush=True)
    ctx.app = gencache.EnsureDispatch("Kompas.Application.7")
    ctx.app.Visible = True
    try:
        log(f"    Приложение: {ctx.app.ApplicationName(True)}")
    except Exception:  # the name is informational only
        log("    (имя/версию приложения получить не удалось)")


def find_kompas_typelibs() -> list[tuple[str, int, int, str]]:
    """List registered type libraries whose name mentions KOMPAS."""
    import winreg

    found = []
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "TypeLib") as root:
        for i in range(winreg.QueryInfoKey(root)[0]):
            guid = winreg.EnumKey(root, i)
            try:
                with winreg.OpenKey(root, guid) as guid_key:
                    for j in range(winreg.QueryInfoKey(guid_key)[0]):
                        version = winreg.EnumKey(guid_key, j)
                        name = winreg.QueryValue(guid_key, version)
                        if "kompas" in name.lower() or "компас" in name.lower():
                            major, _, minor = version.partition(".")
                            found.append((guid, int(major, 16), int(minor or "0", 16), name))
            except (OSError, ValueError):
                continue
    return found


def step_load_api5_constants(ctx: Context) -> None:
    # Kompas.Application.5 does not expose type info, so its wrappers (with
    # the ks* constants and the KompasObject interface) are generated from
    # the registered type libraries instead.
    import pythoncom
    from win32com.client import Dispatch, gencache

    typelibs = find_kompas_typelibs()
    if not typelibs:
        raise RuntimeError("в реестре не найдено ни одной библиотеки типов КОМПАС")
    for guid, major, minor, name in typelibs:
        try:
            module = gencache.EnsureModule(guid, 0, major, minor)
            log(f"    {name} {major}.{minor} {guid}: ok")
        except Exception as exc:
            log(f"    {name} {major}.{minor} {guid}: {exc!r}")
            continue
        if ctx.api5 is None and module is not None and hasattr(module, "KompasObject"):
            raw = Dispatch("Kompas.Application.5")
            ctx.api5_module = module
            ctx.api5 = module.KompasObject(raw._oleobj_.QueryInterface(
                module.KompasObject.CLSID, pythoncom.IID_IDispatch))
    if ctx.api5 is None:
        raise RuntimeError("интерфейс KompasObject (API5) не найден")


def step_new_drawing(ctx: Context) -> None:
    doc_type = constant("ksDocumentDrawing", DOCUMENT_DRAWING_FALLBACK)
    ctx.doc = ctx.app.Documents.Add(doc_type, True)
    ctx.doc2d = cast(ctx.doc, "IKompasDocument2D")


def step_active_view(ctx: Context) -> None:
    views = ctx.doc2d.ViewsAndLayersManager.Views
    ctx.view = views.ActiveView
    log(f"    Активный вид: масштаб {ctx.view.Scale}")
    ctx.drawing = cast(ctx.view, "IDrawingContainer")
    ctx.symbols = cast(ctx.view, "ISymbols2DContainer")


def step_line(ctx: Context) -> None:
    seg = ctx.drawing.LineSegments.Add()
    seg.X1, seg.Y1, seg.X2, seg.Y2 = 20.0, 20.0, 120.0, 20.0
    seg.Style = STYLE_MAIN
    if not seg.Update():
        raise RuntimeError("LineSegment.Update() вернул False")


def step_diagnose_editing(ctx: Context) -> None:
    """Find out why collection.Add() returns nothing.

    Tries the same operation through late binding and through API5: if every
    route fails, KOMPAS itself refuses to edit (licence / view-only mode),
    not a particular API call.
    """
    from win32com.client import dynamic

    try:
        log(f"    Документ только для чтения: {ctx.doc.ReadOnly}")
    except Exception as exc:
        log(f"    ReadOnly недоступен: {exc!r}")

    late = dynamic.Dispatch(ctx.drawing.LineSegments._oleobj_)
    seg = late.Add()
    log(f"    API7 Add() через позднее связывание: {seg!r}")

    if ctx.api5 is None:
        log("    API5 недоступен, проверка через ksLineSeg пропущена")
        return
    doc5 = ctx.api5.ActiveDocument2D()
    ref = doc5.ksLineSeg(20.0, 40.0, 120.0, 40.0, STYLE_MAIN)
    log(f"    API5 ksLineSeg вернул {ref} (0 = не создан)")
    try:
        log(f"    API5 код последней ошибки: {ctx.api5.ksReturnResult()}")
    except Exception as exc:
        log(f"    ksReturnResult недоступен: {exc!r}")
    if not ref:
        raise RuntimeError("КОМПАС не создаёт объекты ни через API7, ни через API5")


def step_circle(ctx: Context) -> None:
    circle = ctx.drawing.Circles.Add()
    circle.Xc, circle.Yc, circle.Radius = 70.0, 60.0, 12.5
    circle.Style = STYLE_MAIN
    if not circle.Update():
        raise RuntimeError("Circle.Update() вернул False")


def step_arc(ctx: Context) -> None:
    arc = ctx.drawing.Arcs.Add()
    arc.Xc, arc.Yc, arc.Radius = 150.0, 60.0, 20.0
    arc.Angle1, arc.Angle2 = 0.0, 90.0
    arc.Direction = True  # counter-clockwise
    arc.Style = STYLE_MAIN
    if not arc.Update():
        raise RuntimeError("Arc.Update() вернул False")


def step_axial_line(ctx: Context) -> None:
    seg = ctx.drawing.LineSegments.Add()
    seg.X1, seg.Y1, seg.X2, seg.Y2 = 50.0, 60.0, 90.0, 60.0
    seg.Style = STYLE_AXIAL
    if not seg.Update():
        raise RuntimeError("осевая: Update() вернул False")


def step_text(ctx: Context) -> None:
    text = ctx.drawing.DrawingTexts.Add()
    text.X, text.Y = 20.0, 100.0
    cast(text, "IText").Str = "Тест плагина КОМПАС-AI"
    if not text.Update():
        raise RuntimeError("DrawingText.Update() вернул False")


def step_linear_dimension(ctx: Context) -> None:
    dim = ctx.symbols.LineDimensions.Add()
    dim.X1, dim.Y1 = 20.0, 20.0
    dim.X2, dim.Y2 = 120.0, 20.0
    dim.X3, dim.Y3 = 70.0, 8.0  # position of the dimension line
    try:
        dim.Orientation = constant("ksLinDHorizontal")
    except AttributeError:
        log("    константа ksLinDHorizontal не найдена, ориентация по умолчанию")
    if not dim.Update():
        raise RuntimeError("LineDimension.Update() вернул False")


def step_diametral_dimension(ctx: Context) -> None:
    dim = ctx.symbols.DiametralDimensions.Add()
    dim.Xc, dim.Yc, dim.Radius = 70.0, 60.0, 12.5
    dim.Angle = 45.0
    if not dim.Update():
        raise RuntimeError("DiametralDimension.Update() вернул False")


def step_save(ctx: Context) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx.doc.SaveAs(str(OUTPUT_FILE))
    if not OUTPUT_FILE.exists():
        raise RuntimeError(f"SaveAs не создал файл {OUTPUT_FILE}")
    log(f"    Сохранено: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size} байт)")



# --- API5 route -------------------------------------------------------------
# In v22 API7 collection.Add() returned nothing while API5 ksLineSeg worked,
# so every object type is also tried through API5. Objects are placed lower on
# the sheet (y < 0 relative to the API7 ones) to tell the routes apart.


def _api5_doc(ctx: Context):
    if ctx.api5 is None:
        raise RuntimeError("API5 недоступен")
    return ctx.api5.ActiveDocument2D()


def _api5_param(ctx: Context, struct_const: str, interface: str):
    raw = ctx.api5.GetParamStruct(constant(struct_const))
    return getattr(ctx.api5_module, interface)(raw)


def _check_ref(ref, what: str) -> None:
    log(f"    {what}: ссылка {ref}")
    if not ref:
        raise RuntimeError(f"{what} не создан (ksReturnResult={_last_error()})")


def _last_error():
    try:
        return Context.last_api5.ksReturnResult()
    except Exception:
        return "?"


def step_api5_geometry(ctx: Context) -> None:
    Context.last_api5 = ctx.api5
    doc = _api5_doc(ctx)
    _check_ref(doc.ksLineSeg(20.0, -20.0, 120.0, -20.0, STYLE_MAIN), "отрезок ksLineSeg")
    _check_ref(doc.ksCircle(70.0, -60.0, 12.5, STYLE_MAIN), "окружность ksCircle")
    _check_ref(doc.ksArcByAngle(150.0, -60.0, 20.0, 0.0, 90.0, 1, STYLE_MAIN),
               "дуга ksArcByAngle")
    _check_ref(doc.ksLineSeg(50.0, -60.0, 90.0, -60.0, STYLE_AXIAL), "осевая ksLineSeg")
    _check_ref(doc.ksPoint(20.0, -100.0, 0), "точка ksPoint")


def step_api5_text(ctx: Context) -> None:
    doc = _api5_doc(ctx)
    # ksText(x, y, angle, height, narrowing, flags, string)
    _check_ref(doc.ksText(20.0, -110.0, 0.0, 5.0, 1.0, 0, "Тест API5"), "текст ksText")


def step_api5_linear_dimension(ctx: Context) -> None:
    doc = _api5_doc(ctx)
    par = _api5_param(ctx, "ko_LDimParam", "ksLDimParam")
    src = ctx.api5_module.ksLDimSourceParam(par.GetSPar())
    src.Init()
    src.x1, src.y1, src.x2, src.y2 = 20.0, -20.0, 120.0, -20.0
    src.dx, src.dy = 0.0, -12.0
    src.basePoint = 1
    src.ps = 1  # horizontal
    drw = ctx.api5_module.ksDimDrawingParam(par.GetDPar())
    drw.Init()
    txt = ctx.api5_module.ksDimTextParam(par.GetTPar())
    txt.Init(False)
    _check_ref(doc.ksLinDimension(par), "линейный размер ksLinDimension")


def step_api5_diametral_dimension(ctx: Context) -> None:
    doc = _api5_doc(ctx)
    par = _api5_param(ctx, "ko_RDimParam", "ksRDimParam")
    src = ctx.api5_module.ksRDimSourceParam(par.GetSPar())
    src.Init()
    src.xc, src.yc, src.rad = 70.0, -60.0, 12.5
    drw = ctx.api5_module.ksRDimDrawingParam(par.GetDPar())
    drw.Init()
    drw.ang = 45.0
    txt = ctx.api5_module.ksDimTextParam(par.GetTPar())
    txt.Init(False)
    _check_ref(doc.ksDiamDimension(par), "размер диаметра ksDiamDimension")


STEPS = [
    ("Подключение к КОМПАС (API7)", step_connect, True),
    ("Константы API5", step_load_api5_constants, False),
    ("Новый чертёж", step_new_drawing, True),
    ("Активный вид и контейнеры", step_active_view, True),
    ("Отрезок", step_line, False),
    ("Диагностика редактирования", step_diagnose_editing, False),
    ("Окружность", step_circle, False),
    ("Дуга", step_arc, False),
    ("Осевая линия", step_axial_line, False),
    ("Текст", step_text, False),
    ("Линейный размер", step_linear_dimension, False),
    ("Размер диаметра", step_diametral_dimension, False),
    ("API5: отрезок, окружность, дуга, осевая, точка", step_api5_geometry, False),
    ("API5: текст", step_api5_text, False),
    ("API5: линейный размер", step_api5_linear_dimension, False),
    ("API5: размер диаметра", step_api5_diametral_dimension, False),
    ("Сохранение .cdw", step_save, False),
]


def main() -> int:
    log(f"Smoke test КОМПАС-3D API — {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    log(f"Python {sys.version.split()[0]}, {platform.platform()}")
    log()

    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        save_report()
        return 2
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        log("Не установлен pywin32. Выполните: pip install -r requirements.txt")
        save_report()
        return 2

    ctx = Context()
    failed = []
    for name, func, required in STEPS:
        print(f"...    {name}", flush=True)
        try:
            func(ctx)
            log(f"[OK]   {name}")
        except Exception as exc:
            failed.append(name)
            log(f"[FAIL] {name}: {exc!r}")
            log("    " + traceback.format_exc().strip().replace("\n", "\n    "))
            if required:
                log("\nШаг обязателен, дальнейшие шаги невозможны.")
                break

    log()
    log("Итог: всё работает." if not failed else f"Итог: не прошли шаги: {', '.join(failed)}")
    save_report()
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
