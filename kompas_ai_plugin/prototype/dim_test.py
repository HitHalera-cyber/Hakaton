"""Find the API5 parameters that give a correct linear dimension.

The smoke test created a linear dimension through ksLinDimension, but it was
drawn collapsed. This script draws the same 100 mm segment several times, each
with a different set of dimension parameters and a caption naming the
variant, so one screenshot shows which variant is right.

Run:  py dim_test.py
"""

from __future__ import annotations

import sys

import smoke_test as st
from smoke_test import Context, log

OUTPUT_FILE = st.OUTPUT_DIR / "kompas_ai_dim_test.cdw"

# name: (source-param overrides, drawing-param overrides, text-param overrides)
VARIANTS = {
    "A ps=1 dx=0 dy=-12": ({"ps": 1, "dx": 0.0, "dy": -12.0}, {}, {}),
    "B ps=0 dx=0 dy=-12": ({"ps": 0, "dx": 0.0, "dy": -12.0}, {}, {}),
    "C ps=1 dx=50 dy=-12": ({"ps": 1, "dx": 50.0, "dy": -12.0}, {}, {}),
    "D ps=1 dy=-12 bitFlag=1": ({"ps": 1, "dx": 0.0, "dy": -12.0}, {}, {"bitFlag": 1}),
    "E ps=1 dy=-12 pt1=pt2=1": ({"ps": 1, "dx": 0.0, "dy": -12.0}, {"pt1": 1, "pt2": 1}, {}),
}


def _apply(obj, values: dict, what: str) -> None:
    for name, value in values.items():
        try:
            setattr(obj, name, value)
        except Exception as exc:
            log(f"      {what}.{name} = {value}: {exc!r}")


def _dump(obj, what: str) -> None:
    """Log the readable properties of a parameter structure after Init()."""
    names = [n for n in getattr(obj, "_prop_map_get_", {}) if not n.startswith("_")]
    values = []
    for name in sorted(names):
        try:
            values.append(f"{name}={getattr(obj, name)!r}")
        except Exception:
            continue
    log(f"      {what}: " + ", ".join(values))


def draw_variant(ctx: Context, y: float, name: str, src_v: dict, drw_v: dict, txt_v: dict,
                 dump: bool) -> None:
    doc = ctx.api5.ActiveDocument2D()
    module = ctx.api5_module
    doc.ksLineSeg(20.0, y, 120.0, y, st.STYLE_MAIN)
    doc.ksText(130.0, y, 0.0, 3.5, 1.0, 0, name)

    par = module.ksLDimParam(ctx.api5.GetParamStruct(st.constant("ko_LDimParam")))
    src = module.ksLDimSourceParam(par.GetSPar())
    src.Init()
    drw = module.ksDimDrawingParam(par.GetDPar())
    drw.Init()
    txt = module.ksDimTextParam(par.GetTPar())
    txt.Init(False)
    if dump:
        _dump(src, "source после Init")
        _dump(drw, "drawing после Init")
        _dump(txt, "text после Init")

    src.x1, src.y1, src.x2, src.y2 = 20.0, y, 120.0, y
    src.basePoint = 1
    _apply(src, src_v, "source")
    _apply(drw, drw_v, "drawing")
    _apply(txt, txt_v, "text")

    ref = doc.ksLinDimension(par)
    log(f"[{'OK' if ref else 'FAIL'}]   {name}: ссылка {ref}")


def main() -> int:
    log("Тест вариантов линейного размера (API5)")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2

    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants),
                       ("Новый чертёж", st.step_new_drawing)]:
        print(f"...    {name}", flush=True)
        func(ctx)

    # Place everything inside the A4 sheet (origin = bottom-left corner).
    y = 250.0
    for i, (name, (src_v, drw_v, txt_v)) in enumerate(VARIANTS.items()):
        try:
            draw_variant(ctx, y, name, src_v, drw_v, txt_v, dump=(i == 0))
        except Exception as exc:
            log(f"[FAIL] {name}: {exc!r}")
        y -= 40.0

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ctx.doc.SaveAs(str(OUTPUT_FILE))
    log(f"Сохранено: {OUTPUT_FILE}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("dim_test_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
