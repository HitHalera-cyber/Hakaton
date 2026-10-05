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

# Findings of the first run (KOMPAS v22): after Init() ps=2; ps=0 gave a correct
# parallel dimension but without the value text, ps=1 collapsed on a horizontal
# segment (so ps=1 is presumably "vertical"). This run checks the text flags and
# the vertical type on a vertical segment.
#
# name: (segment, source overrides, drawing overrides, text overrides)
# A text override "_init": True calls txt.Init(True) instead of txt.Init(False).
H_SEG = (20.0, 0.0, 120.0, 0.0)  # relative to the variant's base y
V_SEG = (20.0, 0.0, 20.0, -25.0)
AUTO = "AUTO"  # replaced by the auto-nominal flag found in the constants

VARIANTS = {
    "F ps=2": (H_SEG, {"ps": 2, "dy": -12.0}, {}, {}),
    "G ps=2 auto": (H_SEG, {"ps": 2, "dy": -12.0}, {}, {"bitFlag": AUTO}),
    "H ps=0 auto": (H_SEG, {"ps": 0, "dy": -12.0}, {}, {"bitFlag": AUTO}),
    "I ps=2 Init(True)": (H_SEG, {"ps": 2, "dy": -12.0}, {}, {"_init": True}),
    "J ps=1 vert auto": (V_SEG, {"ps": 1, "dx": -12.0}, {}, {"bitFlag": AUTO}),
}


TEXT_FLAG_KEYS = ("NOMINAL", "TOLERANCE", "DEVIAT", "PREFIX", "SUFFIX", "RECTTEXT")


def log_text_constants() -> int:
    """Log constants that look like dimension text flags; return the auto-nominal one."""
    from win32com.client import constants

    found = {}
    for table in constants.__dicts__:
        for name, value in table.items():
            upper = name.upper()
            if any(key in upper for key in TEXT_FLAG_KEYS):
                found[name] = value
    for name in sorted(found):
        log(f"      константа {name} = {found[name]}")
    for name in ("_AUTONOMINAL", "ksAutoNominal", "AUTONOMINAL"):
        if name in found:
            return int(found[name])
    log("      флаг автономинала не найден, использую 1")
    return 1


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


def draw_variant(ctx: Context, y: float, name: str, seg: tuple, src_v: dict, drw_v: dict,
                 txt_v: dict, dump: bool) -> None:
    doc = ctx.api5.ActiveDocument2D()
    module = ctx.api5_module
    x1, y1, x2, y2 = seg[0], y + seg[1], seg[2], y + seg[3]
    doc.ksLineSeg(x1, y1, x2, y2, st.STYLE_MAIN)
    doc.ksText(130.0, y, 0.0, 3.5, 1.0, 0, name)

    par = module.ksLDimParam(ctx.api5.GetParamStruct(st.constant("ko_LDimParam")))
    src = module.ksLDimSourceParam(par.GetSPar())
    src.Init()
    drw = module.ksDimDrawingParam(par.GetDPar())
    drw.Init()
    txt = module.ksDimTextParam(par.GetTPar())
    txt_v = dict(txt_v)
    txt.Init(bool(txt_v.pop("_init", False)))
    if dump:
        _dump(src, "source после Init")
        _dump(drw, "drawing после Init")
        _dump(txt, "text после Init")

    src.x1, src.y1, src.x2, src.y2 = x1, y1, x2, y2
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
    auto_flag = log_text_constants()
    y = 250.0
    for i, (name, (seg, src_v, drw_v, txt_v)) in enumerate(VARIANTS.items()):
        txt_v = {k: (auto_flag if v == AUTO else v) for k, v in txt_v.items()}
        try:
            draw_variant(ctx, y, name, seg, src_v, drw_v, txt_v, dump=(i == 0))
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
