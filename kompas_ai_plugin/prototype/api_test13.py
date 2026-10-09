"""Thirteenth API test: radius value position and fixing constraints.

1. Radius dimension through API5 with ksRDimDrawingParam.textPos = 0, 10, 25:
   the program now puts a fillet's value where the source drawing has it by
   this field (api_test12 showed API7 ShelfX/ShelfY are ignored).
2. A 3D sketch with «зафиксировать точку» (ksCFixedPoint) on a line and on
   an arc end and «фиксированная длина» (ksCFixedLenght): the program uses
   them to make the revolve sketch fully defined.

Run:  py api_test13.py   — then send api_test13_report.txt and a screenshot of
the drawing (labels J, K, L readable) and of the part tree with the sketch.
"""

from __future__ import annotations

import sys
import traceback

import smoke_test as st
from api_test7 import result
from api_test11 import const
from api_test12 import label, param, sub
from smoke_test import Context, cast, log


def radial(ctx, x, y, name, text_pos):
    doc = ctx.api5.ActiveDocument2D()
    doc.ksArcByAngle(x, y, 3.0, 270.0, 360.0, 1, st.STYLE_MAIN)
    par = param(ctx, "ko_RDimParam", "ksRDimParam")
    src = sub(ctx, "ksRDimSourceParam", par.GetSPar())
    src.Init()
    src.xc, src.yc, src.rad = x, y, 3.0
    drw = sub(ctx, "ksRDimDrawingParam", par.GetDPar())
    drw.Init()
    drw.ang = -45.0
    if text_pos is not None:
        drw.textPos = text_pos
    txt = sub(ctx, "ksDimTextParam", par.GetTPar())
    txt.Init(False)
    txt.bitFlag = 1
    ok = doc.ksRadDimension(par)
    label(ctx, x - 5, y - 15, name)
    result(f"радиус {name}", ok)


def sketch_fixing(ctx) -> None:
    m, app7 = ctx.api5_module, ctx.app
    doc3d = ctx.api5.Document3D()
    result("новая деталь", doc3d.Create(False, True))
    part = doc3d.GetPart(const("pTop_Part", -1))
    sketch = part.NewEntity(const("o3d_sketch", 5))
    sdef = m.ksSketchDefinition(sketch.GetDefinition())
    sdef.SetPlane(part.GetDefaultEntity(const("o3d_planeXOY", 1)))
    sketch.Create()
    sdef.BeginEdit()
    try:
        doc2d = cast(app7.ActiveDocument, "IKompasDocument2D")
        drawing = cast(doc2d.ViewsAndLayersManager.Views.ActiveView, "IDrawingContainer")
        seg = drawing.LineSegments.Add()
        seg.X1, seg.Y1, seg.X2, seg.Y2, seg.Style = 0.0, 5.0, 20.0, 5.0, 1
        seg.Update()
        from win32com.client import dynamic
        arc = dynamic.Dispatch(drawing._oleobj_).Arcs.Add()
        arc.Xc, arc.Yc, arc.Radius = 20.0, 6.0, 1.0
        arc.Angle1, arc.Angle2, arc.Direction, arc.Style = 270.0, 360.0, False, 1  # False = CCW
        result("дуга (позднее связывание)", arc.Update())
        log(f"      хранится: Angle1={arc.Angle1}, Angle2={arc.Angle2}, Direction={arc.Direction}")
        cross = dynamic.Dispatch(drawing._oleobj_).Arcs.Add()
        cross.Xc, cross.Yc, cross.Radius = 40.0, 6.0, 1.0
        cross.Angle1, cross.Angle2, cross.Direction, cross.Style = 300.0, 30.0, False, 1
        cross.Update()
        log(f"      дуга через 0° (300→30): Angle1={cross.Angle1}, Angle2={cross.Angle2}, "
            f"Direction={cross.Direction}")
        for name, fn in [
            ("объединение точек отрезок–дуга", lambda: constrain(seg, "ksCMergePoints", Index=1,
                                                                 Partner=arc, PartnerIndex=0)),
            ("касание отрезок–дуга", lambda: constrain(seg, "ksCTangentTwoCurves", Partner=arc)),
            ("горизонталь", lambda: constrain(seg, "ksCHorizontal")),
            ("фиксировать точку (начало отрезка)", lambda: constrain(seg, "ksCFixedPoint", Index=0)),
            ("фиксированная длина отрезка", lambda: constrain(seg, "ksCFixedLenght")),
            ("фиксировать точку (конец дуги)", lambda: constrain(arc, "ksCFixedPoint", Index=1)),
        ]:
            try:
                result(name, constrain_any(seg, arc, fn))
            except Exception as exc:
                result(name, False, repr(exc))
    except Exception as exc:
        result("эскиз", False, repr(exc))
        log("      " + traceback.format_exc().strip().splitlines()[-1])
    sdef.EndEdit()
    out = st.OUTPUT_DIR / "kompas_ai_api_test13.m3d"
    result(f"сохранение {out}", doc3d.SaveAs(str(out)))


def constrain_any(seg, arc, fn):
    return fn()


def as_object1(obj):
    """IDrawingObject1 of obj; for a late-bound arc through QueryInterface
    (the way the program does it when CastTo fails)."""
    try:
        return cast(obj, "IDrawingObject1")
    except Exception as exc:
        log(f"      CastTo не сработал ({exc!r}) — QueryInterface")
        import pythoncom
        from win32com.client import dynamic, gencache

        mod = gencache.GetModuleForTypelib("{69AC2981-37C0-4379-84FD-5DD2F3C0A520}", 0, 1, 0)
        iid = mod.NamesToIIDMap["IDrawingObject1"]
        return dynamic.Dispatch(obj._oleobj_.QueryInterface(iid, pythoncom.IID_IDispatch))


def constrain(obj, kind, **fields):
    c = as_object1(obj).NewConstraint()
    if c is None:
        raise RuntimeError("NewConstraint() вернул None")
    c.ConstraintType = const(kind)
    for k, v in fields.items():
        setattr(c, k, v)
    return c.Create()


def main() -> int:
    log("Тест API №13: положение текста радиуса и фиксирующие связи эскиза")
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
    log("")
    log("1. Радиус: textPos")
    for x, name, pos in ((40.0, "J textPos нет", None), (110.0, "K textPos=10", 10.0),
                         (180.0, "L textPos=25", 25.0)):
        try:
            radial(ctx, x, 200.0, name, pos)
        except Exception as exc:
            result(name, False, repr(exc))
    try:
        ctx.doc.SaveAs(str(st.OUTPUT_DIR / "kompas_ai_api_test13.cdw"))
    except Exception as exc:
        log(f"Сохранить чертёж не удалось: {exc!r}")
    log("")
    log("2. Эскиз: фиксирующие связи")
    sketch_fixing(ctx)
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test13_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
