"""Second API test: everything still unverified for writing a drawing into KOMPAS.

One run checks (each part independently, failures are logged and skipped):
  1. linear dimension text — variants F–J (from dim_test.py);
  2. radius dimension;
  3. diameter dimension with the Ø sign set explicitly;
  4. angular dimension between two lines;
  5. hatch inside a rectangle;
  6. a view with scale 5:1 (a circle R5 in the view must look R25 on the sheet);
  7. sheet format A3 landscape.

Parameter structures are dumped after Init(), so even a failed part shows
the real field names of this KOMPAS version.

Run:  py api_test2.py   — then send api_test2_report.txt and a screenshot.
"""

from __future__ import annotations

import sys

import dim_test as dt
import smoke_test as st
from smoke_test import Context, log

OUTPUT_FILE = st.OUTPUT_DIR / "kompas_ai_api_test2.cdw"


def label(ctx: Context, x: float, y: float, text: str) -> None:
    ctx.api5.ActiveDocument2D().ksText(x, y, 0.0, 3.5, 1.0, 0, text)


def param(ctx: Context, struct_const: str, interface: str):
    return getattr(ctx.api5_module, interface)(ctx.api5.GetParamStruct(st.constant(struct_const)))


def sub(ctx: Context, interface: str, raw):
    return getattr(ctx.api5_module, interface)(raw)


def result(name: str, ref) -> None:
    log(f"[{'OK' if ref else 'FAIL'}]   {name}: ссылка {ref}")


# --- 1. linear dimension text ----------------------------------------------------

def part_linear(ctx: Context) -> None:
    auto_flag = dt.log_text_constants()
    y = 285.0
    for i, (name, (seg, src_v, drw_v, txt_v)) in enumerate(dt.VARIANTS.items()):
        txt_v = {k: (auto_flag if v == dt.AUTO else v) for k, v in txt_v.items()}
        try:
            dt.draw_variant(ctx, y, name, seg, src_v, drw_v, txt_v, dump=(i == 0))
        except Exception as exc:
            log(f"[FAIL] {name}: {exc!r}")
        y -= 22.0 if seg is dt.H_SEG else 32.0


# --- 2, 3. radius and diameter ------------------------------------------------------

def _radial(ctx: Context, kind: str, xc: float, yc: float, r: float, sign: int | None) -> None:
    doc = ctx.api5.ActiveDocument2D()
    doc.ksCircle(xc, yc, r, st.STYLE_MAIN)
    par = param(ctx, "ko_RDimParam", "ksRDimParam")
    src = sub(ctx, "ksRDimSourceParam", par.GetSPar())
    src.Init()
    drw = sub(ctx, "ksRDimDrawingParam", par.GetDPar())
    drw.Init()
    txt = sub(ctx, "ksDimTextParam", par.GetTPar())
    txt.Init(False)
    if kind == "radius":
        dt._dump(src, "rdim source после Init")
        dt._dump(drw, "rdim drawing после Init")
    src.xc, src.yc, src.rad = xc, yc, r
    drw.ang = 45.0
    txt.bitFlag = 1
    if sign is not None:
        txt.sign = sign
    method = doc.ksRadDimension if kind == "radius" else doc.ksDiamDimension
    result(f"{kind} sign={sign}", method(par))


def part_radius(ctx: Context) -> None:
    _radial(ctx, "radius", 45.0, 150.0, 10.0, None)
    label(ctx, 30.0, 135.0, "R10 (радиус)")


def part_diameter(ctx: Context) -> None:
    _radial(ctx, "diameter", 95.0, 150.0, 10.0, 1)
    label(ctx, 80.0, 135.0, "Ø20 sign=1")


# --- 4. angular -------------------------------------------------------------------

def part_angular(ctx: Context) -> None:
    doc = ctx.api5.ActiveDocument2D()
    xc, yc = 130.0, 135.0
    doc.ksLineSeg(xc, yc, xc + 50.0, yc, st.STYLE_MAIN)
    doc.ksLineSeg(xc, yc, xc + 35.355, yc + 35.355, st.STYLE_MAIN)  # 45°
    label(ctx, 170.0, 130.0, "угол 45°")
    par = param(ctx, "ko_ADimParam", "ksADimParam")
    src = sub(ctx, "ksADimSourceParam", par.GetSPar())
    src.Init()
    drw = sub(ctx, "ksADimDrawingParam", par.GetDPar())
    drw.Init()
    txt = sub(ctx, "ksDimTextParam", par.GetTPar())
    txt.Init(False)
    dt._dump(src, "adim source после Init")
    dt._dump(drw, "adim drawing после Init")
    dt._apply(src, {"xc": xc, "yc": yc, "ang1": 0.0, "ang2": 45.0, "rad": 30.0, "dir": True},
              "adim source")
    txt.bitFlag = 1
    result("угловой размер ksAngDimension", doc.ksAngDimension(par))


# --- 5. hatch ---------------------------------------------------------------------

def part_hatch(ctx: Context) -> None:
    doc = ctx.api5.ActiveDocument2D()
    x0, y0, x1, y1 = 30.0, 75.0, 80.0, 105.0
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        doc.ksLineSeg(a[0], a[1], b[0], b[1], st.STYLE_MAIN)
    label(ctx, 30.0, 66.0, "штриховка 45°, шаг 2")
    # ksHatch opens a hatch; the objects created until ksEndObj form its boundary.
    opened = doc.ksHatch(0, 45.0, 2.0, 0.0, 0.0, 0.0)
    log(f"      ksHatch вернул {opened}")
    for a, b in zip(corners, corners[1:] + corners[:1]):
        doc.ksLineSeg(a[0], a[1], b[0], b[1], st.STYLE_MAIN)
    result("штриховка ksHatch + ksEndObj", doc.ksEndObj())


# --- 6. view with scale ------------------------------------------------------------

def part_view(ctx: Context) -> None:
    doc = ctx.api5.ActiveDocument2D()
    par = param(ctx, "ko_ViewParam", "ksViewParam")
    par.Init()
    dt._dump(par, "view после Init")
    dt._apply(par, {"x": 160.0, "y": 92.0, "scale_": 5.0, "name": "Вид 5:1"}, "view")
    ref = doc.ksCreateSheetView(par, 2)
    result("вид с масштабом ksCreateSheetView", ref)
    # In the new (current) view coordinates are model mm: R5 must look R25.
    result("окружность R5 в виде 5:1", doc.ksCircle(0.0, 0.0, 5.0, st.STYLE_MAIN))
    doc.ksLineSeg(-8.0, 0.0, 8.0, 0.0, st.STYLE_AXIAL)
    # view coordinates are scaled too: 0.7 mm text looks 3.5 mm on the sheet
    doc.ksText(-5.0, 6.0, 0.0, 0.7, 1.0, 0, "R5 в виде 5:1")


# --- 7. sheet format ---------------------------------------------------------------

def part_format(ctx: Context) -> None:
    sheets = ctx.doc.LayoutSheets
    log(f"      листов: {sheets.Count}")
    sheet = sheets.Item(0)
    fmt = sheet.Format
    log(f"      формат до: {fmt.Format}, вертикальный: {fmt.VerticalOrientation}")
    fmt.Format = st.constant("ksFormatA3", 3)
    fmt.VerticalOrientation = False
    ok = sheet.Update()
    log(f"      формат после: {fmt.Format}, вертикальный: {fmt.VerticalOrientation}")
    result("формат A3 альбомный (API7 LayoutSheets)", ok)


PARTS = [
    ("1. Текст линейного размера", part_linear),
    ("2. Радиус", part_radius),
    ("3. Диаметр со знаком Ø", part_diameter),
    ("4. Угловой размер", part_angular),
    ("5. Штриховка", part_hatch),
    ("6. Вид с масштабом 5:1", part_view),
    ("7. Формат листа A3", part_format),
]


def main() -> int:
    log("Тест API №2: размеры, штриховка, вид с масштабом, формат")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2
    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants),
                       ("Новый чертёж", st.step_new_drawing)]:
        print(f"...    {name}", flush=True)
        func(ctx)
    Context.last_api5 = ctx.api5

    for name, func in PARTS:
        print(f"...    {name}", flush=True)
        log(f"--- {name}")
        try:
            func(ctx)
        except Exception as exc:
            log(f"[FAIL] {name}: {exc!r}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        ctx.doc.SaveAs(str(OUTPUT_FILE))
        log(f"Сохранено: {OUTPUT_FILE}")
    except Exception as exc:
        log(f"[FAIL] Сохранение: {exc!r}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test2_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
