"""KOMPAS-3D backend through API5 (COM, Windows only).

Only calls confirmed by the prototype tests on KOMPAS v22 are used (see
kompas_ai_plugin/README.md): ksCreateDocument with a standard sheet,
ksLineSeg/ksCircle/ksArcByAngle/ksPoint/ksText, ksLinDimension,
ksRadDimension/ksDiamDimension, ksAngDimension, ksHatch…ksEndObj,
ksSaveDocument. ``open_view`` (ksCreateSheetView) is refused without a
licence; the writer then falls back to drawing in sheet millimetres.
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from .backend import LINEAR_HORIZONTAL, DimText, Point

FORMAT_DOC_SHEET = 1  # ksDocumentParam.type: drawing with a standard sheet

# API7 ITextItem.ItemType values (KOMPAS v23 with a licence, prototype/api_test8.py).
# An index is written as: base "" → upper → lower → end, right after the text it
# belongs to (variant 3 of api_test8 draws «P» with «кав» below it and «=3,38»
# after the index). API5 ignores the item type, so indices need API7.
ITEM_STRING, ITEM_BASE, ITEM_UPPER, ITEM_LOWER, ITEM_END = 0, 7, 8, 9, 16


def index_items(parts: list[tuple[str, str]]) -> list[tuple[str, int]]:
    """[(text, "normal"|"sub"|"sup")] → [(string, ItemType)] for one text line."""
    items = []
    for text, kind in parts:
        if kind == "sub":
            items += [("", ITEM_BASE), ("", ITEM_UPPER), (text, ITEM_LOWER), ("", ITEM_END)]
        elif kind == "sup":
            items += [("", ITEM_BASE), (text, ITEM_UPPER), ("", ITEM_LOWER), ("", ITEM_END)]
        else:
            items.append((text, ITEM_STRING))
    return items


def kompas_text(value: str) -> str:
    """KOMPAS API5 strings go through cp1251, which has no «×» (it came out
    as «Ч»: 1ч45°); the Latin x is used as on typed drawings."""
    return value.replace("×", "x")


def _find_kompas_typelibs() -> list[tuple[str, int, int, str]]:
    import winreg

    found = []
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "TypeLib") as root:
        for i in range(winreg.QueryInfoKey(root)[0]):
            guid = winreg.EnumKey(root, i)
            try:
                with winreg.OpenKey(root, guid) as key:
                    for j in range(winreg.QueryInfoKey(key)[0]):
                        version = winreg.EnumKey(key, j)
                        name = winreg.QueryValue(key, version)
                        if "kompas" in name.lower():
                            major, _, minor = version.partition(".")
                            found.append((guid, int(major, 16), int(minor or "0", 16), name))
            except (OSError, ValueError):
                continue
    return found


def _prepare_win32com() -> None:
    """In the packaged exe the pywin32 cache folder is read-only; the wrappers
    generated for the KOMPAS type libraries go to the user's profile instead."""
    if not getattr(sys, "frozen", False):
        return
    import win32com

    gen = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "KompasAI" / "gen_py"
    gen.mkdir(parents=True, exist_ok=True)
    win32com.__gen_path__ = str(gen)
    from win32com.client import gencache

    gencache.is_readonly = False
    gencache.GetGeneratePath()


class Api5Backend:
    """Draws into a new KOMPAS drawing through API5."""

    def __init__(self, visible: bool = True, log=print, parametric: bool = False):
        _prepare_win32com()
        # parametric: geometry through API7 so that constraints can be set on it
        self.parametric = parametric
        self._arc7_broken = False
        import pythoncom
        from win32com.client import Dispatch, constants, gencache

        self.log = log
        module = None
        for guid, major, minor, name in _find_kompas_typelibs():
            try:
                m = gencache.EnsureModule(guid, 0, major, minor)
            except Exception as exc:  # some KOMPAS type libraries are not needed
                log(f"  библиотека {name}: {exc!r}")
                continue
            if m is not None and hasattr(m, "KompasObject"):
                module = m
        if module is None:
            raise RuntimeError("Не найдена библиотека типов API5 КОМПАС (Kompas6API5)")
        self.m = module
        self.constants = constants
        raw = Dispatch("Kompas.Application.5")
        self.kompas = module.KompasObject(raw._oleobj_.QueryInterface(
            module.KompasObject.CLSID, pythoncom.IID_IDispatch))
        self.kompas.Visible = visible
        self.doc = None
        self._drawing7 = None  # API7 container of the active view, for texts with indices

    # --- helpers ------------------------------------------------------------------

    def _param(self, const_name: str, interface: str):
        return getattr(self.m, interface)(self.kompas.GetParamStruct(getattr(self.constants, const_name)))

    def _sub(self, interface: str, raw):
        return getattr(self.m, interface)(raw)

    def last_error(self) -> int:
        try:
            return int(self.kompas.ksReturnResult())
        except Exception:
            return -1

    def _set_text(self, txt, text: DimText) -> None:
        txt.Init(False)
        if text.auto:
            txt.bitFlag = 1
        else:
            txt.bitFlag = 0
            arr = self._sub("ksDynamicArray", txt.GetTextArr())
            item = self._param("ko_Char255", "ksChar255")
            item.str = kompas_text(text.value)
            arr.ksAddArrayItem(-1, item)
        if text.diameter_sign:
            txt.sign = 1

    # --- Backend --------------------------------------------------------------------

    def new_sheet(self, format_index: int, landscape: bool) -> None:
        doc = self.kompas.Document2D()
        par = self._param("ko_DocumentParam", "ksDocumentParam")
        par.Init()
        par.type = FORMAT_DOC_SHEET
        par.regime = 0
        sheet = self._sub("ksSheetPar", par.GetLayoutParam())
        sheet.Init()
        std = self._sub("ksStandartSheet", sheet.GetSheetParam())
        std.Init()
        std.format, std.multiply, std.direct = format_index, 1, bool(landscape)
        if not doc.ksCreateDocument(par):
            raise RuntimeError(f"КОМПАС не создал документ (код {self.last_error()})")
        self.doc = doc
        self._drawing7 = None

    def open_view(self, origin: Point, scale: float, name: str) -> bool:
        par = self._param("ko_ViewParam", "ksViewParam")
        par.Init()
        par.x, par.y, par.scale_, par.name = origin[0], origin[1], scale, name
        ref = self.doc.ksCreateSheetView(par, 1)
        ok = ref[0] if isinstance(ref, tuple) else ref
        self._drawing7 = None  # the new view is the active one now
        return bool(ok)

    def line(self, p1, p2, style):
        if self.parametric:
            seg = self._api7_drawing().LineSegments.Add()
            seg.X1, seg.Y1, seg.X2, seg.Y2, seg.Style = p1[0], p1[1], p2[0], p2[1], style
            return seg if seg.Update() else None
        return self.doc.ksLineSeg(p1[0], p1[1], p2[0], p2[1], style)

    def circle(self, center, radius, style):
        if self.parametric:
            c = self._api7_drawing().Circles.Add()
            c.Xc, c.Yc, c.Radius, c.Style = center[0], center[1], radius, style
            return c if c.Update() else None
        return self.doc.ksCircle(center[0], center[1], radius, style)

    def arc(self, center, radius, start, end, style):
        if self.parametric and not self._arc7_broken:
            try:
                return self._arc7(center, radius, start, end, style)
            except Exception as exc:  # seen in the exe: FileNotFoundError from the wrapper
                self._arc7_broken = True
                self.log(f"  дуги через API7 недоступны ({exc!r}) — строю через API5, без связей")
        return self.doc.ksArcByAngle(center[0], center[1], radius, start, end, 1, style)

    def _arc7(self, center, radius, start, end, style):
        """API7 arc. In the exe the typed wrapper of the arc collection failed
        with FileNotFoundError (all 56 arcs of the fitting were left out), so the
        arc is made through late binding, which needs no generated wrapper."""
        from win32com.client import dynamic

        container = dynamic.Dispatch(self._api7_drawing()._oleobj_)
        a = container.Arcs.Add()
        a.Xc, a.Yc, a.Radius = center[0], center[1], radius
        a.Angle1, a.Angle2, a.Direction, a.Style = start, end, True, style
        return a if a.Update() else None

    # --- parametric constraints (API7, prototype/api_test10.py) ---------------------

    CONSTRAINTS = {"horizontal": "ksCHorizontal", "vertical": "ksCVertical",
                   "coincident": "ksCMergePoints", "tangent": "ksCTangentTwoCurves",
                   "parallel": "ksCParallel", "perpendicular": "ksCPerpendicular",
                   "concentric": "ksCConcentricity", "fixed_point": "ksCFixedPoint",
                   "fixed_length": "ksCFixedLenght", "fixed_angle": "ksCFixedAngle"}

    def constrain(self, kind, a, b=None, index=None, partner_index=None) -> bool:
        """A KOMPAS constraint on objects returned by line/circle/arc in
        parametric mode. ``index``/``partner_index``: 0 = start, 1 = end point."""
        name = self.CONSTRAINTS.get(kind)
        if name is None or not hasattr(self.constants, name):
            return False
        if isinstance(a, int) or isinstance(b, int):
            return False  # an API5 object (int reference) takes no API7 constraint
        c = _interface(a, "IDrawingObject1").NewConstraint()
        if c is None:
            return False
        c.ConstraintType = getattr(self.constants, name)
        if index is not None:
            c.Index = index
        if b is not None:
            c.Partner = b
        if partner_index is not None:
            c.PartnerIndex = partner_index
        return bool(c.Create())

    def point(self, p):
        return self.doc.ksPoint(p[0], p[1], 0)

    def text(self, p, value, height, angle):
        value = kompas_text(value)
        return self.doc.ksText(p[0], p[1], angle, height, 1.0, 0, value)

    def rich_text(self, p, parts, height, angle):
        # Through API7 on the active view of the same document (the scaled view
        # when one was opened). Height and angle of API7 texts are not confirmed
        # yet: a turned text is left to the per-part fallback.
        if abs(angle) > 0.01:
            raise NotImplementedError("текст с индексом под углом")
        drawing = self._api7_drawing()
        obj = drawing.DrawingTexts.Add()
        if obj is None:
            raise NotImplementedError("API7 недоступен (нет лицензии)")
        obj.X, obj.Y = p
        from win32com.client import CastTo

        line = CastTo(obj, "IText").Add()
        for value, kind in index_items(parts):
            item = line.Add()
            item.ItemType = kind
            item.Str = value
            item.Update()
        return bool(obj.Update())

    def _api7_view(self):
        from win32com.client import CastTo, gencache

        app = gencache.EnsureDispatch("Kompas.Application.7")
        doc2d = CastTo(app.ActiveDocument, "IKompasDocument2D")
        return doc2d.ViewsAndLayersManager.Views.ActiveView

    def _api7_drawing(self):
        if self._drawing7 is None:
            from win32com.client import CastTo

            self._drawing7 = CastTo(self._api7_view(), "IDrawingContainer")
        return self._drawing7

    def linear_dim(self, p1, p2, offset, kind, text, text_right=False, line_point=None):
        """``text_right``: the value goes on the dimension line extended past the
        right extension line, like on the source (API7 ShelfDirection = 1,
        api_test12 variant I) — for small sizes whose value does not fit."""
        if text_right and line_point is not None and kind == LINEAR_HORIZONTAL \
                and not text.diameter_sign:
            try:
                ref = self._linear7(p1, p2, line_point, text)
                if ref:
                    return ref
            except Exception as exc:
                self.log(f"  размер с текстом справа через API7: {exc!r} — строю через API5")
        return self._linear5(p1, p2, offset, kind, text)

    def _linear7(self, p1, p2, line_point, text):
        from win32com.client import CastTo

        symbols = CastTo(self._api7_view(), "ISymbols2DContainer")
        dim = symbols.LineDimensions.Add()
        dim.X1, dim.Y1, dim.X2, dim.Y2 = p1[0], p1[1], p2[0], p2[1]
        dim.X3, dim.Y3 = line_point
        dim.Orientation = self.constants.ksLinDHorizontal
        CastTo(dim, "IDimensionParams").ShelfDirection = 1
        if not text.auto:
            t = CastTo(dim, "IDimensionText")
            t.AutoNominalValue = False
            t.NominalText.Str = kompas_text(text.value)
        return dim if dim.Update() else None

    def _linear5(self, p1, p2, offset, kind, text):
        par = self._param("ko_LDimParam", "ksLDimParam")
        src = self._sub("ksLDimSourceParam", par.GetSPar())
        src.Init()
        src.x1, src.y1, src.x2, src.y2 = p1[0], p1[1], p2[0], p2[1]
        src.dx, src.dy = offset
        src.basePoint, src.ps = 1, kind
        self._sub("ksDimDrawingParam", par.GetDPar()).Init()
        self._set_text(self._sub("ksDimTextParam", par.GetTPar()), text)
        return self.doc.ksLinDimension(par)

    def radial_dim(self, center, radius, angle, diameter, text, text_dist=None):
        """``text_dist``: distance in sheet mm from the arrow on the arc to the
        value along the dimension line (ksRDimDrawingParam.textPos), so the
        value stands where the source drawing has it, off the part. API7
        ShelfX/ShelfY are ignored by KOMPAS (api_test12, variants D–F)."""
        par = self._param("ko_RDimParam", "ksRDimParam")
        src = self._sub("ksRDimSourceParam", par.GetSPar())
        src.Init()
        src.xc, src.yc, src.rad = center[0], center[1], radius
        drw = self._sub("ksRDimDrawingParam", par.GetDPar())
        drw.Init()
        drw.ang = angle
        if text_dist is not None and not diameter:
            drw.textPos = text_dist
        self._set_text(self._sub("ksDimTextParam", par.GetTPar()), text)
        method = self.doc.ksDiamDimension if diameter else self.doc.ksRadDimension
        ref = method(par)
        if not ref and text_dist is not None and not diameter:
            drw.textPos = 0  # KOMPAS refused the position: the default placement
            ref = method(par)
        return ref

    def angular_dim(self, center, start, end, radius, text, extension=True):
        """``extension=False``: no extension lines (ksDimDrawingParam.pl1/pl2 = 1,
        api_test12 variant C); the caller draws them from the sides."""
        par = self._param("ko_ADimParam", "ksADimParam")
        src = self._sub("ksADimSourceParam", par.GetSPar())
        src.Init()
        src.xc, src.yc, src.ang1, src.ang2, src.rad, src.dir = \
            center[0], center[1], start, end, radius, 1
        drw = self._sub("ksDimDrawingParam", par.GetDPar())
        drw.Init()
        if not extension:
            drw.pl1, drw.pl2 = 1, 1
        self._set_text(self._sub("ksDimTextParam", par.GetTPar()), text)
        return self.doc.ksAngDimension(par)

    def hatch(self, contours, angle, step):
        # ksHatch opens a hatch; objects created until ksEndObj are its boundary.
        self.doc.ksHatch(0, angle, step, 0.0, 0.0, 0.0)
        for ring in contours:
            for a, b in zip(ring, ring[1:]):
                if math.dist(a, b) > 1e-6:
                    self.doc.ksLineSeg(a[0], a[1], b[0], b[1], 1)
        return self.doc.ksEndObj()

    def save(self, path):
        return bool(self.doc.ksSaveDocument(path))

    # --- 3D -----------------------------------------------------------------------------

    def revolve_part(self, loops, path: str, threads=(), log=None) -> bool:
        """A part made by revolving closed profile loops 360° around the X axis.

        Calls confirmed by prototype/api_test9.py and api_test11.py (KOMPAS v23):
        Document3D.Create, sketch on the XOY plane, ksBaseRotatedDefinition,
        SaveAs; while the sketch is edited the active API7 document is the
        sketch, so its objects are made through API7 and get constraints
        (a parametric sketch). ``loops``: closed loops of ("line", p1, p2) /
        ("arc", center, r, a1, a2) in model mm, x along the axis, y the radius.
        ``threads``: model3d.revolve.ThreadSpec — cosmetic threads on the part.
        """
        log = log or self.log
        m, c = self.m, self.constants
        doc3d = self.kompas.Document3D()
        if not doc3d.Create(False, True):
            raise RuntimeError(f"КОМПАС не создал деталь (код {self.last_error()})")
        part = doc3d.GetPart(c.pTop_Part)
        sketch = part.NewEntity(c.o3d_sketch)
        sdef = m.ksSketchDefinition(sketch.GetDefinition())
        sdef.SetPlane(part.GetDefaultEntity(c.o3d_planeXOY))
        sketch.Create()
        d2 = sdef.BeginEdit()
        try:
            made, tried = self._sketch7(loops, d2)
            log(f"Эскиз через API7: связей создано {made} из {tried}"
                + (" — все наложены" if made == tried else ""))
        except Exception as exc:
            log(f"Эскиз через API7 не удался ({exc!r}) — строю через API5, без связей")
            self._sketch5(d2, loops)
        sdef.EndEdit()
        rot = part.NewEntity(c.o3d_baseRotated)
        rdef = m.ksBaseRotatedDefinition(rot.GetDefinition())
        rdef.SetSideParam(True, 360.0)
        rdef.SetSketch(sketch)
        if not rot.Create():
            raise RuntimeError(f"Операция вращения не выполнена (код {self.last_error()})")
        for t in threads:
            try:
                ok = self._thread(part, t)
                log(f"Резьба {t.text()}: {'создана' if ok else 'не создана'}")
            except Exception as exc:
                log(f"Резьба {t.text()}: {exc!r}")
        return bool(doc3d.SaveAs(path))

    @staticmethod
    def _sketch_extent(loops):
        xs = []
        for loop in loops:
            for seg in loop:
                if seg[0] == "line":
                    xs += [seg[1][0], seg[2][0]]
                else:
                    xs += [seg[1][0] - seg[2], seg[1][0] + seg[2]]
        return min(xs), max(xs)

    def _sketch5(self, d2, loops):
        for loop in loops:
            for seg in loop:
                if seg[0] == "line":
                    (ax, ay), (bx, by) = seg[1], seg[2]
                    if math.hypot(bx - ax, by - ay) > 1e-6:
                        d2.ksLineSeg(ax, ay, bx, by, 1)
                else:
                    (cx, cy), r, a1, a2 = seg[1], seg[2], seg[3], seg[4]
                    d2.ksArcByAngle(cx, cy, r, a1, a2, 1, 1)
        x0, x1 = self._sketch_extent(loops)
        d2.ksLineSeg(x0 - 5.0, 0.0, x1 + 5.0, 0.0, 3)  # the axis of revolution

    def _sketch7(self, loops, d2) -> tuple[int, int]:
        """Sketch objects through API7 + constraints that define the sketch
        fully (model3d.sketch_dof): joints, horizontal/vertical lines, tangent
        fillets, then fixed points and lengths for what is still free — each
        only if it is not implied by the others (no over-definition)."""
        from ..model3d.sketch_dof import full_definition

        saved = (self.parametric, self._drawing7)
        self.parametric, self._drawing7 = True, None  # the active document: the sketch
        try:
            x0, x1 = self._sketch_extent(loops)
            axis = ((x0 - 5.0, 0.0), (x1 + 5.0, 0.0))
            segments, jobs, left = full_definition(loops, axis)
            objs = []
            for seg in segments[:-1]:
                objs.append(self.line(seg[1], seg[2], 1) if seg[0] == "line"
                            else self._sketch_arc(d2, seg))
            objs.append(self.line(axis[0], axis[1], 3))  # the axis of revolution
            if not all(objs):
                raise RuntimeError("не все объекты эскиза созданы")
            made, failed = 0, {}
            for job in jobs:
                b = objs[job.b] if job.b is not None else None
                try:
                    ok = bool(self.constrain(job.kind, objs[job.a], b, job.ia, job.ib))
                except Exception:
                    ok = False
                made += ok
                if not ok:
                    failed[job.kind] = failed.get(job.kind, 0) + 1
            if failed:
                self.log("  не наложены: " + ", ".join(f"{k} {v}" for k, v in failed.items()))
            if left:
                self.log(f"  эскиз недоопределён: свободных степеней {left}")
            elif not failed:
                self.log("  по расчёту эскиз полностью определён (степеней свободы 0)")
            return made, len(jobs)
        finally:
            self.parametric, self._drawing7 = saved

    def _sketch_arc(self, d2, seg):
        """API7 arc (constrainable) or, when API7 arcs fail, an API5 one (an int
        reference: built, but left out of the constraints)."""
        (cx, cy), r, a1, a2 = seg[1], seg[2], seg[3], seg[4]
        if not self._arc7_broken:
            try:
                obj = self._arc7((cx, cy), r, a1, a2, 1)
                if obj:
                    return obj
            except Exception as exc:
                self._arc7_broken = True
                self.log(f"  дуги через API7 недоступны ({exc!r}) — дуги эскиза через API5")
        return int(d2.ksArcByAngle(cx, cy, r, a1, a2, 1, 1)) or None

    def _thread(self, part, t) -> bool:
        """Cosmetic thread on the cylinder through (x, r, 0) (api_test11 names)."""
        c, m = self.constants, self.m
        faces = part.EntityCollection(c.o3d_face)
        faces.SelectByPoint(t.x, t.radius, 0.0)
        if faces.GetCount() == 0:
            raise RuntimeError("цилиндр под резьбу не найден")
        thread = part.NewEntity(c.o3d_thread)
        tdef = m.ksThreadDefinition(thread.GetDefinition())
        tdef.allLength = True
        tdef.autoDefinDr = False
        tdef.dr = t.diameter
        tdef.p = t.pitch
        tdef.outside = t.outside
        tdef.SetBaseObject(faces.First())
        return bool(thread.Create())


def _interface(obj, name: str):
    """``obj`` seen through the API7 interface ``name``. Objects made through
    late binding (arcs, see _arc7) are not known to the generated wrapper, so
    CastTo can fail on them; the interface is then asked for directly."""
    from win32com.client import CastTo

    try:
        return CastTo(obj, name)
    except Exception:
        import pythoncom
        from win32com.client import dynamic, gencache

        mod = gencache.GetModuleForTypelib(API7_TYPELIB, 0, 1, 0)
        iid = mod.NamesToIIDMap[name]
        return dynamic.Dispatch(obj._oleobj_.QueryInterface(iid, pythoncom.IID_IDispatch))


API7_TYPELIB = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"


def _seg_end(seg, which):
    if seg[0] == "line":
        return seg[1] if which == 0 else seg[2]
    (cx, cy), r, a1, a2 = seg[1], seg[2], seg[3], seg[4]
    a = math.radians(a1 if which == 0 else a2)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def _joint_indices(a, b):
    """Which ends (0 = start, 1 = end) of a and b meet."""
    best = min(((i, j) for i in (0, 1) for j in (0, 1)),
               key=lambda ij: math.dist(_seg_end(a, ij[0]), _seg_end(b, ij[1])))
    return best


def _tangent(a, b) -> bool:
    line, arc = (a, b) if a[0] == "line" else (b, a)
    (x1, y1), (x2, y2) = line[1], line[2]
    (cx, cy), r = arc[1], arc[2]
    n = math.hypot(x2 - x1, y2 - y1)
    if n < 1e-9:
        return False
    dist = abs((x2 - x1) * (y1 - cy) - (x1 - cx) * (y2 - y1)) / n
    return abs(dist - r) <= 1e-3 * max(1.0, r)
