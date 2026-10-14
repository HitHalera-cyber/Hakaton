"""«Проверить КОМПАС»: which ways of this KOMPAS make a drawing linked to its
model and a KOMPAS table (prototype/api_test16.py, from inside the program).

A small shaft is built and saved, a drawing gets an associative view of it
and a 3 × 2 table — every variant tried is written to the log with the
members of the interfaces met, so the next fix needs no guessing.
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

API7_TYPELIB = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"


def run(log) -> Path:
    from win32com.client import CastTo, gencache

    from .api5 import Api5Backend

    folder = Path(os.environ.get("TEMP") or Path.home()) / "kompas_ai_check"
    folder.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        log(text)

    def result(name, ok, details=""):
        say(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" — {details}" if details else ""))

    def members(obj) -> str:
        try:
            return ", ".join(n for n in dir(obj) if not n.startswith("_"))[:700]
        except Exception:
            return "?"

    def last(exc) -> str:
        return f"{exc!r} | {traceback.format_exc().strip().splitlines()[-1]}"

    say("Проверка КОМПАС: связь чертежа с моделью, таблицы")
    b = Api5Backend(log=say)
    c = b.constants
    try:
        mod = gencache.GetModuleForTypelib(API7_TYPELIB, 0, 1, 0)
        names = sorted(n for n in mod.NamesToIIDMap
                       if any(w in n for w in ("Table", "Assoc", "View")))
        say("Интерфейсы API7: " + ", ".join(names))
    except Exception as exc:
        say(f"Интерфейсы API7: {exc!r}")

    say("1. Модель")
    shaft = folder / "shaft.m3d"
    pts = [(0, 0), (0, 10), (30, 10), (30, 15), (60, 15), (60, 0)]
    loops = [[("line", a, b2) for a, b2 in zip(pts, pts[1:] + pts[:1])]]
    result("вал", b.revolve_part(loops, str(shaft), parametric=False), str(shaft))
    try:
        coll = b._doc3d.GetViewProjectionCollection()
        say("Проекции модели: " + ", ".join(repr(coll.GetByIndex(i).name)
                                            for i in range(coll.GetCount())))
    except Exception as exc:
        say(f"Проекции модели: {last(exc)}")

    say("2. Ассоциативный вид")
    b.new_sheet(3, True)
    app = gencache.EnsureDispatch("Kompas.Application.7")
    doc2d = CastTo(app.ActiveDocument, "IKompasDocument2D")
    views = doc2d.ViewsAndLayersManager.Views
    say(f"IViews: {members(views)}")
    done, y = False, 230.0
    for type_name in ("vt_Arbitrary", "vt_Normal"):
        for projection in ("#Спереди", "Спереди"):
            name = f"API7 {type_name}, {projection!r}"
            try:
                view = views.Add(getattr(c, type_name))
                assoc = CastTo(view, "IAssociationView")
                if y == 230.0:
                    say(f"IView: {members(view)}")
                    say(f"IAssociationView: {members(assoc)}")
                assoc.SourceFileName = str(shaft)
                assoc.ProjectionName = projection
                view.X, view.Y, view.Scale = 40.0, y, 1.0
                ok = view.Update()
                result(name, ok)
                y -= 50.0
                if ok:
                    done = True
                    break
            except Exception as exc:
                result(name, False, last(exc))
        if done:
            break
    try:
        result("API5 ассоциативный вид (через программу)",
               b.model_view(str(shaft), (200.0, 230.0), 1.0, projection="#Спереди"))
    except Exception as exc:
        result("API5 ассоциативный вид", False, last(exc))
    try:  # a view of a model is an empty frame until the sheet is rebuilt
        result("Перестроение листа (виды модели заполняются)", b.rebuild())
    except Exception as exc:
        result("Перестроение листа", False, last(exc))

    say("3. Таблица")
    view = views.ActiveView
    made = False
    for iface in ("IDrawingContainer", "ISymbols2DContainer"):
        try:
            container = CastTo(view, iface)
            say(f"{iface}: {members(container)}")
            coll = container.DrawingTables
            say(f"{iface}.DrawingTables: {members(coll)}")
        except Exception as exc:
            say(f"{iface}: {last(exc)}")
            continue
        for args in ((3, 2, 8.0, 30.0, 0), (3, 2, 8.0, 30.0), ()):
            try:
                table = coll.Add(*args)
                say(f"Add{args}: {members(table)}")
                table.X, table.Y = 20.0, 100.0
                grid = CastTo(table, "ITable")
                say(f"ITable: {members(grid)}")
                cell = grid.Cell(0, 0)
                say(f"ITableCell: {members(cell)}")
                text = CastTo(cell.Text, "IText")
                say(f"IText: {members(text)}")
                text.Str = "A"
                ok = table.Update()
                result(f"API7 {iface}.DrawingTables.Add{args}", ok)
                made = bool(ok)
                break
            except Exception as exc:
                result(f"API7 {iface}.DrawingTables.Add{args}", False, last(exc))
        if made:
            break
    try:
        doc = b.doc
        r = doc.ksTable()
        say(f"ksTable() → {r!r}, код {b.last_error()}")
        xs, ys = (100.0, 130.0, 160.0), (100.0, 92.0, 84.0, 76.0)
        for yy in ys:
            doc.ksLineSeg(xs[0], yy, xs[-1], yy, 1)
        for x in xs:
            doc.ksLineSeg(x, ys[0], x, ys[-1], 1)
        n = 0
        for row in range(3):
            for col in range(2):
                n += 1
                cn = doc.ksColumnNumber(n)
                doc.ksText(xs[col] + 1.0, ys[row + 1] + 2.0, 0.0, 3.5, 1.0, 0, f"{row}{col}")
                if n == 1:
                    say(f"ksColumnNumber(1) → {cn!r}, код {b.last_error()}")
        ref = doc.ksEndObj()
        result("API5 ksTable … ksEndObj", ref, f"{ref!r}, код {b.last_error()}")
    except Exception as exc:
        result("API5 таблица", False, last(exc))
    out = folder / "check.cdw"
    result("сохранение", b.save(str(out)), str(out))
    report = Path(os.environ.get("APPDATA") or Path.home()) / "KompasAI" / "kompas_check.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    say(f"Отчёт: {report}")
    return report
