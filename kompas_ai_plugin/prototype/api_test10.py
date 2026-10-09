"""Tenth API test: parametric constraints (параметризация) through API7.

The plugin already finds the relations of the drawing (horizontal,
vertical, coincident ends, tangency…). This test checks how to give them to
KOMPAS so that the result is a parametric sketch:
  1. list the constraint/view/angle constants of the type library;
  2. two connected segments: «горизонталь» on one, «вертикаль» on the other,
     «объединение точек» at the corner (IDrawingObject1.NewConstraint);
  3. a circle with a tangent segment: «касание»;
  4. the API7 angular dimension and view with the argument the type
     library names (they returned nothing in api_test9).

Afterwards: drag a corner of the rectangle in KOMPAS — with working
constraints the sides stay horizontal/vertical and connected.

Run:  py api_test10.py   — then send api_test10_report.txt and a screenshot
(with the «Параметры»/«Ограничения» shown for a segment if you can).
"""

from __future__ import annotations

import sys
import traceback

import smoke_test as st
from api_test7 import members, result
from smoke_test import Context, cast, log


def all_constants(prefixes) -> list[str]:
    from win32com.client import constants

    names = set()
    for d in getattr(constants, "__dicts__", []):
        names.update(k for k in d if k.startswith(prefixes))
    return sorted(names)


def const(name):
    from win32com.client import constants

    return getattr(constants, name)


def check_constants(ctx: Context) -> None:
    for prefix in (("ksC",), ("ksView", "ksDrawingView"), ("ksAngle", "ksAng"),
                   ("ksDimension", "ksDim")):
        names = all_constants(prefix)
        log(f"      {prefix}: {', '.join(f'{n}={const(n)}' for n in names)[:1500]}")
    result("константы перечислены", True)


def segment(ctx, x1, y1, x2, y2):
    seg = ctx.drawing.LineSegments.Add()
    seg.X1, seg.Y1, seg.X2, seg.Y2 = x1, y1, x2, y2
    seg.Style = st.STYLE_MAIN
    seg.Update()
    return seg


def safe(name, fn):
    try:
        result(name, fn())
    except Exception as exc:
        result(name, False, repr(exc))


def constraint(obj, kind_name, **fields):
    dobj = cast(obj, "IDrawingObject1")
    c = dobj.NewConstraint()
    if c is None:
        raise RuntimeError("NewConstraint() вернул None")
    c.ConstraintType = const(kind_name)
    for k, v in fields.items():
        setattr(c, k, v)
    return c.Create()


def check_rectangle(ctx: Context) -> None:
    s1 = segment(ctx, 30.0, 200.0, 90.0, 201.0)   # almost horizontal on purpose
    s2 = segment(ctx, 90.0, 201.0, 91.0, 240.0)   # almost vertical
    log(f"      IDrawingObject1: {members(cast(s1, 'IDrawingObject1'))}")
    c = cast(s1, "IDrawingObject1").NewConstraint()
    log(f"      IParametriticConstraint: {members(c)}")
    safe("горизонталь", lambda: constraint(s1, "ksCHorizontal"))
    safe("вертикаль", lambda: constraint(s2, "ksCVertical"))
    # end of s1 (index 1) coincides with the start of s2 (index 0)
    safe("объединение точек", lambda: constraint(s1, "ksCMergePoints", Index=1, Partner=s2,
                                                 PartnerIndex=0))
    log(f"      после связей: s1 = ({s1.X1:.2f}, {s1.Y1:.2f}) – ({s1.X2:.2f}, {s1.Y2:.2f}); "
        f"s2 = ({s2.X1:.2f}, {s2.Y1:.2f}) – ({s2.X2:.2f}, {s2.Y2:.2f})")


def check_tangent(ctx: Context) -> None:
    circle = ctx.drawing.Circles.Add()
    circle.Xc, circle.Yc, circle.Radius, circle.Style = 150.0, 220.0, 15.0, st.STYLE_MAIN
    circle.Update()
    seg = segment(ctx, 120.0, 235.3, 180.0, 235.3)
    safe("касание отрезка и окружности",
         lambda: constraint(seg, "ksCTangentTwoCurves", Partner=circle))


def check_api7_angle_view(ctx: Context) -> None:
    for name in all_constants(("ksDrAngle", "ksAngleDim", "ksAngle")):
        try:
            dim = ctx.symbols.AngleDimensions.Add(const(name))
        except Exception as exc:
            log(f"      AngleDimensions.Add({name}): {exc!r}")
            continue
        log(f"      AngleDimensions.Add({name}) → {dim!r}")
        if dim is not None:
            log(f"      IAngleDimension: {members(dim)}")
            dim.Delete()
            break
    views = ctx.doc2d.ViewsAndLayersManager.Views
    for name in all_constants(("ksView", "ksDrawingView")):
        try:
            view = views.Add(const(name))
        except Exception as exc:
            log(f"      Views.Add({name}): {exc!r}")
            continue
        log(f"      Views.Add({name}) → {view!r}")
        if view is not None:
            log(f"      IView: {members(view)}")
            break
    result("угловой размер и вид API7 (см. строки выше)", True)


CHECKS = [
    ("1. Константы связей, видов, угловых размеров", check_constants),
    ("2. Прямоугольник со связями", check_rectangle),
    ("3. Касание", check_tangent),
    ("4. API7 угловой размер и вид", check_api7_angle_view),
]


def main() -> int:
    log("Тест API №10: параметризация (связи) через API7")
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
    out = st.OUTPUT_DIR / "kompas_ai_api_test10.cdw"
    try:
        ctx.doc.SaveAs(str(out))
        log(f"\nСохранено: {out}")
    except Exception as exc:
        log(f"\nСохранить не удалось: {exc!r}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test10_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
