"""Third API test: the parts api_test2.py could not confirm.

Findings so far (KOMPAS v22, licence expired, API5):
  * linear dims: ps 0/1/2 = parallel/vertical/horizontal, bitFlag=1 shows the value;
  * radius/diameter dims and hatches (ksHatch ... ksEndObj) are created;
  * ksCreateSheetView returned 0 — the circle went into the system view;
  * sheet format via API7 LayoutSheets did not change (Update() = False);
  * the angular dimension needs another parameter class.

This run tries:
  1. the angular dimension with ksDimDrawingParam;
  2. a scaled view with several ``state`` values (error code logged);
  3. a new A3 landscape document created through API5 ksCreateDocument.

Run:  py api_test3.py   — then send api_test3_report.txt and screenshots of
both documents (the test drawing and the new A3 sheet).
"""

from __future__ import annotations

import sys

import dim_test as dt
import smoke_test as st
from smoke_test import Context, log

OUTPUT_FILE = st.OUTPUT_DIR / "kompas_ai_api_test3.cdw"
OUTPUT_A3 = st.OUTPUT_DIR / "kompas_ai_api_test3_A3.cdw"


def param(ctx: Context, struct_const: str, interface: str):
    return getattr(ctx.api5_module, interface)(ctx.api5.GetParamStruct(st.constant(struct_const)))


def sub(ctx: Context, interface: str, raw):
    return getattr(ctx.api5_module, interface)(raw)


def last_error(ctx: Context):
    try:
        return ctx.api5.ksReturnResult()
    except Exception:
        return "?"


def result(ctx: Context, name: str, ref) -> None:
    ok = ref[0] if isinstance(ref, tuple) else ref
    log(f"[{'OK' if ok else 'FAIL'}]   {name}: ссылка {ref}, код ошибки {last_error(ctx)}")


def log_constants(*keys: str) -> dict:
    from win32com.client import constants

    found = {}
    for table in constants.__dicts__:
        for name, value in table.items():
            if any(k.upper() in name.upper() for k in keys):
                found[name] = value
    for name in sorted(found):
        log(f"      константа {name} = {found[name]}")
    return found


# --- 1. angular ------------------------------------------------------------------

def part_angular(ctx: Context) -> None:
    doc = ctx.api5.ActiveDocument2D()
    xc, yc = 40.0, 230.0
    doc.ksLineSeg(xc, yc, xc + 50.0, yc, st.STYLE_MAIN)
    doc.ksLineSeg(xc, yc, xc + 35.355, yc + 35.355, st.STYLE_MAIN)
    doc.ksText(xc, yc - 8.0, 0.0, 3.5, 1.0, 0, "угол 45°")
    par = param(ctx, "ko_ADimParam", "ksADimParam")
    src = sub(ctx, "ksADimSourceParam", par.GetSPar())
    src.Init()
    drw = sub(ctx, "ksDimDrawingParam", par.GetDPar())
    drw.Init()
    txt = sub(ctx, "ksDimTextParam", par.GetTPar())
    txt.Init(False)
    dt._dump(src, "adim source после Init")
    dt._apply(src, {"xc": xc, "yc": yc, "ang1": 0.0, "ang2": 45.0, "rad": 30.0, "dir": True},
              "adim source")
    dt._dump(src, "adim source после записи")
    txt.bitFlag = 1
    result(ctx, "угловой размер ksAngDimension", doc.ksAngDimension(par))


# --- 2. scaled view --------------------------------------------------------------

def part_views(ctx: Context) -> None:
    states = log_constants("stACTIVE", "stCURRENT", "stREADONLY", "stINVISIBLE")
    candidates = [("state=0", 0)] + [(f"state={n}", v) for n, v in sorted(states.items())]
    x = 120.0
    number = 2
    for name, state in candidates[:4]:
        doc = ctx.api5.ActiveDocument2D()
        par = param(ctx, "ko_ViewParam", "ksViewParam")
        par.Init()
        dt._apply(par, {"x": x, "y": 230.0, "scale_": 5.0, "state": state,
                        "name": f"Вид {number}"}, "view")
        ref = doc.ksCreateSheetView(par, number)
        result(ctx, f"вид {number} ({name})", ref)
        ok = ref[0] if isinstance(ref, tuple) else ref
        if ok:
            # Inside a 5:1 view: R4 must look R20 on the sheet.
            result(ctx, f"окружность R4 в виде {number}", doc.ksCircle(0.0, 0.0, 4.0, st.STYLE_MAIN))
            doc.ksText(-4.0, 5.0, 0.0, 0.7, 1.0, 0, name)
        x += 45.0
        number += 1
    # Back to the system view (number 0) for anything drawn afterwards.
    try:
        result(ctx, "вернуться в системный вид ksOpenView(0)", ctx.api5.ActiveDocument2D().ksOpenView(0))
    except Exception as exc:
        log(f"      ksOpenView недоступен: {exc!r}")


# --- 3. A3 document via API5 ---------------------------------------------------------

def part_a3_document(ctx: Context) -> None:
    log_constants("lt_DocSheetStandart", "ksFormatA3")
    doc5 = ctx.api5.Document2D()
    par = param(ctx, "ko_DocumentParam", "ksDocumentParam")
    par.Init()
    dt._dump(par, "document после Init")
    par.type = st.constant("lt_DocSheetStandart", 1)
    par.regime = 0  # visible
    sheet = sub(ctx, "ksSheetPar", par.GetLayoutParam())
    sheet.Init()
    dt._dump(sheet, "sheet после Init")
    std = sub(ctx, "ksStandartSheet", sheet.GetSheetParam())
    std.Init()
    dt._dump(std, "standart sheet после Init")
    dt._apply(std, {"format": 3, "multiply": 1, "direct": True}, "standart sheet")
    dt._dump(std, "standart sheet после записи")
    created = doc5.ksCreateDocument(par)
    result(ctx, "новый документ A3 ksCreateDocument", created)
    if created:
        doc5.ksLineSeg(30.0, 30.0, 380.0, 280.0, st.STYLE_MAIN)
        doc5.ksText(40.0, 270.0, 0.0, 5.0, 1.0, 0, "Должен быть лист A3 альбомный")
        try:
            result(ctx, "сохранение A3 ksSaveDocument", doc5.ksSaveDocument(str(OUTPUT_A3)))
        except Exception as exc:
            log(f"[FAIL] сохранение A3: {exc!r}")


PARTS = [
    ("1. Угловой размер", part_angular),
    ("2. Вид с масштабом 5:1", part_views),
    ("3. Документ A3 через API5", part_a3_document),
]


def main() -> int:
    log("Тест API №3: угловой размер, вид с масштабом, формат A3")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2
    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants),
                       ("Новый чертёж", st.step_new_drawing)]:
        print(f"...    {name}", flush=True)
        func(ctx)

    for name, func in PARTS:
        print(f"...    {name}", flush=True)
        log(f"--- {name}")
        if name.startswith("3."):  # the A3 part opens another document: save this one first
            _save(ctx)
        try:
            func(ctx)
        except Exception as exc:
            log(f"[FAIL] {name}: {exc!r}")

    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test3_report.txt")
    st.save_report()
    return 0


def _save(ctx: Context) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        ctx.doc.SaveAs(str(OUTPUT_FILE))
        log(f"Сохранено: {OUTPUT_FILE}")
    except Exception as exc:
        log(f"[FAIL] Сохранение: {exc!r}")


if __name__ == "__main__":
    sys.exit(main())
