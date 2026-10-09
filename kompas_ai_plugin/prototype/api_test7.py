"""Seventh API test: what a working licence (KOMPAS v23 учебная) unlocks.

Without a licence (v22) these were refused or did nothing:
  * API7 collection.Add() / Update()            → check 1
  * scaled view ksCreateSheetView (error 216)   → check 2
  * sheet format via API7 LayoutSheets           → check 3
  * text index (API5 ignores the item type)     → check 4, through API7
  * title block (основная надпись)               → check 5

Each check runs on its own; the report says [OK] / [FAIL] with details, and
the drawing is saved so the screenshot shows what really appeared.

Run:  py api_test7.py   — then send api_test7_report.txt and a screenshot
(zoom in on the texts with indices, top left, and on the title block).
"""

from __future__ import annotations

import sys
import traceback

import smoke_test as st
from smoke_test import Context, cast, constant, log


def result(name: str, ok, details: str = "") -> None:
    log(f"[{'OK' if ok else 'FAIL'}]   {name}" + (f" — {details}" if details else ""))


def members(obj) -> str:
    """Public names of a COM wrapper (to fix a wrong name from the report)."""
    try:
        return ", ".join(n for n in dir(obj) if not n.startswith("_"))[:600]
    except Exception:
        return "?"


# --- 1. API7 editing ----------------------------------------------------------------

def check_api7_edit(ctx: Context) -> None:
    seg = ctx.drawing.LineSegments.Add()
    if seg is None:
        result("API7 LineSegments.Add()", False, "вернул None — редактирование через API7 закрыто")
        return
    seg.X1, seg.Y1, seg.X2, seg.Y2 = 20.0, 200.0, 80.0, 200.0
    seg.Style = st.STYLE_MAIN
    result("API7 отрезок Add() + Update()", seg.Update())
    st.step_text(ctx)  # "Тест плагина КОМПАС-AI" at (20, 100)
    result("API7 текст DrawingTexts", True)


# --- 2. scaled view (API5) ----------------------------------------------------------

def check_view(ctx: Context) -> None:
    doc = ctx.api5.ActiveDocument2D()
    par = ctx.api5_module.ksViewParam(ctx.api5.GetParamStruct(constant("ko_ViewParam")))
    par.Init()
    par.x, par.y, par.scale_, par.name = 250.0, 150.0, 5.0, "Вид 5:1"
    ref = doc.ksCreateSheetView(par, 2)
    ok = bool(ref[0] if isinstance(ref, tuple) else ref)
    result("вид 5:1 ksCreateSheetView", ok, f"ссылка {ref}, код {ctx.api5.ksReturnResult()}")
    if not ok:
        return
    # In the view, coordinates are model mm: R5 must look R25 on the sheet,
    # and the automatic dimension must read Ø10, not Ø50.
    result("окружность R5 в виде", doc.ksCircle(0.0, 0.0, 5.0, st.STYLE_MAIN))
    doc.ksLineSeg(-8.0, 0.0, 8.0, 0.0, st.STYLE_AXIAL)
    doc.ksLineSeg(0.0, -8.0, 0.0, 8.0, st.STYLE_AXIAL)
    m = ctx.api5_module
    dpar = m.ksRDimParam(ctx.api5.GetParamStruct(constant("ko_RDimParam")))
    src = m.ksRDimSourceParam(dpar.GetSPar())
    src.Init()
    src.xc, src.yc, src.rad = 0.0, 0.0, 5.0
    drw = m.ksRDimDrawingParam(dpar.GetDPar())
    drw.Init()
    drw.ang = 45.0
    txt = m.ksDimTextParam(dpar.GetTPar())
    txt.Init(False)
    txt.bitFlag = 1  # automatic value
    txt.sign = 1  # Ø
    result("авто-размер Ø в виде (на экране должно быть Ø10)", doc.ksDiamDimension(dpar))
    try:
        views = ctx.doc2d.ViewsAndLayersManager.Views
        log(f"      видов в документе: {views.Count}, активный вид масштаб {views.ActiveView.Scale}")
    except Exception as exc:
        log(f"      API7 Views: {exc!r}")


# --- 3. sheet format (API7) ---------------------------------------------------------

def check_format(ctx: Context) -> None:
    sheet = ctx.doc.LayoutSheets.Item(0)
    fmt = sheet.Format
    log(f"      формат до: {fmt.Format}, вертикальный: {fmt.VerticalOrientation}")
    fmt.Format = constant("ksFormatA3", 3)
    fmt.VerticalOrientation = False
    ok = sheet.Update()
    log(f"      формат после: {fmt.Format}, вертикальный: {fmt.VerticalOrientation}")
    result("формат A3 альбомный (API7 LayoutSheets)", ok)


# --- 4. text with an index (API7) ---------------------------------------------------

INDEX_TYPES = [  # (label, constant name, value in the type library per api_test5)
    ("начало индекса", "ksTItSBase", 7),
    ("верхний индекс", "ksTItSUpperIndex", 8),
    ("нижний индекс", "ksTItSLowerIndex", 9),
    ("конец", "ksTItSEnd", 16),
]


def _item_type(name: str, fallback: int) -> int:
    try:
        return constant(name)
    except AttributeError:
        return fallback


def _rich_text(ctx: Context, x: float, y: float, items) -> bool:
    """items = [(string, item type or None)] → one text object."""
    obj = ctx.drawing.DrawingTexts.Add()
    obj.X, obj.Y = x, y
    text = cast(obj, "IText")
    line = text.Add()
    for value, kind in items:
        item = line.Add()
        if kind is not None:
            item.ItemType = kind
        item.Str = value
        item.Update()
    ok = obj.Update()
    log(f"      прочитано обратно: {text.Str!r}")
    return ok


def check_index(ctx: Context) -> None:
    base = _item_type("ksTItSBase", 7)
    low = _item_type("ksTItSLowerIndex", 9)
    up = _item_type("ksTItSUpperIndex", 8)
    end = _item_type("ksTItSEnd", 16)
    log(f"      типы: SBase={base}, нижний={low}, верхний={up}, конец={end}")
    variants = [
        ("A: P + нижний «кав» + =3,38",
         [("P", None), ("кав", low), ("", end), ("=3,38", None)]),
        ("B: P(база) + нижний «кав» + конец",
         [("P", base), ("кав", low), ("", end), ("=3,38", None)]),
        ("C: D + верхний «2»", [("D", None), ("2", up), ("", end)]),
    ]
    y = 280.0
    for name, items in variants:
        try:
            result(name, _rich_text(ctx, 25.0, y, items))
        except Exception as exc:
            result(name, False, repr(exc))
            try:
                line = cast(ctx.drawing.DrawingTexts.Add(), "IText").Add()
                log(f"      ITextLine: {members(line)}")
                log(f"      ITextItem: {members(line.Add())}")
            except Exception:
                pass
        doc5 = ctx.api5.ActiveDocument2D()
        doc5.ksText(80.0, y, 0.0, 3.5, 1.0, 0, name)
        y -= 12.0


# --- 5. title block -----------------------------------------------------------------

STAMP_CELLS = [(1, "Вал (тест КОМПАС-AI)"), (2, "КАИ.000.001"), (3, "Сталь 45 ГОСТ 1050-2013"),
               (6, "1:1")]


def check_stamp(ctx: Context) -> None:
    sheet = ctx.doc.LayoutSheets.Item(0)
    stamp = sheet.Stamp
    for cell, value in STAMP_CELLS:
        try:
            stamp.Text(cell).Str = value
        except Exception as exc:
            result(f"графа {cell}", False, repr(exc))
    ok = stamp.Update()
    result("основная надпись Stamp.Update()", ok)
    for cell, _ in STAMP_CELLS:
        try:
            log(f"      графа {cell}: {stamp.Text(cell).Str!r}")
        except Exception as exc:
            log(f"      графа {cell}: {exc!r}")


CHECKS = [
    ("1. Редактирование через API7", check_api7_edit),
    ("2. Вид с масштабом 5:1", check_view),
    ("3. Формат листа A3 (API7)", check_format),
    ("4. Текст с индексом (API7)", check_index),
    ("5. Основная надпись", check_stamp),
]


def main() -> int:
    log("Тест API №7: что даёт рабочая лицензия")
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
    for name, func in CHECKS:
        log("")
        log(name)
        try:
            func(ctx)
        except Exception as exc:
            result(name, False, repr(exc))
            log("      " + traceback.format_exc().strip().splitlines()[-1])

    out = st.OUTPUT_DIR / "kompas_ai_api_test7.cdw"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        ctx.doc.SaveAs(str(out))
        log(f"\nСохранено: {out}")
    except Exception as exc:
        log(f"\nСохранить не удалось: {exc!r}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test7_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
