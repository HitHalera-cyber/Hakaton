"""Fourteenth API test: driving dimensions (размеры, которые меняют геометрию).

A segment and a linear dimension on it are made through API7. The test then
tries to tie the dimension to the segment ends (the point indices of a
dimension: ksDimensionBasePoint…) and to make it driving
(«фиксированный размер», «размер с переменной»), sets a new value and reads
the segment back: if its length followed, the way is found. It also lists
the API7 interfaces whose names speak of dimensions, association and
variables, so the next step needs no guessing.

Run:  py api_test14.py   — then send api_test14_report.txt and a screenshot.
"""

from __future__ import annotations

import sys
import traceback

import smoke_test as st
from api_test7 import members, result
from smoke_test import Context, cast, log


def const(name):
    from win32com.client import constants

    return getattr(constants, name)


def interfaces(words) -> list[str]:
    from win32com.client import gencache

    mod = gencache.GetModuleForTypelib("{69AC2981-37C0-4379-84FD-5DD2F3C0A520}", 0, 1, 0)
    return sorted(n for n in mod.NamesToIIDMap if any(w in n for w in words))


def seg_text(seg) -> str:
    return f"({seg.X1:.2f}, {seg.Y1:.2f}) – ({seg.X2:.2f}, {seg.Y2:.2f}), длина {seg.X2 - seg.X1:.2f}"


def make(ctx, y):
    seg = ctx.drawing.LineSegments.Add()
    seg.X1, seg.Y1, seg.X2, seg.Y2, seg.Style = 20.0, y, 50.0, y, st.STYLE_MAIN
    seg.Update()
    dim = ctx.symbols.LineDimensions.Add()
    dim.X1, dim.Y1, dim.X2, dim.Y2 = 20.0, y, 50.0, y
    dim.X3, dim.Y3 = 35.0, y + 10.0
    dim.Orientation = const("ksLinDHorizontal")
    dim.Update()
    return seg, dim


def constraint(obj, kind, **fields):
    c = cast(obj, "IDrawingObject1").NewConstraint()
    c.ConstraintType = const(kind)
    for k, v in fields.items():
        setattr(c, k, v)
    return c, c.Create()


def main() -> int:
    log("Тест API №14: управляющие размеры")
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

    log("")
    log("1. Интерфейсы API7")
    try:
        log("      " + ", ".join(interfaces(("Dimension", "Assoc", "Variable", "Parametr"))))
        result("перечислены", True)
    except Exception as exc:
        result("перечислены", False, repr(exc))

    log("")
    log("2. Размер на отрезке: интерфейсы размера")
    seg, dim = make(ctx, 200.0)
    for name in interfaces(("Dimension",)):
        try:
            log(f"      {name}: {members(cast(dim, name))[:600]}")
        except Exception:
            pass

    log("")
    log("3. Привязка точек размера к концам отрезка")
    for idx_name in ("ksDimensionBasePoint", "ksDimensionExtensionLinePoint", "ksDimensionLinePoint",
                     "ksDimensionTextPoint", "ksDimensionShelfPoint"):
        try:
            idx = const(idx_name)
        except AttributeError:
            continue
        s2, d2 = make(ctx, 120.0 + 15 * idx)
        try:
            _, ok1 = constraint(d2, "ksCMergePoints", Index=idx, Partner=s2, PartnerIndex=0)
            _, ok2 = constraint(d2, "ksCMergePoints", Index=idx + 100, Partner=s2, PartnerIndex=1)
            result(f"{idx_name}={idx}: начало {ok1}, конец (индекс+100) {ok2}", ok1)
        except Exception as exc:
            result(idx_name, False, repr(exc))

    log("")
    log("4. Размер управляющий: значение 40 вместо 30")
    for kind, fields in (("ksCFixedDim", {}),
                         ("ksCDimWithVariable", {"Variable": "L1", "Value": 40.0})):
        s3, d3 = make(ctx, 60.0 if kind == "ksCFixedDim" else 30.0)
        try:
            constraint(d3, "ksCMergePoints", Index=const("ksDimensionBasePoint"), Partner=s3,
                       PartnerIndex=0)
            c, ok = constraint(d3, kind, **fields)
            result(f"{kind}: Create", ok)
            log(f"      отрезок после связи: {seg_text(s3)}")
            try:
                t = cast(d3, "IDimensionText")
                t.NominalValue = 40.0
                d3.Update()
            except Exception as exc:
                log(f"      NominalValue: {exc!r}")
            try:
                c.Value = 40.0
                c.Update() if hasattr(c, "Update") else None
            except Exception as exc:
                log(f"      Value: {exc!r}")
            log(f"      отрезок после значения 40: {seg_text(s3)}")
        except Exception as exc:
            result(kind, False, repr(exc))
            log("      " + traceback.format_exc().strip().splitlines()[-1])

    out = st.OUTPUT_DIR / "kompas_ai_api_test14.cdw"
    try:
        ctx.doc.SaveAs(str(out))
        log(f"\nСохранено: {out}")
    except Exception as exc:
        log(f"\nСохранить не удалось: {exc!r}")
    st.REPORT_PATH = st.REPORT_PATH.with_name("api_test14_report.txt")
    st.save_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
