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
        self._swapped_arcs: dict[int, object] = {}  # arcs stored end → start (see _arc7)
        self._arcs: dict[int, object] = {}  # API7 arcs made here, by id (kept alive)
        self._arc_indices: dict[int, int] | None = None  # our 0/1 → KOMPAS point index
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
        # Our arcs run counter-clockwise from start to end; Direction = True is
        # clockwise. KOMPAS may also store the angles the other way round (arcs
        # through 0° came out as the remaining three quarters of the circle), so
        # the stored arc is read back: a wrong side is turned over, and when the
        # stored Angle1 is our end the point indices of the constraints swap.
        a.Angle1, a.Angle2, a.Direction, a.Style = start, end, False, style
        if not a.Update():
            return None
        try:
            for _ in range(2):
                state = arc_state(start, end, float(a.Angle1), float(a.Angle2), bool(a.Direction))
                if state != "flip":
                    break
                a.Direction = not bool(a.Direction)
                a.Update()
            if state == "flip":
                self.log(f"  дуга R{radius:g}: КОМПАС строит её с другой стороны")
            elif state == "swapped":
                self._swapped_arcs[id(a)] = a  # kept alive: the id stays unique
        except Exception as exc:  # no read-back: keep the arc as made
            self.log(f"  дуга: не удалось проверить направление ({exc!r})")
        self._arcs[id(a)] = a
        return a

    def _arc_point_index(self, arc, ours: int) -> int:
        """KOMPAS point index of the start (0) or end (1) of one of our arcs."""
        if id(arc) in self._swapped_arcs:
            ours = 1 - ours
        if self._arc_indices is None:
            self._arc_indices = {0: 0, 1: 1}
            try:
                self._arc_indices = self._probe_arc_indices()
                self.log(f"  точки дуги в связях КОМПАС: начало = {self._arc_indices[0]}, "
                         f"конец = {self._arc_indices[1]}")
            except Exception as exc:
                self.log(f"  нумерацию точек дуги проверить не удалось ({exc!r}) — беру 0/1")
        return self._arc_indices[ours]

    def _probe_arc_indices(self) -> dict[int, int]:
        """Which constraint point index is the start and which the end of an
        arc: a segment end is merged with point k of a test arc far off the
        drawing and the point it lands on is looked up; both are then deleted.
        (A merge with index 0 put the arc centre on the segment end — the
        small circles at the joints of the fitting.)"""
        found = {}
        for k in (0, 1, 2):
            # construction style (6): left over, they would not enter a contour
            arc = self._arc7((1000.0, 1000.0), 10.0, 0.0, 90.0, 6)
            self._arcs.pop(id(arc), None)
            seg = self.line((1010.5, 1000.3), (1030.0, 1000.3), 6)
            try:
                c = _interface(seg, "IDrawingObject1").NewConstraint()
                c.ConstraintType = self.constants.ksCMergePoints
                c.Index, c.Partner, c.PartnerIndex = 0, arc, k
                if c.Create():
                    xc, yc, r = float(arc.Xc), float(arc.Yc), float(arc.Radius)
                    a1, a2 = math.radians(float(arc.Angle1)), math.radians(float(arc.Angle2))
                    points = {"center": (xc, yc),
                              "start": (xc + r * math.cos(a1), yc + r * math.sin(a1)),
                              "end": (xc + r * math.cos(a2), yc + r * math.sin(a2))}
                    p = (float(seg.X1), float(seg.Y1))
                    name = min(points, key=lambda n: math.dist(points[n], p))
                    if math.dist(points[name], p) < 1e-3:
                        found[name] = k
            finally:
                for obj in (seg, arc):
                    try:
                        _interface(obj, "IDrawingObject").Delete()
                    except Exception:
                        try:
                            obj.Delete()
                        except Exception as exc:
                            self.log(f"  пробный объект не удалён ({exc!r})")
        if "start" not in found or "end" not in found:
            raise RuntimeError(f"найдено только {found}")
        return {0: found["start"], 1: found["end"]}

    def ellipse(self, center, a, b, angle, style):
        """API7 IEllipse through the typed wrapper of the view (the late-bound
        one failed with FileNotFoundError), else API5 ksEllipse with the field
        names its structure has."""
        errors = []
        try:
            e = self._api7_drawing().Ellipses.Add()
            e.Xc, e.Yc, e.SemiAxisA, e.SemiAxisB, e.Angle, e.Style = \
                center[0], center[1], a, b, angle, style
            if e.Update():
                return e
            errors.append("API7: Update() = False")
        except Exception as exc:
            errors.append(f"API7: {exc!r}")
        try:
            par = self._param("ko_EllipseParam", "ksEllipseParam")
            par.Init()
            names = set(getattr(type(par), "_prop_map_put_", {}))
            for keys, value in ((("xc", "xC"), center[0]), (("yc", "yC"), center[1]),
                                (("a", "A"), a), (("b", "B"), b),
                                (("angle", "ang", "Angle"), angle), (("style", "Style"), style)):
                key = next((k for k in keys if k in names), keys[0])
                setattr(par, key, value)
            ref = self.doc.ksEllipse(par)
            if ref:
                return ref
            errors.append(f"API5: ksEllipse = 0 (поля {sorted(names)})")
        except Exception as exc:
            errors.append(f"API5: {exc!r}")
        if not getattr(self, "_ellipse_logged", False):
            self._ellipse_logged = True
            self.log("  эллипс не построен: " + "; ".join(errors))
        return None

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
            c.Index = self._arc_point_index(a, index) if id(a) in self._arcs else index
        if b is not None:
            c.Partner = b
        if partner_index is not None:
            c.PartnerIndex = self._arc_point_index(b, partner_index) if id(b) in self._arcs \
                else partner_index
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

    def linear_dim(self, p1, p2, offset, kind, text, text_right=False, line_point=None,
                   text_offset=None, text_at=None):
        """``text_at``: where the value starts, as on the source — set through
        API7 IDimension2D.SetTextPosition (api_test15). Without it (or when it
        fails): ``text_right`` puts the value right of a small size (API7
        ShelfDirection = 1, api_test12 I), ``text_offset`` along the line from
        the first point (ksDimDrawingParam.textPos)."""
        if line_point is not None and (text_at is not None or text_right) \
                and kind in (LINEAR_HORIZONTAL, LINEAR_VERTICAL) \
                and not (text.diameter_sign and text.auto):
            try:
                ref = self._linear7(p1, p2, line_point, text, kind, text_right, text_at)
                if ref:
                    return ref
            except Exception as exc:
                self._once("linear7", f"  размер через API7: {exc!r} — строю через API5")
        return self._linear5(p1, p2, offset, kind, text, text_offset)

    def _once(self, key, message):
        seen = self.__dict__.setdefault("_logged", set())
        if key not in seen:
            seen.add(key)
            self.log(message)

    def _place_text(self, dim, text_at) -> None:
        from win32com.client import CastTo

        try:
            CastTo(dim, "IDimension2D").SetTextPosition(text_at[0], text_at[1])
            dim.Update()
        except Exception as exc:
            self._once("place_text", f"  положение текста размера: {exc!r}")

    def _api7_text(self, dim, text, prefix=""):
        """Manual value of an API7 dimension (Unicode: Ø and × as they are)."""
        from win32com.client import CastTo

        if text.auto:
            return
        t = CastTo(dim, "IDimensionText")
        t.AutoNominalValue = False
        t.NominalText.Str = prefix + text.value

    def _linear7(self, p1, p2, line_point, text, kind=LINEAR_HORIZONTAL, text_right=True,
                 text_at=None):
        from win32com.client import CastTo

        symbols = CastTo(self._api7_view(), "ISymbols2DContainer")
        dim = symbols.LineDimensions.Add()
        dim.X1, dim.Y1, dim.X2, dim.Y2 = p1[0], p1[1], p2[0], p2[1]
        dim.X3, dim.Y3 = line_point
        dim.Orientation = self.constants.ksLinDHorizontal if kind == LINEAR_HORIZONTAL \
            else self.constants.ksLinDVertical
        if text_right and text_at is None:
            CastTo(dim, "IDimensionParams").ShelfDirection = 1
        self._api7_text(dim, text, "Ø" if text.diameter_sign else "")
        if not dim.Update():
            return None
        if text_at is not None:
            self._place_text(dim, text_at)
        return dim

    def _linear5(self, p1, p2, offset, kind, text, text_offset=None):
        """``text_offset``: where the value stands along the dimension line,
        sheet mm from its middle (ksDimDrawingParam.textPos, like the radius
        in api_test13; to be confirmed by api_test14)."""
        par = self._param("ko_LDimParam", "ksLDimParam")
        src = self._sub("ksLDimSourceParam", par.GetSPar())
        src.Init()
        src.x1, src.y1, src.x2, src.y2 = p1[0], p1[1], p2[0], p2[1]
        src.dx, src.dy = offset
        src.basePoint, src.ps = 1, kind
        drw = self._sub("ksDimDrawingParam", par.GetDPar())
        drw.Init()
        if text_offset is not None:
            drw.textPos = text_offset
        self._set_text(self._sub("ksDimTextParam", par.GetTPar()), text)
        ref = self.doc.ksLinDimension(par)
        if not ref and text_offset is not None:
            drw.textPos = 0
            ref = self.doc.ksLinDimension(par)
        return ref

    def radial_dim(self, center, radius, angle, diameter, text, text_dist=None, text_at=None):
        if text_at is not None:
            try:
                from win32com.client import CastTo

                symbols = CastTo(self._api7_view(), "ISymbols2DContainer")
                coll = symbols.DiametralDimensions if diameter else symbols.RadialDimensions
                dim = coll.Add()
                dim.Xc, dim.Yc, dim.Radius, dim.Angle = center[0], center[1], radius, angle
                if not text.auto:  # KOMPAS writes R / Ø itself
                    t = CastTo(dim, "IDimensionText")
                    t.AutoNominalValue = False
                    t.NominalText.Str = text.value.lstrip("RØ")
                if dim.Update():
                    self._place_text(dim, text_at)
                    return dim
            except Exception as exc:
                self._once("radial7", f"  радиус через API7: {exc!r} — строю через API5")
        return self._radial5(center, radius, angle, diameter, text, text_dist)

    def _radial5(self, center, radius, angle, diameter, text, text_dist=None):
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

    def revolve_part(self, loops, path: str, threads=(), log=None, flange=None,
                     fillets=()) -> bool:
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
        if flange is not None:
            try:
                self._flange(part, flange, log)
            except Exception as exc:
                log(f"Фланец по виду с торца: {exc!r}")
            for f in fillets:
                try:
                    ok = self._fillet_after_milling(part, flange, f)
                    log(f"Скругление R{f.radius:g} после фрезеровки: "
                        f"{'выполнено' if ok else 'не выполнено'}")
                except Exception as exc:
                    log(f"Скругление R{f.radius:g} после фрезеровки: {exc!r}")
        for t in threads:
            try:
                ok = self._thread(part, t)
                log(f"Резьба {t.text()}: {'создана' if ok else 'не создана'}")
            except Exception as exc:
                log(f"Резьба {t.text()}: {exc!r}")
        return bool(doc3d.SaveAs(path))

    def _flange(self, part, flange, log) -> None:
        """The flange outline of the end view (model3d.endview.FlangeSpec): the
        outline extruded over the flange (adds what reaches past the revolved
        disc) and everything outside it cut away there (flats, notches). The
        flange is centred on the YOZ plane (the caller shifts the profile), so
        both are made to both sides by half the thickness."""
        c, m = self.constants, self.m
        half = (flange.x1 - flange.x0) / 2
        # In a sketch on YOZ the sketch x runs along Y and y along Z (read off the
        # cube of api_test15); the outline's first coordinate lies in the
        # section plane XOY, i.e. along Y.
        outline = list(flange.loop)
        r = flange.radius + 10.0
        square = [("line", (-r, -r), (r, -r)), ("line", (r, -r), (r, r)),
                  ("line", (r, r), (-r, r)), ("line", (-r, r), (-r, -r))]
        bore = [("circle", (0.0, 0.0), flange.bore)] if flange.bore > 0 else []
        for name, loops, entity, interface in (
                ("выдавливание контура", [outline, bore], c.o3d_bossExtrusion,
                 "ksBossExtrusionDefinition"),
                ("вырез вокруг контура", [square, outline], c.o3d_cutExtrusion,
                 "ksCutExtrusionDefinition")):
            sketch = self._plane_sketch(part, c.o3d_planeYOZ, loops)
            op = part.NewEntity(entity)
            d = getattr(m, interface)(op.GetDefinition())
            if entity == c.o3d_cutExtrusion:
                d.cut = True
            depth = half + (flange.cut_extra if entity == c.o3d_cutExtrusion else 0.0)
            d.directionType = c.dtBoth
            d.SetSideParam(True, c.etBlind, depth, 0.0, False)
            d.SetSideParam(False, c.etBlind, depth, 0.0, False)
            d.SetSketch(sketch)
            log(f"Фланец: {name} — {'выполнено' if op.Create() else 'не выполнено'}")
        for h in flange.holes or []:
            try:
                log(f"Отверстие Ø{2 * h.radius:g} под {h.tilt:.0f}°: "
                    f"{'выполнено' if self._angled_hole(part, flange, h) else 'не выполнено'}")
            except Exception as exc:
                log(f"Отверстие Ø{2 * h.radius:g}: {exc!r}")

    def _angled_hole(self, part, flange, h) -> bool:
        """A hole from the flange face at (x_face, u→Y, v→Z) leaning in the
        X–Z plane: a circle on a plane at angle α to YOZ around the Y axis
        (sketch x along Y, y along (sin α·X + cos α·Z) — api_test15), cut
        through everything both ways."""
        c, m = self.constants, self.m
        if abs(h.mu) > 0.05:
            raise RuntimeError("наклон не в плоскости XZ — пока не строится")
        beta = math.radians(h.tilt)
        s = -float(h.into)  # +1: from the face at x1 towards x0
        dx, dz = -s * math.cos(beta), h.mv * math.sin(beta)
        x_face = flange.x1 if h.into < 0 else flange.x0
        alpha = math.atan2(-dz, dx)  # plane normal (cos α, 0, −sin α) along the hole
        if math.cos(alpha) < 0:
            alpha += math.pi
            alpha = (alpha + math.pi) % (2 * math.pi) - math.pi
        sx, sy, sz = x_face, h.u, h.v
        t = sx * dx + sz * dz
        px, py, pz = sx - t * dx, sy, sz - t * dz
        local = (py, px * math.sin(alpha) + pz * math.cos(alpha))
        plane = part.NewEntity(c.o3d_planeAngle)
        pd = m.ksPlaneAngleDefinition(plane.GetDefinition())
        pd.SetPlane(part.GetDefaultEntity(c.o3d_planeYOZ))
        pd.SetAxis(part.GetDefaultEntity(c.o3d_axisOY))
        pd.angle = math.degrees(alpha)
        if not plane.Create():
            raise RuntimeError("плоскость под углом не создана")
        sketch = part.NewEntity(c.o3d_sketch)
        sdef = m.ksSketchDefinition(sketch.GetDefinition())
        sdef.SetPlane(plane)
        sketch.Create()
        d2 = sdef.BeginEdit()
        d2.ksCircle(local[0], local[1], h.radius, 1)
        sdef.EndEdit()
        cut = part.NewEntity(c.o3d_cutExtrusion)
        cd = m.ksCutExtrusionDefinition(cut.GetDefinition())
        cd.cut = True
        cd.directionType = c.dtBoth
        cd.SetSideParam(True, c.etThroughAll, 0.0, 0.0, False)
        cd.SetSideParam(False, c.etThroughAll, 0.0, 0.0, False)
        cd.SetSketch(sketch)
        return bool(cut.Create())

    def _fillet_after_milling(self, part, flange, f) -> bool:
        """Round the corner edge left where the profile's fillet was taken out
        (model3d.endview.fillets_after_milling) — only where the flange still
        stands, i.e. along the section plane, not on the flats."""
        c, m = self.constants, self.m
        # which axis the flats face: a point on a flat (the flange's middle,
        # at the flats' distance) finds a face on it
        faces = part.EntityCollection(c.o3d_face)
        faces.SelectByPoint(0.0, 0.0, flange.inner)
        along_y = faces.GetCount() > 0  # flats square to Z: the flange stands along Y
        op = part.NewEntity(c.o3d_fillet)
        d = m.ksFilletDefinition(op.GetDefinition())
        d.radius = f.radius
        d.tangent = True
        arr = d.array()
        found = 0
        for sign in (1.0, -1.0):
            edges = part.EntityCollection(c.o3d_edge)
            p = (f.x, sign * f.y, 0.0) if along_y else (f.x, 0.0, sign * f.y)
            edges.SelectByPoint(*p)
            if edges.GetCount():
                arr.Add(edges.First())
                found += 1
        if not found:
            raise RuntimeError("ребро не найдено")
        return bool(op.Create())

    def _plane_sketch(self, part, plane, loops):
        m = self.m
        sketch = part.NewEntity(self.constants.o3d_sketch)
        sdef = m.ksSketchDefinition(sketch.GetDefinition())
        sdef.SetPlane(part.GetDefaultEntity(plane))
        sketch.Create()
        d2 = sdef.BeginEdit()
        self._draw5(d2, loops)
        sdef.EndEdit()
        return sketch

    @staticmethod
    def _draw5(d2, loops):
        for loop in loops:
            for seg in loop:
                if seg[0] == "circle":
                    d2.ksCircle(seg[1][0], seg[1][1], seg[2], 1)
                elif seg[0] == "line":
                    (ax, ay), (bx, by) = seg[1], seg[2]
                    if math.hypot(bx - ax, by - ay) > 1e-6:
                        d2.ksLineSeg(ax, ay, bx, by, 1)
                else:
                    (cx, cy), r, a1, a2 = seg[1], seg[2], seg[3], seg[4]
                    d2.ksArcByAngle(cx, cy, r, a1, a2, 1, 1)

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
                ok = False
                # a tangency is tried without point indices first (api_test10),
                # then at the shared ends
                tries = [(None, None), (job.ia, job.ib)] if job.kind == "tangent" \
                    else [(job.ia, job.ib)]
                for ia, ib in tries:
                    try:
                        ok = bool(self.constrain(job.kind, objs[job.a], b, ia, ib))
                    except Exception:
                        ok = False
                    if ok:
                        break
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
        # «outside» is read-only (KOMPAS takes it from the face); set where allowed
        try:
            tdef.outside = t.outside
        except AttributeError:
            pass
        tdef.SetBaseObject(faces.First())
        return bool(thread.Create())


def _swap_xy(seg):
    """The segment mirrored in the line y = x (x and y swap); an arc keeps
    running counter-clockwise."""
    if seg[0] == "line":
        return ("line", (seg[1][1], seg[1][0]), (seg[2][1], seg[2][0]))
    (cx, cy), r, a1, a2 = seg[1], seg[2], seg[3], seg[4]
    return ("arc", (cy, cx), r, (90.0 - a2) % 360.0, (90.0 - a1) % 360.0)


def _same_angle(a: float, b: float, tol: float = 0.01) -> bool:
    return abs((a - b + 180.0) % 360.0 - 180.0) <= tol


def arc_state(start, end, angle1, angle2, clockwise) -> str:
    """How KOMPAS stored the counter-clockwise arc start → end: "ok", "swapped"
    (the same arc, but Angle1 is our end: point indices 0/1 swap) or "flip"
    (the other part of the circle: the direction has to be turned)."""
    f, t = (angle2, angle1) if clockwise else (angle1, angle2)  # counter-clockwise f → t
    if _same_angle(f, start) and _same_angle(t, end):
        return "ok" if _same_angle(angle1, start) else "swapped"
    return "flip"


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
