"""Sixteenth API test: a drawing linked to its model, and KOMPAS tables.

1. A stepped shaft is made (API5, revolve) and saved; the names of its
   projections are listed (the exact names an associative view needs).
2. A new drawing gets an associative view of the shaft — API7
   (IViews.Add + IAssociationView) and API5 (ksAssociationViewParam +
   ksCreateSheetArbitraryView), each variant reported. Then: open the shaft,
   change it, go back to the drawing, F5 — does the view follow?
3. A table 3 × 2 with texts — API7 (DrawingTables in the view's containers,
   several Add signatures) and API5 (ksTable … ksColumnNumber … ksEndObj).
   The members of every interface met are written to the report, so the
   next fix needs no guessing.

Run:  py api_test16.py   — then send api_test16_report.txt and a screenshot
of the drawing.
"""

from __future__ import annotations

import sys
import traceback

import smoke_test as st
from api_test7 import members, result
from smoke_test import Context, cast, log

API7_TYPELIB = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"


def const(name, default=None):
    from win32com.client import constants

    try:
        return getattr(constants, name)
    except AttributeError:
        if default is None:
            raise
        return default


def interfaces(words) -> list[str]:
    from win32com.client import gencache

    mod = gencache.GetModuleForTypelib(API7_TYPELIB, 0, 1, 0)
    return sorted(n for n in mod.NamesToIIDMap if any(w in n for w in words))


def tail(exc) -> str:
    return traceback.format_exc().strip().splitlines()[-1] if exc else ""


# --- 1. the model ---------------------------------------------------------------------

def make_shaft(ctx) -> str:
    from win32com.client import constants

    m = ctx.api5_module
    doc3d = ctx.api5.Document3D()
    result("новая деталь", doc3d.Create(False, True))
    part = doc3d.GetPart(constants.pTop_Part)
    sk = part.NewEntity(constants.o3d_sketch)
    sd = m.ksSketchDefinition(sk.GetDefinition())
    sd.SetPlane(part.GetDefaultEntity(constants.o3d_planeXOY))
    sk.Create()
    d2 = sd.BeginEdit()
    pts = [(0, 0), (0, 10), (30, 10), (30, 15), (60, 15), (60, 0)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        d2.ksLineSeg(a[0], a[1], b[0], b[1], 1)
    d2.ksLineSeg(-5, 0, 65, 0, 3)  # the axis
    sd.EndEdit()
    rot = part.NewEntity(constants.o3d_baseRotated)
    rd = m.ksBaseRotatedDefinition(rot.GetDefinition())
    rd.SetSideParam(True, 360.0)
    rd.SetSketch(sk)
    result("вал вращением", rot.Create())
    try:
        coll = doc3d.GetViewProjectionCollection()
        names = []
        for i in range(coll.GetCount()):
            names.append(repr(coll.GetByIndex(i).name))
        log(f"      проекции модели: {', '.join(names)}")
    except Exception as exc:
        log(f"      список проекций: {exc!r}")
    path = str(st.OUTPUT_DIR / "kompas_ai_api_test16_shaft.m3d")
    st.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result(f"сохранение {path}", doc3d.SaveAs(path))
    return path


# --- 2. the linked view ----------------------------------------------------------------

def linked_view(ctx, source: str) -> None:
    log(f"      интерфейсы: {', '.join(interfaces(('Assoc', 'View')))}"[:1500])
    views = ctx.doc2d.ViewsAndLayersManager.Views
    log(f"      IViews: {members(views)}")
    y = 200.0
    for type_name in ("vt_Arbitrary", "vt_Normal"):
        for projection in ("#Спереди", "Спереди", "#Front"):
            name = f"API7 {type_name}, проекция {projection!r}"
            try:
                view = views.Add(const(type_name))
                assoc = cast(view, "IAssociationView")
                if y == 200.0:
                    log(f"      IView: {members(view)}")
                    log(f"      IAssociationView: {members(assoc)}")
                assoc.SourceFileName = source
                assoc.ProjectionName = projection
                view.X, view.Y = 60.0, y
                view.Scale = 1.0
                ok = view.Update()
                result(name, ok, f"вид №{view.Number}" if ok else "")
                y -= 45.0
                if ok:
                    return
            except Exception as exc:
                result(name, False, repr(exc))
                log("      " + tail(exc))
    # API5
    try:
        kompas = ctx.api5
        par = kompas.GetParamStruct(const("ko_AssociationViewParam"))
        par = ctx.api5_module.ksAssociationViewParam(par)
        log(f"      ksAssociationViewParam: {members(par)}")
        par.Init()
        par.fileName = source
        par.projectionName = "#Спереди"
        par.scale_, par.x, par.y = 1.0, 150.0, 200.0
        doc5 = kompas.ActiveDocument2D()
        ref = doc5.ksCreateSheetArbitraryView(par, 0)
        result("API5 ksCreateSheetArbitraryView", ref, repr(ref))
    except Exception as exc:
        result("API5 ассоциативный вид", False, repr(exc))
        log("      " + tail(exc))


# --- 3. tables -------------------------------------------------------------------------

def tables(ctx) -> None:
    log(f"      интерфейсы: {', '.join(interfaces(('Table',)))}")
    view = ctx.doc2d.ViewsAndLayersManager.Views.ActiveView
    made = False
    for iface in ("IDrawingContainer", "ISymbols2DContainer", "IDrawingTables"):
        try:
            container = cast(view, iface)
            log(f"      {iface}: {members(container)}")
            coll = container.DrawingTables
            log(f"      {iface}.DrawingTables: {members(coll)}")
        except Exception as exc:
            log(f"      {iface}: {exc!r}")
            continue
        for args in ((3, 2, 8.0, 30.0, 0), (3, 2, 8.0, 30.0), ()):
            try:
                table = coll.Add(*args)
                log(f"      Add{args}: {members(table)}")
                table.X, table.Y = 20.0, 280.0
                grid = cast(table, "ITable")
                log(f"      ITable: {members(grid)}")
                cell = grid.Cell(0, 0)
                log(f"      ITableCell: {members(cell)}")
                text = cast(cell.Text, "IText")
                log(f"      IText: {members(text)}")
                text.Str = "A"
                ok = table.Update()
                result(f"API7 {iface}.DrawingTables.Add{args}", ok)
                made = made or ok
                break
            except Exception as exc:
                result(f"API7 {iface}.DrawingTables.Add{args}", False, repr(exc))
                log("      " + tail(exc))
        if made:
            break
    # API5
    try:
        doc5 = ctx.api5.ActiveDocument2D()
        r = doc5.ksTable()
        log(f"      ksTable() → {r!r}")
        xs, ys = (100.0, 130.0, 160.0), (280.0, 272.0, 264.0, 256.0)
        for y in ys:
            doc5.ksLineSeg(xs[0], y, xs[-1], y, 1)
        for x in xs:
            doc5.ksLineSeg(x, ys[0], x, ys[-1], 1)
        n = 0
        for r_ in range(3):
            for c in range(2):
                n += 1
                cn = doc5.ksColumnNumber(n)
                doc5.ksText(xs[c] + 1.0, ys[r_ + 1] + 2.0, 0.0, 3.5, 1.0, 0, f"{r_}{c}")
                if n == 1:
                    log(f"      ksColumnNumber(1) → {cn!r}")
        ref = doc5.ksEndObj()
        result("API5 ksTable … ksEndObj", ref, repr(ref))
        try:
            log(f"      тип объекта: {doc5.ksGetObjParam(ref, 0, -1)!r}")
        except Exception:
            pass
    except Exception as exc:
        result("API5 таблица", False, repr(exc))
        log("      " + tail(exc))


def main() -> int:
    log("Тест API №16: чертёж, связанный с моделью; таблицы КОМПАС")
    if sys.platform != "win32":
        log("Скрипт нужно запускать в Windows с установленным КОМПАС-3D.")
        return 2
    ctx = Context()
    for name, func in [("Подключение", st.step_connect),
                       ("Библиотеки API5", st.step_load_api5_constants)]:
        print(f"...    {name}", flush=True)
        func(ctx)
    log("")
    log("1. Модель")
    source = None
    try:
        source = make_shaft(ctx)
    except Exception as exc:
        result("модель", False, repr(exc))
        log("      " + tail(exc))
    for name, func in [("Новый чертёж", st.step_new_drawing),
                       ("Активный вид", st.step_active_view)]:
        func(ctx)
    log("")
    log("2. Ассоциативный вид модели")
    if source:
        try:
            linked_view(ctx, source)
        except Exception as exc:
            result("2", False, repr(exc))
            log("      " + tail(exc))
    log("")
    log("3. Таблица")
    try:
        tables(ctx)
    except Exception as exc:
        result("3", False, repr(exc))
        log("      " + tail(exc))
    try:
        out = st.OUTPUT_DIR / "kompas_ai_api_test16.cdw"
        ctx.doc.SaveAs(str(out))
        log(f"\nСохранено: {out}")
    except Exception as exc:
        log(f"\nСохранить чертёж не удалось: {exc!r}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test16_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
