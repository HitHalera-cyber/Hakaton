"""Eleventh API test: a parametric 3D sketch and a thread on the model.

1. Sketch constraints. The 3D sketch is edited through API5 (BeginEdit gives
   a ksDocument2D); constraints need API7 objects. Two ways are tried:
   a) API7 IApplication.TransferReference(API5 reference, API5 document)
      turns an API5 sketch line into an API7 object;
   b) while the sketch is open, the active API7 document is the sketch —
      its lines are created through API7 directly.
   Each way sets «горизонталь» and «объединение точек».
2. A cosmetic thread (условное изображение резьбы) M20×1,5 on the outer
   cylinder of a revolved rod: the face is found by a point on it.

Run:  py api_test11.py   — then send api_test11_report.txt and a screenshot of
the part with the sketch opened (its tree shows the constraints) and of the thread.
"""

from __future__ import annotations

import sys
import traceback

import smoke_test as st
from api_test7 import members, result
from smoke_test import Context, cast, log


def const(name, fallback=None):
    from win32com.client import constants

    try:
        return getattr(constants, name)
    except AttributeError:
        if fallback is None:
            raise
        log(f"      константа {name} не найдена, беру {fallback}")
        return fallback


def constrain(obj, kind, **fields):
    c = cast(obj, "IDrawingObject1").NewConstraint()
    if c is None:
        raise RuntimeError("NewConstraint() вернул None")
    c.ConstraintType = const(kind)
    for k, v in fields.items():
        setattr(c, k, v)
    return c.Create()


def safe(name, fn):
    try:
        result(name, fn())
    except Exception as exc:
        result(name, False, repr(exc))


def main() -> int:
    log("Тест API №11: параметрический эскиз и резьба на модели")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2
    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants)]:
        print(f"...    {name}", flush=True)
        func(ctx)
    m, app7 = ctx.api5_module, ctx.app
    doc3d = ctx.api5.Document3D()
    result("новая деталь", doc3d.Create(False, True))
    part = doc3d.GetPart(const("pTop_Part", -1))
    sketch = part.NewEntity(const("o3d_sketch", 5))
    sdef = m.ksSketchDefinition(sketch.GetDefinition())
    sdef.SetPlane(part.GetDefaultEntity(const("o3d_planeXOY", 1)))
    sketch.Create()
    d2 = sdef.BeginEdit()

    log("")
    log("1a. TransferReference (API5 → API7)")
    r1 = d2.ksLineSeg(0.0, 0.0, 0.0, 10.0, 1)
    r2 = d2.ksLineSeg(0.0, 10.0, 40.0, 10.3, 1)      # almost horizontal on purpose
    r3 = d2.ksLineSeg(40.0, 10.0, 40.0, 0.0, 1)
    r4 = d2.ksLineSeg(40.0, 0.0, 0.0, 0.0, 1)
    d2.ksLineSeg(-5.0, 0.0, 45.0, 0.0, 3)             # axis
    try:
        log(f"      IApplication: {members(app7)}")
        o2 = app7.TransferReference(r2, d2.reference)
        log(f"      TransferReference → {o2!r}")
        o3 = app7.TransferReference(r3, d2.reference)
        safe("горизонталь на верхней стороне (a)", lambda: constrain(o2, "ksCHorizontal"))
        safe("объединение точек (a)", lambda: constrain(o2, "ksCMergePoints", Index=1,
                                                        Partner=o3, PartnerIndex=0))
    except Exception as exc:
        result("1a", False, repr(exc))
    _ = (r1, r4)

    log("")
    log("1b. Активный документ API7 во время редактирования эскиза")
    try:
        active = app7.ActiveDocument
        log(f"      ActiveDocument: {active!r}; {members(active)[:300]}")
        doc2d = cast(active, "IKompasDocument2D")
        drawing = cast(doc2d.ViewsAndLayersManager.Views.ActiveView, "IDrawingContainer")
        seg = drawing.LineSegments.Add()
        seg.X1, seg.Y1, seg.X2, seg.Y2, seg.Style = 50.0, 0.0, 50.0, 8.2, 1
        result("отрезок API7 в эскизе (b)", seg.Update())
        safe("вертикаль (b)", lambda: constrain(seg, "ksCVertical"))
    except Exception as exc:
        result("1b", False, repr(exc))
    sdef.EndEdit()

    rot = part.NewEntity(const("o3d_baseRotated", 25))
    rdef = m.ksBaseRotatedDefinition(rot.GetDefinition())
    rdef.SetSideParam(True, 360.0)
    rdef.SetSketch(sketch)
    result("вращение (стержень Ø20×40)", rot.Create())

    log("")
    log("2. Условная резьба M20×1,5 на цилиндре")
    try:
        faces = part.EntityCollection(const("o3d_face", 6))
        log(f"      ksEntityCollection: {members(faces)}")
        ok = faces.SelectByPoint(20.0, 10.0, 0.0)  # a point on the Ø20 cylinder
        log(f"      SelectByPoint → {ok}, граней {faces.GetCount()}")
        face = faces.First()
        thread = part.NewEntity(const("o3d_thread", 0))
        log(f"      сущность резьбы: {thread!r}")
        tdef = m.ksThreadDefinition(thread.GetDefinition())
        log(f"      ksThreadDefinition: {members(tdef)}")
        for name, value in (("allLength", True), ("dr", 20.0), ("p", 1.5), ("faceValue", True)):
            try:
                setattr(tdef, name, value)
            except Exception as exc:
                log(f"      {name}: {exc!r}")
        tdef.SetBaseObject(face)
        result("резьба создана", thread.Create())
    except Exception as exc:
        result("2", False, repr(exc))
        log("      " + traceback.format_exc().strip().splitlines()[-1])

    out = st.OUTPUT_DIR / "kompas_ai_api_test11.m3d"
    out.parent.mkdir(parents=True, exist_ok=True)
    result(f"сохранение {out}", doc3d.SaveAs(str(out)))
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test11_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
