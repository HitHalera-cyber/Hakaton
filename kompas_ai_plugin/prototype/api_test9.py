"""Ninth API test: API7 for everything, and a first 3D body.

Part A — the API7 objects the plugin still makes through API5. Each check
lists the members of the API7 interface (so a wrong name can be fixed from
the report) and tries to create the object:
  * linear dimension with a manual text, radial and angular dimension;
  * a view with scale 2:1 through API7 Views.Add;
  * a hatch.
Part B — a body of revolution (the future «3D по чертежу»): a stepped shaft
profile is drawn in a sketch on the XOY plane and revolved 360° around an
axial line, then saved as .m3d.

Run:  py api_test9.py   — then send api_test9_report.txt and screenshots of
the drawing and of the 3D part.
"""

from __future__ import annotations

import sys
import traceback

import smoke_test as st
from api_test7 import members, result
from smoke_test import Context, cast, constant, log


def try_constant(name, fallback):
    try:
        return constant(name)
    except AttributeError:
        log(f"      константа {name} не найдена, беру {fallback}")
        return fallback


# --- Part A: API7 2D ----------------------------------------------------------------

def check_linear(ctx: Context) -> None:
    dims = ctx.symbols.LineDimensions
    dim = dims.Add()
    log(f"      ILineDimension: {members(dim)}")
    dim.X1, dim.Y1, dim.X2, dim.Y2 = 30.0, 150.0, 90.0, 150.0
    dim.X3, dim.Y3 = 60.0, 140.0
    dim.Orientation = try_constant("ksLinDHorizontal", 0)
    try:
        text = cast(dim, "IDimensionText")
        log(f"      IDimensionText: {members(text)}")
        text.AutoNominalValue = False
        text.NominalText.Str = "60±0,1"
    except Exception as exc:
        log(f"      ручной текст размера: {exc!r}")
    result("API7 линейный размер (на экране «60±0,1»)", dim.Update())


def check_radial(ctx: Context) -> None:
    doc = ctx.api5.ActiveDocument2D()
    doc.ksCircle(150.0, 150.0, 12.0, st.STYLE_MAIN)
    dim = ctx.symbols.RadialDimensions.Add()
    log(f"      IRadialDimension: {members(dim)}")
    dim.Xc, dim.Yc, dim.Radius, dim.Angle = 150.0, 150.0, 12.0, 45.0
    result("API7 радиальный размер R12", dim.Update())


def check_angular(ctx: Context) -> None:
    doc = ctx.api5.ActiveDocument2D()
    doc.ksLineSeg(200.0, 140.0, 240.0, 140.0, st.STYLE_MAIN)
    doc.ksLineSeg(200.0, 140.0, 228.28, 168.28, st.STYLE_MAIN)
    coll = ctx.symbols.AngleDimensions
    dim = coll.Add(try_constant("ksAngleDimension", 0)) if _needs_arg(coll) else coll.Add()
    log(f"      IAngleDimension: {members(dim)}")
    for name, value in (("Xc", 200.0), ("Yc", 140.0), ("Angle1", 0.0), ("Angle2", 45.0),
                        ("Radius", 25.0)):
        try:
            setattr(dim, name, value)
        except Exception as exc:
            log(f"      {name}: {exc!r}")
    result("API7 угловой размер 45°", dim.Update())


def _needs_arg(coll) -> bool:
    try:
        import inspect
        return len(inspect.signature(coll.Add).parameters) > 0
    except (TypeError, ValueError):
        return False


def check_view(ctx: Context) -> None:
    views = ctx.doc2d.ViewsAndLayersManager.Views
    log(f"      IViews: {members(views)}")
    view = views.Add(try_constant("ksViewDrawing", 0)) if _needs_arg(views) else views.Add()
    log(f"      IView: {members(view)}")
    view.X, view.Y, view.Scale = 300.0, 60.0, 2.0
    try:
        view.Name = "Вид 2:1 (API7)"
    except Exception as exc:
        log(f"      Name: {exc!r}")
    ok = view.Update()
    result("API7 вид 2:1 Views.Add", ok)
    if ok:
        drawing = cast(view, "IDrawingContainer")
        c = drawing.Circles.Add()
        c.Xc, c.Yc, c.Radius, c.Style = 0.0, 0.0, 5.0, st.STYLE_MAIN
        result("окружность R5 в виде 2:1 (на листе R10)", c.Update())


def check_hatch(ctx: Context) -> None:
    hatches = ctx.drawing.Hatches
    hatch = hatches.Add()
    log(f"      IHatch: {members(hatch)}")
    try:
        bounds = cast(hatch, "IBoundariesObject")
        log(f"      IBoundariesObject: {members(bounds)}")
    except Exception as exc:
        log(f"      IBoundariesObject: {exc!r}")
    result("API7 штриховка (объект создан)", hatch is not None)


# --- Part B: 3D body of revolution ----------------------------------------------------

PROFILE = [(0, 0), (0, 10), (20, 10), (20, 15), (45, 15), (45, 8), (60, 8), (60, 0)]


def check_revolve(ctx: Context) -> None:
    m = ctx.api5_module
    doc3d = ctx.api5.Document3D()
    log(f"      ksDocument3D: {members(doc3d)}")
    result("новая деталь Document3D.Create", doc3d.Create(False, True))
    part = doc3d.GetPart(try_constant("pTop_Part", -1))
    sketch = part.NewEntity(try_constant("o3d_sketch", 5))
    sdef = m.ksSketchDefinition(sketch.GetDefinition())
    sdef.SetPlane(part.GetDefaultEntity(try_constant("o3d_planeXOY", 1)))
    result("эскиз на плоскости XOY", sketch.Create())
    d2 = sdef.BeginEdit()
    # Profile above the axis (X along the axis, Y = radius); the axial line is
    # the axis of revolution.
    for a, b in zip(PROFILE, PROFILE[1:]):
        d2.ksLineSeg(float(a[0]), float(a[1]), float(b[0]), float(b[1]), st.STYLE_MAIN)
    d2.ksLineSeg(-5.0, 0.0, 65.0, 0.0, st.STYLE_AXIAL)
    sdef.EndEdit()
    rot = part.NewEntity(try_constant("o3d_baseRotated", 25))
    rdef = m.ksBaseRotatedDefinition(rot.GetDefinition())
    log(f"      ksBaseRotatedDefinition: {members(rdef)}")
    rdef.SetSideParam(True, 360.0)
    rdef.SetSketch(sketch)
    result("операция вращения 360°", rot.Create())
    out = st.OUTPUT_DIR / "kompas_ai_api_test9.m3d"
    out.parent.mkdir(parents=True, exist_ok=True)
    result(f"сохранение детали {out}", doc3d.SaveAs(str(out)))


CHECKS = [
    ("A1. API7 линейный размер с ручным текстом", check_linear),
    ("A2. API7 радиальный размер", check_radial),
    ("A3. API7 угловой размер", check_angular),
    ("A4. API7 вид с масштабом", check_view),
    ("A5. API7 штриховка", check_hatch),
    ("B. 3D: тело вращения по профилю", check_revolve),
]


def main() -> int:
    log("Тест API №9: API7 для всего и первая 3D-деталь")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2
    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants),
                       ("Новый чертёж", st.step_new_drawing),
                       ("Активный вид", st.step_active_view)]:
        print(f"...    {name}", flush=True)
        func(ctx)
    for name, func in CHECKS:
        log("")
        log(name)
        try:
            func(ctx)
        except Exception as exc:
            result(name, False, repr(exc))
            log("      " + traceback.format_exc().strip().splitlines()[-1])
    out = st.OUTPUT_DIR / "kompas_ai_api_test9.cdw"
    try:
        ctx.doc.SaveAs(str(out))
        log(f"\nЧертёж сохранён: {out}")
    except Exception as exc:
        log(f"\nСохранить чертёж не удалось: {exc!r}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test9_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
