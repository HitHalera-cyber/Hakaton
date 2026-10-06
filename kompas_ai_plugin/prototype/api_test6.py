"""Sixth API test: which text item flag makes an index.

api_test5 showed that ksTextItemParam.type (ksTItSLowerIndex = 9 …) is
ignored by API5: every variant was drawn as plain text. In API5 fractions,
deviations and indices are flags of the item font (ksTextItemFont.bitVector),
whose values are not in the type library. Each row below sets one candidate
flag on «кав» (and the deviation flags as a known reference), labelled with
its value; the screenshot shows which one draws «кав» as a lower index.

Run:  py api_test6.py   — then send api_test6_report.txt and a zoomed screenshot.
"""

from __future__ import annotations

import sys

import smoke_test as st
from smoke_test import Context, log


def param(ctx, struct_const, interface):
    return getattr(ctx.api5_module, interface)(ctx.api5.GetParamStruct(st.constant(struct_const)))


def sub(ctx, interface, raw):
    return getattr(ctx.api5_module, interface)(raw)


def paragraph(ctx, x, y, items):
    """items = [(text, item_type, bit_vector)]"""
    doc = ctx.api5.ActiveDocument2D()
    par = param(ctx, "ko_ParagraphParam", "ksParagraphParam")
    par.Init()
    par.x, par.y, par.ang = x, y, 0.0
    doc.ksParagraph(par)
    line = param(ctx, "ko_TextLineParam", "ksTextLineParam")
    line.Init()
    arr = sub(ctx, "ksDynamicArray", line.GetTextItemArr())
    for text, item_type, flags in items:
        item = param(ctx, "ko_TextItemParam", "ksTextItemParam")
        item.Init()
        font = sub(ctx, "ksTextItemFont", item.GetItemFont())
        font.Init()
        font.height, font.ksu, font.bitVector = 5.0, 1.0, flags
        item.s, item.type = text, item_type
        arr.ksAddArrayItem(-1, item)
    doc.ksTextLine(line)
    return doc.ksEndObj()


def main() -> int:
    log("Тест API №6: флаги индекса в тексте")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2
    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants),
                       ("Новый чертёж", st.step_new_drawing)]:
        print(f"...    {name}", flush=True)
        func(ctx)

    variants = [
        # reference: deviation flags (upper empty, lower «кав») — a stacked small text
        ("отклонение 0x8/0x10/0x20", [("P", 0, 0), ("", 4, 0x8), ("кав", 5, 0x10), ("", 6, 0x20),
                                     ("=3,38", 0, 0)]),
        ("индекс тип+флаг 7/9/16", [("P", 7, 0), ("кав", 9, 0), ("", 16, 0), ("=3,38", 0, 0)]),
    ]
    for bit in range(6, 26):
        value = 1 << bit
        variants.append((f"флаг 0x{value:X}", [("P", 0, 0), ("кав", 0, value), ("=3,38", 0, 0)]))

    y, x = 285.0, 25.0
    for name, items in variants:
        try:
            ref = paragraph(ctx, x, y, items)
            log(f"[{'OK' if ref else 'FAIL'}]   {name}: ссылка {ref}")
        except Exception as exc:
            log(f"[FAIL] {name}: {exc!r}")
        try:
            ctx.api5.ActiveDocument2D().ksText(x + 45.0, y, 0.0, 3.5, 1.0, 0, name)
        except Exception:
            pass
        y -= 11.0
        if y < 65.0:
            y, x = 285.0, 115.0

    out = st.OUTPUT_DIR / "kompas_ai_api_test6.cdw"
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx.doc.SaveAs(str(out))
    log(f"Сохранено: {out}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test6_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
