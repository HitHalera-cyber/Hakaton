"""Eighth API test: the exact item sequence of a text index (API7).

api_test7 showed that ITextItem.ItemType works with a licence: only the
variant that started with a base item (ksTItSBase) drew «кав» as an index,
but «=3,38» came right after «P» instead of after the index. Each row below
is one candidate sequence, labelled; the screenshot shows which one draws
P with the lower index «кав» followed by «=3,38».

Run:  py api_test8.py   — then send api_test8_report.txt and a zoomed screenshot.
"""

from __future__ import annotations

import sys

import smoke_test as st
from api_test7 import _item_type, result
from smoke_test import Context, cast, log


def rich_text(ctx: Context, x: float, y: float, items) -> str:
    obj = ctx.drawing.DrawingTexts.Add()
    obj.X, obj.Y = x, y
    text = cast(obj, "IText")
    line = text.Add()
    for value, kind in items:
        item = line.Add()
        item.ItemType = kind
        item.Str = value
        item.Update()
    obj.Update()
    return text.Str


def main() -> int:
    log("Тест API №8: последовательность элементов индекса")
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

    s = _item_type("ksTItString", 0)
    base = _item_type("ksTItSBase", 7)
    up = _item_type("ksTItSUpperIndex", 8)
    low = _item_type("ksTItSLowerIndex", 9)
    end = _item_type("ksTItSEnd", 16)
    log(f"типы: строка={s}, база={base}, верхний={up}, нижний={low}, конец={end}")
    variants = [
        ("1 база,верх'',низ,конец,стр", [("P", base), ("", up), ("кав", low), ("", end), ("=3,38", s)]),
        ("2 база,низ,конец,стр", [("P", base), ("кав", low), ("", end), ("=3,38", s)]),
        ("3 стр,база'',верх'',низ,конец", [("P", s), ("", base), ("", up), ("кав", low), ("", end),
                                         ("=3,38", s)]),
        ("4 база,низ,конец(=3,38)", [("P", base), ("кав", low), ("=3,38", end)]),
        ("5 база,верх'2',низ'кав',конец", [("P", base), ("2", up), ("кав", low), ("", end),
                                          ("=3,38", s)]),
        ("6 база,верх'2',конец (D²)", [("D", base), ("2", up), ("", end), (" мм", s)]),
    ]
    y = 260.0
    for name, items in variants:
        try:
            got = rich_text(ctx, 30.0, y, items)
            result(name, True, f"прочитано {got!r}")
        except Exception as exc:
            result(name, False, repr(exc))
        ctx.api5.ActiveDocument2D().ksText(90.0, y, 0.0, 3.5, 1.0, 0, name)
        y -= 15.0

    out = st.OUTPUT_DIR / "kompas_ai_api_test8.cdw"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        ctx.doc.SaveAs(str(out))
        log(f"Сохранено: {out}")
    except Exception as exc:
        log(f"Сохранить не удалось: {exc!r}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test8_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
