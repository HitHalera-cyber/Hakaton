"""Twelfth API test: how to lay dimensions out like on a real drawing.

Problems seen on the fitting (штуцер) in KOMPAS:
  * an angular dimension draws its extension lines from the vertex (the two
    60° lines meet at the cone apex) — the drawing has them only from the
    cone sides outwards;
  * small radius values land on the part — they belong on a shelf outside;
  * values of small linear dimensions overlap — they belong outside on a shelf.
This test lists the fields of the dimension parameter structures and builds
labelled variants side by side; the screenshot shows which variant looks
right.

Run:  py api_test12.py   — then send api_test12_report.txt and a screenshot
(zoom so the labels are readable).
"""

from __future__ import annotations

import math
import sys
import traceback

import smoke_test as st
from api_test7 import members, result
from smoke_test import Context, cast, log


def param(ctx, const_name, interface):
    return getattr(ctx.api5_module, interface)(ctx.api5.GetParamStruct(st.constant(const_name)))


def sub(ctx, interface, raw):
    return getattr(ctx.api5_module, interface)(raw)


def label(ctx, x, y, text):
    ctx.api5.ActiveDocument2D().ksText(x, y, 0.0, 2.5, 1.0, 0, text)


def dump_structures(ctx) -> None:
    for const_name, iface in (("ko_LDimParam", "ksLDimParam"), ("ko_ADimParam", "ksADimParam"),
                              ("ko_RDimParam", "ksRDimParam")):
        par = param(ctx, const_name, iface)
        log(f"      {iface}: {members(par)}")
        for getter in ("GetSPar", "GetDPar", "GetTPar"):
            try:
                log(f"        {getter}: {members(getattr(par, getter)())}")
            except Exception as exc:
                log(f"        {getter}: {exc!r}")
    for iface in ("ksLDimSourceParam", "ksADimSourceParam", "ksRDimSourceParam",
                  "ksDimDrawingParam", "ksRDimDrawingParam", "ksDimTextParam"):
        try:
            cls = getattr(ctx.api5_module, iface)
            props = sorted(getattr(cls, "_prop_map_get_", {}).keys())
            log(f"      {iface}: свойства {', '.join(props)}")
        except Exception as exc:
            log(f"      {iface}: {exc!r}")
    result("структуры перечислены", True)


def angular(ctx, x, y, name, drawing_fields):
    doc = ctx.api5.ActiveDocument2D()
    # a cone: two sides meeting at (x, y) at ±30°, drawn from 20 to 35 mm off the apex
    for s in (1, -1):
        a = math.radians(30 * s)
        doc.ksLineSeg(x + 20 * math.cos(a), y + 20 * math.sin(a),
                      x + 35 * math.cos(a), y + 35 * math.sin(a), st.STYLE_MAIN)
    par = param(ctx, "ko_ADimParam", "ksADimParam")
    src = sub(ctx, "ksADimSourceParam", par.GetSPar())
    src.Init()
    src.xc, src.yc, src.ang1, src.ang2, src.rad, src.dir = x, y, -30.0, 30.0, 40.0, 1
    drw = sub(ctx, "ksDimDrawingParam", par.GetDPar())
    drw.Init()
    for k, v in drawing_fields.items():
        try:
            setattr(drw, k, v)
        except Exception as exc:
            log(f"      {name}: поле {k}: {exc!r}")
    txt = sub(ctx, "ksDimTextParam", par.GetTPar())
    txt.Init(False)
    txt.bitFlag = 1
    ok = doc.ksAngDimension(par)
    label(ctx, x - 5, y - 18, name)
    result(f"угловой {name}", ok)


def radial7(ctx, x, y, name, shelf):
    doc = ctx.api5.ActiveDocument2D()
    doc.ksArcByAngle(x, y, 3.0, 90.0, 180.0, 1, st.STYLE_MAIN)
    dim = ctx.symbols.RadialDimensions.Add()
    dim.Xc, dim.Yc, dim.Radius, dim.Angle = x, y, 3.0, 135.0
    if shelf:
        dim.ShelfX, dim.ShelfY = shelf
    try:
        log(f"      IDimensionParams: {members(cast(dim, 'IDimensionParams'))}")
    except Exception as exc:
        log(f"      IDimensionParams: {exc!r}")
    ok = dim.Update()
    label(ctx, x - 5, y - 12, name)
    result(f"радиус {name}", ok)
    if ok:
        log(f"      после Update: ShelfX={dim.ShelfX}, ShelfY={dim.ShelfY}")


def linear7(ctx, x, y, name, params):
    doc = ctx.api5.ActiveDocument2D()
    doc.ksLineSeg(x, y, x + 3.0, y, st.STYLE_MAIN)  # a short 3 mm step
    dim = ctx.symbols.LineDimensions.Add()
    dim.X1, dim.Y1, dim.X2, dim.Y2 = x, y, x + 3.0, y
    dim.X3, dim.Y3 = x + 1.5, y - 8.0
    dim.Orientation = st.constant("ksLinDHorizontal")
    try:
        p = cast(dim, "IDimensionParams")
        if not linear7.dumped:
            log(f"      IDimensionParams (линейный): {members(p)}")
            linear7.dumped = True
        for k, v in params.items():
            try:
                setattr(p, k, v)
            except Exception as exc:
                log(f"      {name}: {k}: {exc!r}")
    except Exception as exc:
        log(f"      IDimensionParams: {exc!r}")
    ok = dim.Update()
    label(ctx, x - 5, y - 18, name)
    result(f"линейный {name}", ok)


linear7.dumped = False


def main() -> int:
    log("Тест API №12: расположение размеров")
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
    steps = [
        ("1. Поля структур размеров", lambda: dump_structures(ctx)),
        ("2. Угловой: выносные линии", lambda: [
            angular(ctx, 40.0, 240.0, "A по умолч.", {}),
            angular(ctx, 110.0, 240.0, "B pl1=pl2=0", {"pl1": 0, "pl2": 0}),
            angular(ctx, 180.0, 240.0, "C pl1=pl2=1", {"pl1": 1, "pl2": 1}),
        ]),
        ("3. Радиус: полка (API7)", lambda: [
            radial7(ctx, 40.0, 160.0, "D без полки", None),
            radial7(ctx, 110.0, 160.0, "E полка (+15,+10)", (125.0, 170.0)),
            radial7(ctx, 180.0, 160.0, "F полка (-15,+10)", (165.0, 170.0)),
        ]),
        ("4. Линейный 3 мм: текст снаружи (API7)", lambda: [
            linear7(ctx, 40.0, 100.0, "G по умолч.", {}),
            linear7(ctx, 110.0, 100.0, "H TextPos=2", {"TextPos": 2}),
            linear7(ctx, 180.0, 100.0, "I ShelfDirection=1", {"ShelfDirection": 1}),
        ]),
    ]
    for name, fn in steps:
        log("")
        log(name)
        try:
            fn()
        except Exception as exc:
            result(name, False, repr(exc))
            log("      " + traceback.format_exc().strip().splitlines()[-1])
    out = st.OUTPUT_DIR / "kompas_ai_api_test12.cdw"
    try:
        ctx.doc.SaveAs(str(out))
        log(f"\nСохранено: {out}")
    except Exception as exc:
        log(f"\nСохранить не удалось: {exc!r}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test12_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
