"""Fifth API test: text with subscripts (P_кав = 3,38).

A KOMPAS text with indices is a paragraph (ksParagraph) whose line
(ksTextLine) holds several items (ksTextItemParam) of different types. The
item type numbers for indices are not confirmed yet, so several candidate
sequences are drawn, each labelled; the screenshot shows which one renders
"P" with a lower index "кав".

Run:  py api_test5.py   — then send api_test5_report.txt and a zoomed screenshot.
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


def item_types() -> dict:
    """All text item type constants (ksTIt…) of this KOMPAS version."""
    from win32com.client import constants

    found = {}
    for table in constants.__dicts__:
        for name, value in table.items():
            if name.startswith("ksTIt") or "INDEX" in name.upper():
                found[name] = value
    for name in sorted(found, key=lambda n: (found[n], n)):
        log(f"      константа {name} = {found[name]}")
    return found


def paragraph(ctx, x, y, items, dump=False):
    """Draw one paragraph; items = [(text, type)]."""
    doc = ctx.api5.ActiveDocument2D()
    par = param(ctx, "ko_ParagraphParam", "ksParagraphParam")
    par.Init()
    if dump:
        dt._dump(par, "paragraph после Init")
    dt._apply(par, {"x": x, "y": y, "ang": 0.0, "height": 10.0, "width": 80.0}, "paragraph")
    doc.ksParagraph(par)

    line = param(ctx, "ko_TextLineParam", "ksTextLineParam")
    line.Init()
    arr = sub(ctx, "ksDynamicArray", line.GetTextItemArr())
    for i, (text, kind) in enumerate(items):
        item = param(ctx, "ko_TextItemParam", "ksTextItemParam")
        item.Init()
        font = sub(ctx, "ksTextItemFont", item.GetItemFont())
        font.Init()
        if dump and i == 0:
            dt._dump(item, "item после Init")
            dt._dump(font, "font после Init")
        dt._apply(font, {"height": 5.0, "ksu": 1.0}, "font")
        item.s = text
        item.type = kind
        arr.ksAddArrayItem(-1, item)
    doc.ksTextLine(line)
    return doc.ksEndObj()


def main() -> int:
    log("Тест API №5: текст с индексами")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2
    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants),
                       ("Новый чертёж", st.step_new_drawing)]:
        print(f"...    {name}", flush=True)
        func(ctx)

    t = item_types()

    def c(name, fallback):
        return t.get(name, fallback)

    upper, lower, dev_end = c("ksTItUpperDeviation", 4), c("ksTItLowerDeviation", 5), \
        c("ksTItDeviationEnd", 6)
    variants = [
        ("A: обычный текст", [("Pкав=3,38", 0)]),
        ("B: отклонения (пусто/кав)", [("P", 0), ("", upper), ("кав", lower), ("", dev_end),
                                       ("=3,38", 0)]),
    ]
    # Every constant that looks like an index type gets its own variant.
    base = next((v for n, v in t.items() if "BASE" in n.upper()), None)
    ends = [v for n, v in t.items() if "END" in n.upper() and "INDEX" in n.upper()] + \
        [v for n, v in t.items() if n.upper().endswith("SEND")]
    for name, value in sorted(t.items(), key=lambda kv: kv[1]):
        if "LOWER" in name.upper() and "DEVIAT" not in name.upper():
            seq = [("P", 0)]
            if base is not None:
                seq = [("P", base)]
            seq += [("кав", value)]
            if ends:
                seq += [("", ends[0])]
            seq += [("=3,38", 0)]
            variants.append((f"C: {name}", seq))
    # Plain guesses in case the constants are missing in this version.
    for guess in (7, 8, 9, 10, 11, 12):
        variants.append((f"D: тип {guess}", [("P", 0), ("кав", guess), ("=3,38", 0)]))

    y = 280.0
    for i, (name, items) in enumerate(variants):
        try:
            ref = paragraph(ctx, 30.0, y, items, dump=(i == 0))
            log(f"[{'OK' if ref else 'FAIL'}]   {name}: ссылка {ref}, элементы {items}")
        except Exception as exc:
            log(f"[FAIL] {name}: {exc!r}")
        try:
            ctx.api5.ActiveDocument2D().ksText(120.0, y, 0.0, 3.5, 1.0, 0, name)
        except Exception:
            pass
        y -= 18.0
        if y < 70:
            break

    out = st.OUTPUT_DIR / "kompas_ai_api_test5.cdw"
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx.doc.SaveAs(str(out))
    log(f"Сохранено: {out}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test5_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
