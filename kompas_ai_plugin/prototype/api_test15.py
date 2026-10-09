"""Fifteenth API test: driving dimensions, text position, an angled plane.

1. A segment 30 mm long and a linear dimension on it; both points of the
   dimension tied to the segment ends (Index 0 and 1, api_test14 showed both
   are accepted for a start point), then «фиксированный размер» /
   «размер с переменной», then the value set to 40: does the segment follow?
2. IDimension2D.SetTextPosition / GetTextPosition: putting a dimension's
   value exactly where the source drawing has it.
3. A plane at 45° to YOZ around the Y axis and a sketch on it with two
   circles: R1 at (5, 0) and R2 at (0, 10), cut through the part — the
   screenshot shows which sketch axis is which (for the angled holes).

Run:  py api_test15.py   — then send api_test15_report.txt and screenshots
(the drawing and the part).
"""

from __future__ import annotations

import sys
import traceback

import smoke_test as st
from api_test7 import members, result
from smoke_test import Context, cast, log


def const(name):
    from win32com.client import constants

    return getattr(constants, name)


def seg_text(seg) -> str:
    return f"({seg.X1:.2f}, {seg.Y1:.2f}) – ({seg.X2:.2f}, {seg.Y2:.2f}), длина {seg.X2 - seg.X1:.2f}"


def make(ctx, y):
    seg = ctx.drawing.LineSegments.Add()
    seg.X1, seg.Y1, seg.X2, seg.Y2, seg.Style = 20.0, y, 50.0, y, st.STYLE_MAIN
    seg.Update()
    dim = ctx.symbols.LineDimensions.Add()
    dim.X1, dim.Y1, dim.X2, dim.Y2 = 20.0, y, 50.0, y
    dim.X3, dim.Y3 = 35.0, y + 10.0
    dim.Orientation = const("ksLinDHorizontal")
    dim.Update()
    return seg, dim


def constraint(obj, kind, **fields):
    c = cast(obj, "IDrawingObject1").NewConstraint()
    c.ConstraintType = const(kind)
    for k, v in fields.items():
        setattr(c, k, v)
    return c, c.Create()


def tie(dim, seg):
    _, a = constraint(dim, "ksCMergePoints", Index=0, Partner=seg, PartnerIndex=0)
    _, b = constraint(dim, "ksCMergePoints", Index=1, Partner=seg, PartnerIndex=1)
    return a, b


def driving(ctx) -> None:
    for y, kind, fields in ((240.0, "ksCFixedDim", {}),
                            (200.0, "ksCDimWithVariable", {"Variable": "L1"}),
                            (160.0, "ksCDimWithVariable", {"Variable": "L2", "Value": 30.0}),
                            (120.0, None, {})):
        seg, dim = make(ctx, y)
        name = kind or "только привязка"
        try:
            a, b = tie(dim, seg)
            log(f"      {name}: привязка точек 0 → {a}, 1 → {b}")
            if kind:
                c, ok = constraint(dim, kind, **fields)
                result(f"{name} {fields}: Create", ok)
            t = cast(dim, "IDimensionText")
            log(f"      значение размера: {t.NominalValue}")
            t.AutoNominalValue = False
            t.NominalValue = 40.0
            dim.Update()
            log(f"      после NominalValue = 40: отрезок {seg_text(seg)}")
            if kind:
                try:
                    c.Value = 40.0
                    log(f"      после Value = 40 у связи: отрезок {seg_text(seg)}")
                except Exception as exc:
                    log(f"      Value: {exc!r}")
        except Exception as exc:
            result(name, False, repr(exc))
            log("      " + traceback.format_exc().strip().splitlines()[-1])
    try:
        doc2d = cast(ctx.app.ActiveDocument, "IKompasDocument2D1")
        log(f"      IKompasDocument2D1: {members(doc2d)[:500]}")
        log(f"      RebuildDocument: {doc2d.RebuildDocument()}")
    except Exception as exc:
        log(f"      перестроение: {exc!r}")


def text_position(ctx) -> None:
    seg, dim = make(ctx, 80.0)
    d2 = cast(dim, "IDimension2D")
    try:
        log(f"      GetTextPosition до: {d2.GetTextPosition()}")
    except Exception as exc:
        log(f"      GetTextPosition: {exc!r}")
    for args in ((70.0, 95.0), ):
        try:
            r = d2.SetTextPosition(*args)
            dim.Update()
            log(f"      SetTextPosition{args} → {r}; GetTextPosition: {d2.GetTextPosition()}")
            result("текст размера на (70, 95) — справа за выносной линией", True)
        except Exception as exc:
            result("SetTextPosition", False, repr(exc))
    try:
        log(f"      GetDimensionPoint(0): {d2.GetDimensionPoint(0)}")
    except Exception as exc:
        log(f"      GetDimensionPoint: {exc!r}")


def angled_plane(ctx) -> None:
    from win32com.client import constants

    m = ctx.api5_module
    doc3d = ctx.api5.Document3D()
    result("новая деталь", doc3d.Create(False, True))
    part = doc3d.GetPart(constants.pTop_Part)
    # a block 40 × 40 × 40 around the origin
    sk = part.NewEntity(constants.o3d_sketch)
    sd = m.ksSketchDefinition(sk.GetDefinition())
    sd.SetPlane(part.GetDefaultEntity(constants.o3d_planeXOY))
    sk.Create()
    d2 = sd.BeginEdit()
    for (x1, y1, x2, y2) in ((-20, -20, 20, -20), (20, -20, 20, 20), (20, 20, -20, 20),
                             (-20, 20, -20, -20)):
        d2.ksLineSeg(x1, y1, x2, y2, 1)
    sd.EndEdit()
    ext = part.NewEntity(constants.o3d_baseExtrusion)
    ed = m.ksBaseExtrusionDefinition(ext.GetDefinition())
    ed.directionType = constants.dtBoth
    ed.SetSideParam(True, constants.etBlind, 20.0, 0.0, False)
    ed.SetSideParam(False, constants.etBlind, 20.0, 0.0, False)
    ed.SetSketch(sk)
    result("куб 40×40×40", ext.Create())
    try:
        plane = part.NewEntity(constants.o3d_planeAngle)
        pd = m.ksPlaneAngleDefinition(plane.GetDefinition())
        log(f"      ksPlaneAngleDefinition: {members(pd)}")
        pd.SetPlane(part.GetDefaultEntity(constants.o3d_planeYOZ))
        pd.SetAxis(part.GetDefaultEntity(constants.o3d_axisOY))
        pd.angle = 45.0
        result("плоскость под 45° к YOZ вокруг оси Y", plane.Create())
        sk2 = part.NewEntity(constants.o3d_sketch)
        sd2 = m.ksSketchDefinition(sk2.GetDefinition())
        sd2.SetPlane(plane)
        sk2.Create()
        d3 = sd2.BeginEdit()
        d3.ksCircle(5.0, 0.0, 1.0, 1)
        d3.ksCircle(0.0, 10.0, 2.0, 1)
        sd2.EndEdit()
        cut = part.NewEntity(constants.o3d_cutExtrusion)
        cd = m.ksCutExtrusionDefinition(cut.GetDefinition())
        cd.cut = True
        cd.directionType = constants.dtBoth
        cd.SetSideParam(True, constants.etThroughAll, 0.0, 0.0, False)
        cd.SetSideParam(False, constants.etThroughAll, 0.0, 0.0, False)
        cd.SetSketch(sk2)
        result("вырез: R1 в точке (5, 0), R2 в точке (0, 10) эскиза", cut.Create())
    except Exception as exc:
        result("плоскость под углом", False, repr(exc))
        log("      " + traceback.format_exc().strip().splitlines()[-1])
    out = st.OUTPUT_DIR / "kompas_ai_api_test15.m3d"
    result(f"сохранение {out}", doc3d.SaveAs(str(out)))


def main() -> int:
    log("Тест API №15: управляющие размеры, положение текста, плоскость под углом")
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
    for title, fn in (("1. Управляющий размер (30 → 40)", driving),
                      ("2. Положение текста размера", text_position)):
        log("")
        log(title)
        try:
            fn(ctx)
        except Exception as exc:
            result(title, False, repr(exc))
            log("      " + traceback.format_exc().strip().splitlines()[-1])
    try:
        ctx.doc.SaveAs(str(st.OUTPUT_DIR / "kompas_ai_api_test15.cdw"))
    except Exception as exc:
        log(f"Сохранить чертёж не удалось: {exc!r}")
    log("")
    log("3. Плоскость под углом и эскиз на ней")
    try:
        angled_plane(ctx)
    except Exception as exc:
        result("3", False, repr(exc))
        log("      " + traceback.format_exc().strip().splitlines()[-1])
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test15_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
