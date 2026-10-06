"""Fourth API test: dimension values written by hand.

The scaled view (ksCreateSheetView) is refused without a licence (error 216),
so a 5:1 drawing has to be drawn in sheet millimetres in the 1:1 system view.
Then the automatic value would show sheet size (50 instead of 10), so the
dimension text must be set explicitly. This run tries ways to do that, and
redraws the angular dimension for a visual check.

Run:  py api_test4.py   — then send api_test4_report.txt and a screenshot.
"""

from __future__ import annotations

import sys

import dim_test as dt
import smoke_test as st
from smoke_test import Context, log


def param(ctx, struct_const, interface):
    return getattr(ctx.api5_module, interface)(ctx.api5.GetParamStruct(st.constant(struct_const)))


def sub(ctx, interface, raw):
    return getattr(ctx.api5_module, interface)(raw)


def last_error(ctx):
    try:
        return ctx.api5.ksReturnResult()
    except Exception:
        return "?"


def set_text(ctx, txt, value: str) -> None:
    """Put ``value`` into the dimension text array (CHAR_STR_ARR of ksChar255)."""
    arr = sub(ctx, "ksDynamicArray", txt.GetTextArr())
    item = param(ctx, "ko_Char255", "ksChar255")
    item.str = value
    log(f"      ksAddArrayItem: {arr.ksAddArrayItem(-1, item)}")


def linear(ctx, y: float, name: str, flags: dict, text: str | None) -> None:
    doc = ctx.api5.ActiveDocument2D()
    doc.ksLineSeg(30.0, y, 80.0, y, st.STYLE_MAIN)  # 50 mm on the sheet = 10 mm at 5:1
    doc.ksText(110.0, y, 0.0, 3.5, 1.0, 0, name)
    par = param(ctx, "ko_LDimParam", "ksLDimParam")
    src = sub(ctx, "ksLDimSourceParam", par.GetSPar())
    src.Init()
    src.x1, src.y1, src.x2, src.y2 = 30.0, y, 80.0, y
    src.basePoint, src.ps, src.dy = 1, 2, -10.0
    sub(ctx, "ksDimDrawingParam", par.GetDPar()).Init()
    txt = sub(ctx, "ksDimTextParam", par.GetTPar())
    txt.Init(False)
    dt._apply(txt, flags, "text")
    if text is not None:
        try:
            set_text(ctx, txt, text)
        except Exception as exc:
            log(f"      текст не записан: {exc!r}")
    ref = doc.ksLinDimension(par)
    log(f"[{'OK' if ref else 'FAIL'}]   {name}: ссылка {ref}, код {last_error(ctx)}")


VARIANTS = [
    ("K: только текст '10'", {"bitFlag": 0}, "10"),
    ("L: stringFlag + '10'", {"bitFlag": 0, "stringFlag": True}, "10"),
    ("M: auto + текст '10'", {"bitFlag": 1}, "10"),
    ("N: 'Ø2,68' вручную", {"bitFlag": 0, "stringFlag": True}, "Ø2,68"),
    ("O: sign=1 + '2,68'", {"bitFlag": 0, "stringFlag": True, "sign": 1}, "2,68"),
]


def angular(ctx) -> None:
    doc = ctx.api5.ActiveDocument2D()
    xc, yc = 40.0, 110.0
    doc.ksLineSeg(xc, yc, xc + 50.0, yc, st.STYLE_MAIN)
    doc.ksLineSeg(xc, yc, xc + 35.355, yc + 35.355, st.STYLE_MAIN)
    doc.ksText(110.0, yc + 10.0, 0.0, 3.5, 1.0, 0, "угол 45° (должна быть дуга с 45°)")
    par = param(ctx, "ko_ADimParam", "ksADimParam")
    src = sub(ctx, "ksADimSourceParam", par.GetSPar())
    src.Init()
    sub(ctx, "ksDimDrawingParam", par.GetDPar()).Init()
    txt = sub(ctx, "ksDimTextParam", par.GetTPar())
    txt.Init(False)
    txt.bitFlag = 1
    src.xc, src.yc, src.ang1, src.ang2, src.rad, src.dir = xc, yc, 0.0, 45.0, 30.0, 1
    ref = doc.ksAngDimension(par)
    log(f"[{'OK' if ref else 'FAIL'}]   угловой: ссылка {ref}, код {last_error(ctx)}")


def main() -> int:
    log("Тест API №4: числа размеров вручную, угловой размер")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2
    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants),
                       ("Новый чертёж", st.step_new_drawing)]:
        print(f"...    {name}", flush=True)
        func(ctx)
    y = 270.0
    for name, flags, text in VARIANTS:
        try:
            linear(ctx, y, name, flags, text)
        except Exception as exc:
            log(f"[FAIL] {name}: {exc!r}")
        y -= 25.0
    try:
        angular(ctx)
    except Exception as exc:
        log(f"[FAIL] угловой: {exc!r}")
    out = st.OUTPUT_DIR / "kompas_ai_api_test4.cdw"
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx.doc.SaveAs(str(out))
    log(f"Сохранено: {out}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test4_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
