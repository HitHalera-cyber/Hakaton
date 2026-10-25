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

from .backend import LINEAR_HORIZONTAL, LINEAR_VERTICAL, DimText, Point

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
        """Manual value of an API7 dimension. Strings reach KOMPAS in cp1251
        as through API5 (Ø came out as «Ш», × as «Ч»): × goes as x and the
        diameter sign as the dimension's Sign, never as a character."""
        from win32com.client import CastTo

        t = CastTo(dim, "IDimensionText")
        if text.diameter_sign:
            try:
                t.Sign = 1  # the diameter sign, as txt.sign = 1 in API5
            except Exception as exc:
                self._once("dim_sign", f"  знак диаметра через API7: {exc!r}")
        if getattr(text, "prefix", ""):
            t.Prefix.Str = kompas_text(text.prefix)
        if text.auto:
            return
        t.AutoNominalValue = False
        t.NominalText.Str = kompas_text(text.value)

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
        self._api7_text(dim, text)
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

    def radial_dim(self, center, radius, angle, diameter, text, text_dist=None, text_at=None,
                   branches=()):
        """``branches``: more arcs of the same value — [center, radius, arrow,
        leader start, arrow length]: added to the dimension as leaders where
        KOMPAS takes them (IRadialDimension.AddBranchByArcParam), else drawn as
        a thin line with an arrow.

        A radius with ``text_dist`` goes through API5: the arrow stays at
        ``angle`` and the value may stand past the centre (negative textPos,
        api_test13). API7 SetTextPosition turned the leader towards the value,
        so the arrow landed on the open side of a notch (R3) or of a fillet."""
        if text_dist is not None and not diameter:
            ref = self._radial5(center, radius, angle, diameter, text, text_dist)
            if ref:
                dim = self._from_ref(ref) if branches else None
                for b in branches:
                    if dim is None or not self._branch(dim, b):
                        self._leader(b[3], b[2], b[4] if len(b) > 4 else 2.5)
                return ref
        if text_at is not None or getattr(text, "prefix", ""):
            # a prefix («2 отв.») goes only through API7 (IDimensionText.Prefix)
            try:
                from win32com.client import CastTo

                symbols = CastTo(self._api7_view(), "ISymbols2DContainer")
                coll = symbols.DiametralDimensions if diameter else symbols.RadialDimensions
                dim = coll.Add()
                dim.Xc, dim.Yc, dim.Radius, dim.Angle = center[0], center[1], radius, angle
                if not text.auto:  # KOMPAS writes R / Ø itself
                    t = CastTo(dim, "IDimensionText")
                    t.AutoNominalValue = False
                    t.NominalText.Str = kompas_text(text.value.lstrip("RØ"))
                    if getattr(text, "prefix", ""):
                        t.Prefix.Str = kompas_text(text.prefix)
                if dim.Update():
                    if text_at is not None:
                        self._place_text(dim, text_at)
                    for b in branches:
                        if not self._branch(dim, b):
                            self._leader(b[3], b[2], b[4] if len(b) > 4 else 2.5)
                    return dim
            except Exception as exc:
                self._once("radial7", f"  радиус через API7: {exc!r} — строю через API5")
        ref = self._radial5(center, radius, angle, diameter, text, text_dist)
        for b in branches:
            self._leader(b[3], b[2], b[4] if len(b) > 4 else 2.5)
        return ref

    def _from_ref(self, ref):
        """The API7 object of an API5 reference (IApplication.TransferReference)."""
        try:
            from win32com.client import gencache

            app = gencache.EnsureDispatch("Kompas.Application.7")
            return app.TransferReference(ref, self.doc.reference)
        except Exception as exc:
            self._once("transfer", f"  объект API7 по ссылке API5: {exc!r}")
            return None

    def _branch(self, dim, b) -> bool:
        (cx, cy), r, tip = b[0], b[1], b[2]
        ang = math.degrees(math.atan2(tip[1] - cy, tip[0] - cx))
        last = "False"
        for target in (dim, "IRadialDimension", "IBranchs"):
            try:
                if isinstance(target, str):
                    from win32com.client import CastTo

                    target = CastTo(dim, target)
                for args in ((cx, cy, r, ang), (cx, cy, r)):
                    try:
                        ok = target.AddBranchByArcParam(*args)
                        if ok is not False:
                            target.Update()
                            return True
                    except Exception as exc:
                        last = exc
            except Exception as exc:
                last = exc
        self._once("branch", f"  вторая выноска радиуса: {last!r} — рисую линией со стрелкой")
        return False

    def _leader(self, start, tip, size):
        """A thin line ending in a filled arrow at ``tip`` (``size`` long, a
        third as wide): the second leader of a radius when KOMPAS takes none."""
        dx, dy = tip[0] - start[0], tip[1] - start[1]
        n = math.hypot(dx, dy)
        if n < 1e-6:
            return
        ux, uy = dx / n, dy / n
        bx, by = tip[0] - ux * size, tip[1] - uy * size
        w = size / 6
        left, right = (bx - uy * w, by + ux * w), (bx + uy * w, by - ux * w)
        self.line(start, (bx, by), 2)
        try:
            self.doc.ksColouring(0)  # a solid fill bounded by the objects up to ksEndObj
            for a, c in ((tip, left), (left, right), (right, tip)):
                self.doc.ksLineSeg(a[0], a[1], c[0], c[1], 1)
            if self.doc.ksEndObj():
                return
        except Exception as exc:
            self._once("colouring", f"  заливка стрелки: {exc!r} — штриховкой")
        self.hatch([[tip, left, right, tip]], 45.0, 0.1)
        for a, c in ((tip, left), (left, right), (right, tip)):
            self.line(a, c, 2)

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

    def angular_dim(self, center, start, end, radius, text, extension=True, shelf=None):
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
        if shelf is not None:
            # the value on a leader with a shelf: (direction ±1, leader angle, length)
            drw.shelfDir, drw.ang, drw.lenght = shelf
        self._set_text(self._sub("ksDimTextParam", par.GetTPar()), text)
        ref = self.doc.ksAngDimension(par)
        if not ref and shelf is not None:
            drw.shelfDir, drw.ang, drw.lenght = 0, 0.0, 0.0
            ref = self.doc.ksAngDimension(par)
        return ref

    def hatch(self, contours, angle, step):
        # ksHatch opens a hatch; objects created until ksEndObj are its boundary.
        # rings of points, or of ("line", p1, p2) / ("arc", c, r, a1, a2) segments
        self.doc.ksHatch(0, angle, step, 0.0, 0.0, 0.0)
        for ring in contours:
            if ring and isinstance(ring[0][0], str):
                for sg in ring:
                    if sg[0] == "line":
                        (ax, ay), (bx, by) = sg[1], sg[2]
                        if math.hypot(bx - ax, by - ay) > 1e-6:
                            self.doc.ksLineSeg(ax, ay, bx, by, 1)
                    else:
                        (cx, cy), r, a1, a2 = sg[1], sg[2], sg[3], sg[4]
                        self.doc.ksArcByAngle(cx, cy, r, a1, a2, 1, 1)
                continue
            for a, b in zip(ring, ring[1:]):
                if math.dist(a, b) > 1e-6:
                    self.doc.ksLineSeg(a[0], a[1], b[0], b[1], 1)
        return self.doc.ksEndObj()

    def save(self, path):
        if getattr(self, "_model_views", 0):
            self.rebuild()
        return bool(self.doc.ksSaveDocument(path))

    def rebuild(self) -> bool:
        """The sheet rebuilt (F5): a view of a model stays an empty frame until
        KOMPAS rebuilds the document — the drawing came out blank."""
        try:
            if self.doc.ksRebuildDocument():
                return True
        except Exception as exc:
            self.log(f"  перестроение через API5: {exc!r}")
        try:
            from win32com.client import CastTo, gencache

            app = gencache.EnsureDispatch("Kompas.Application.7")
            doc = CastTo(app.ActiveDocument, "IKompasDocument2D")
            return bool(doc.RebuildDocument())
        except Exception as exc:
            self.log(f"  перестроение через API7: {exc!r}")
        return False

    # --- 3D -----------------------------------------------------------------------------

    def revolve_part(self, loops, path: str, threads=(), log=None, flange=None,
                     fillets=(), channels=(), parametric: bool = True,
                     holes=()) -> bool:
        """A part made by revolving closed profile loops 360° around the X axis.

        Calls confirmed by prototype/api_test9.py and api_test11.py (KOMPAS v23):
        Document3D.Create, sketch on the XOY plane, ksBaseRotatedDefinition,
        SaveAs; while the sketch is edited the active API7 document is the
        sketch, so its objects are made through API7 and get constraints
        (a parametric sketch). ``loops``: closed loops of ("line", p1, p2) /
        ("arc", center, r, a1, a2) in model mm, x along the axis, y the radius.
        ``threads``: model3d.revolve.ThreadSpec — cosmetic threads on the part.
        ``channels``: model3d.channels.ChannelSpec — holes drilled across the
        axis (the swirl channels of an injector). ``parametric``: the sketch
        with constraints and driving dimensions (False: plain lines).
        """
        log = log or self.log
        m, c = self.m, self.constants
        if flange is not None:  # sketch axes of the planes used, found on a test part
            self._plane_axes(0.0, log)
            for h in flange.holes or []:
                alpha = _hole_geometry(flange, h)[0]
                self._plane_axes(alpha, log)
                self._plane_axes(-alpha, log)
        for along in sorted({ch.along for ch in channels}):
            self._default_plane_axes(along, log)
        if holes:
            self._plane_axes(0.0, log)  # the YOZ plane, square to the axis
        doc3d = self._new_part(log)
        self._doc3d = doc3d
        part = doc3d.GetPart(c.pTop_Part)
        sketch = part.NewEntity(c.o3d_sketch)
        sdef = m.ksSketchDefinition(sketch.GetDefinition())
        sdef.SetPlane(part.GetDefaultEntity(c.o3d_planeXOY))
        sketch.Create()
        with _editing(sdef) as d2:
            if not parametric:
                log("Эскиз без параметризации: простые отрезки и дуги")
                self._sketch5(d2, loops)
            else:
                try:
                    made, tried = self._sketch7(loops, d2)
                    log(f"Эскиз через API7: связей и размеров создано {made} из {tried}"
                        + (" — все наложены" if made == tried else ""))
                except Exception as exc:
                    log(f"Эскиз через API7 не удался ({exc!r}) — строю через API5, без связей")
                    self._sketch5(d2, loops)
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
        if holes:
            try:
                ok = self._axial_holes(part, holes)
                log(f"Отверстия вдоль оси ({len(holes)} × Ø{2 * holes[0].radius:g}): "
                    f"{'просверлены' if ok else 'не выполнены'}")
            except Exception as exc:
                log(f"Отверстия вдоль оси: {exc!r}")
        for ch in channels:
            try:
                log(f"Канал Ø{2 * ch.radius:g} (сверление): "
                    f"{'выполнен' if self._channel(part, ch, log) else 'не выполнен'}")
            except Exception as exc:
                log(f"Канал Ø{2 * ch.radius:g}: {exc!r}")
        for t in threads:
            try:
                ok = self._thread(part, t)
                log(f"Резьба {t.text()}: {'создана' if ok else 'не создана'}")
            except Exception as exc:
                log(f"Резьба {t.text()}: {exc!r}")
        return bool(doc3d.SaveAs(path))

    def _axial_holes(self, part, holes) -> bool:
        """Holes along the axis (model3d.holes.AxialHole: Y, Z of the centre):
        circles in a sketch on the YOZ plane, cut through everything both ways."""
        m, c = self.m, self.constants
        ex, ey = self._plane_axes(0.0)
        sketch = part.NewEntity(c.o3d_sketch)
        sdef = m.ksSketchDefinition(sketch.GetDefinition())
        sdef.SetPlane(part.GetDefaultEntity(c.o3d_planeYOZ))
        sketch.Create()
        with _editing(sdef) as d2:
            for h in holes:
                p = (0.0, h.y, h.z)
                sx = sum(a * b for a, b in zip(p, ex))
                sy = sum(a * b for a, b in zip(p, ey))
                d2.ksCircle(sx, sy, h.radius, 1)
        cut = part.NewEntity(c.o3d_cutExtrusion)
        cd = m.ksCutExtrusionDefinition(cut.GetDefinition())
        cd.cut = True
        cd.directionType = c.dtBoth
        cd.SetSideParam(True, c.etThroughAll, 0.0, 0.0, False)
        cd.SetSideParam(False, c.etThroughAll, 0.0, 0.0, False)
        cd.SetSketch(sketch)
        return bool(cut.Create())

    def _flange(self, part, flange, log) -> None:
        """The flange outline of the end view (model3d.endview.FlangeSpec): the
        outline extruded over the flange (adds what reaches past the revolved
        disc) and everything outside it cut away there (flats, notches). The
        flange is centred on the YOZ plane (the caller shifts the profile), so
        both are made to both sides by half the thickness."""
        c, m = self.constants, self.m
        half = (flange.x1 - flange.x0) / 2
        # The outline's first coordinate lies along Y (the section plane XOY),
        # the second along Z; the sketch axes on YOZ were found by _plane_axes.
        ex, ey = self._plane_axes(0.0, log)
        outline = _map_loop(flange.loop, lambda p: (p[0] * ex[1] + p[1] * ex[2],
                                                    p[0] * ey[1] + p[1] * ey[2]))
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
        (its sketch axes found by _plane_axes), cut over the hole's length."""
        c, m = self.constants, self.m
        alpha, point, reach, direction = _hole_geometry(flange, h)
        for kompas_angle in (alpha, -alpha):  # KOMPAS may turn the plane the other way
            ex, ey = self._plane_axes(kompas_angle, self.log)
            normal = (ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2],
                      ex[0] * ey[1] - ex[1] * ey[0])
            if abs(sum(a * b for a, b in zip(normal, direction))) > 0.99:
                alpha = kompas_angle
                break
        else:
            raise RuntimeError("плоскость поперёк отверстия не найдена")
        local = (sum(a * b for a, b in zip(point, ex)), sum(a * b for a, b in zip(point, ey)))
        if abs(alpha) < 1e-9:
            plane = part.GetDefaultEntity(c.o3d_planeYOZ)
        else:
            plane = self._angle_plane(part, alpha)
        sketch = part.NewEntity(c.o3d_sketch)
        sdef = m.ksSketchDefinition(sketch.GetDefinition())
        sdef.SetPlane(plane)
        sketch.Create()
        with _editing(sdef) as d2:
            d2.ksCircle(local[0], local[1], h.radius, 1)
        cut = part.NewEntity(c.o3d_cutExtrusion)
        cd = m.ksCutExtrusionDefinition(cut.GetDefinition())
        cd.cut = True
        cd.directionType = c.dtBoth
        # only as far as the hole goes (through everything it pierced the part
        # elsewhere when the sketch axes were guessed wrong)
        cd.SetSideParam(True, c.etBlind, reach, 0.0, False)
        cd.SetSideParam(False, c.etBlind, reach, 0.0, False)
        cd.SetSketch(sketch)
        return bool(cut.Create())

    def _channel(self, part, ch, log) -> bool:
        """A channel across the axis: a circle on the plane through the axis
        across the channel (XOZ for one along Y, XOY for one along Z), cut
        from there outwards past the outside.

        The sketch axes and the forward side come from the test part; if the
        cut is refused (it missed the part) or its wall is not where the
        channel should be, the other ways round are tried, and a wrong cut
        is taken back."""
        c, m = self.constants, self.m
        ex, ey, normal = self._default_plane_axes(ch.along, log)
        point = (ch.x, 0.0, ch.offset) if ch.along == 1 else (ch.x, ch.offset, 0.0)
        outwards = [0.0, 0.0, 0.0]
        outwards[ch.along] = float(ch.sign)
        forward = sum(a * b for a, b in zip(normal, outwards)) > 0
        local = (sum(a * b for a, b in zip(point, ex)), sum(a * b for a, b in zip(point, ey)))
        # a point on the channel's wall, well out along it
        wall = [point[k] + outwards[k] * 0.6 * ch.length for k in range(3)]
        wall[0] += ch.radius
        tries = [(sx, sy, fw) for fw in (forward, not forward)
                 for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1))]
        accepted = None  # the first way KOMPAS took, if no wall is ever found
        for n in range(len(tries) + 1):
            if n < len(tries):
                sx, sy, fw = tries[n]
            else:
                if accepted is None:
                    return False
                sx, sy, fw = accepted
                log("  стенку канала проверить не удалось — оставляю первый принятый вырез")
            plane = part.GetDefaultEntity(c.o3d_planeXOZ if ch.along == 1 else c.o3d_planeXOY)
            sketch = part.NewEntity(c.o3d_sketch)
            sdef = m.ksSketchDefinition(sketch.GetDefinition())
            sdef.SetPlane(plane)
            sketch.Create()
            with _editing(sdef) as d2:
                d2.ksCircle(sx * local[0], sy * local[1], ch.radius, 1)
            cut = part.NewEntity(c.o3d_cutExtrusion)
            cd = m.ksCutExtrusionDefinition(cut.GetDefinition())
            cd.cut = True
            cd.directionType = c.dtNormal if fw else c.dtReverse
            cd.SetSideParam(fw, c.etBlind, ch.length, 0.0, False)
            cd.SetSketch(sketch)
            made = bool(cut.Create())
            if made and n == len(tries):
                return True
            if made and accepted is None:
                accepted = (sx, sy, fw)
            if made and self._face_at(part, wall):
                if n:
                    log(f"  канал вырезан с {n + 1}-й попытки (оси эскиза {sx:+d}/{sy:+d}, "
                        f"{'вперёд' if fw else 'назад'})")
                return True
            for obj in ((cut, sketch) if made else (sketch,)):
                self._take_back(part, obj)
        return False

    def _face_at(self, part, p) -> bool:
        faces = part.EntityCollection(self.constants.o3d_face)
        faces.SelectByPoint(*p)
        return faces.GetCount() > 0

    def _take_back(self, part, obj) -> None:
        """Remove a feature that went wrong (a cut on the wrong side)."""
        for owner in (getattr(self, "_doc3d", None), part):
            try:
                if owner is not None and owner.DeleteObject(obj):
                    return
            except Exception:
                pass
        self._once("take_back", "  неудачный вырез не удалён из дерева")

    def _default_plane_axes(self, along: int, log=None):
        """For the plane across a channel along Y (1: XOZ) or Z (2: XOY): the 3D
        directions of its sketch x and y axes and of its normal (the way a
        "forward" cut goes). Found on a test part like _plane_axes: a cube
        cut one way by a circle R1 at sketch (10, 0) and R2 at (0, 10)."""
        cache = self.__dict__.setdefault("_default_axes", {})
        if along in cache:
            return cache[along]
        known = _known_axes().get(f"default:{along}")
        if known:  # found on an earlier run: no test part this time
            cache[along] = tuple(tuple(v) for v in known)
            return cache[along]
        unit = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        normal = unit[along]
        in_plane = [unit[0], unit[2] if along == 1 else unit[1]]
        try:
            found = self._probe_default_plane(along, normal, in_plane)
            (log or self.log)(f"  оси эскиза на плоскости {'XOZ' if along == 1 else 'XOY'}: "
                              f"x = {_vec(found[0])}, y = {_vec(found[1])}, "
                              f"вырез вперёд = {_vec(found[2])}")
            _remember_axes(f"default:{along}", found)
        except Exception as exc:
            found = (in_plane[0], in_plane[1], normal)
            (log or self.log)(f"  оси эскиза на плоскости {'XOZ' if along == 1 else 'XOY'} "
                              f"не найдены ({exc!r}) — беру x = X")
        cache[along] = found
        return found

    def _probe_default_plane(self, along, normal, in_plane):
        c, m = self.constants, self.m
        doc = self._new_part(self.log, invisible=True)  # the test part is not shown
        try:
            part = doc.GetPart(c.pTop_Part)
            sk = part.NewEntity(c.o3d_sketch)
            sd = m.ksSketchDefinition(sk.GetDefinition())
            sd.SetPlane(part.GetDefaultEntity(c.o3d_planeYOZ))
            sk.Create()
            d2 = sd.BeginEdit()
            for x1, y1, x2, y2 in ((-30, -30, 30, -30), (30, -30, 30, 30), (30, 30, -30, 30),
                                   (-30, 30, -30, -30)):
                d2.ksLineSeg(x1, y1, x2, y2, 1)
            sd.EndEdit()
            ext = part.NewEntity(c.o3d_baseExtrusion)
            ed = m.ksBaseExtrusionDefinition(ext.GetDefinition())
            ed.directionType = c.dtBoth
            ed.SetSideParam(True, c.etBlind, 30.0, 0.0, False)
            ed.SetSideParam(False, c.etBlind, 30.0, 0.0, False)
            ed.SetSketch(sk)
            if not ext.Create():
                raise RuntimeError("пробный куб не создан")
            sk2 = part.NewEntity(c.o3d_sketch)
            sd2 = m.ksSketchDefinition(sk2.GetDefinition())
            sd2.SetPlane(part.GetDefaultEntity(c.o3d_planeXOZ if along == 1 else c.o3d_planeXOY))
            sk2.Create()
            d3 = sd2.BeginEdit()
            d3.ksCircle(10.0, 0.0, 1.0, 1)
            d3.ksCircle(0.0, 10.0, 2.0, 1)
            sd2.EndEdit()
            cut = part.NewEntity(c.o3d_cutExtrusion)
            cd = m.ksCutExtrusionDefinition(cut.GetDefinition())
            cd.cut = True
            cd.directionType = c.dtNormal
            cd.SetSideParam(True, c.etBlind, 20.0, 0.0, False)
            cd.SetSketch(sk2)
            if not cut.Create():
                raise RuntimeError("пробный вырез не выполнен")

            def wall(direction, side, r, n):
                # a point on the wall of the hole of radius r centred 10 mm
                # along direction, 10 mm into the cut along n
                p = [10.0 * direction[k] + r * side[k] + 10.0 * n[k] for k in range(3)]
                faces = part.EntityCollection(c.o3d_face)
                faces.SelectByPoint(*p)
                return faces.GetCount() > 0

            cands = [v for u in in_plane for v in (u, tuple(-a for a in u))]
            norms = [normal, tuple(-a for a in normal)]
            found = {}
            for r in (1.0, 2.0):
                hits = [(v, n) for v in cands for n in norms
                        if wall(v, next(u for u in in_plane if abs(sum(a * b for a, b in zip(u, v))) < 0.5), r, n)]
                if len(hits) != 1:
                    raise RuntimeError(f"неоднозначно: R{r:g} — {len(hits)}")
                found[r] = hits[0]
            if found[1.0][1] != found[2.0][1]:
                raise RuntimeError("направление выреза не совпало")
            return found[1.0][0], found[2.0][0], found[1.0][1]
        finally:
            _close(doc)

    def _angle_plane(self, part, alpha):
        c, m = self.constants, self.m
        plane = part.NewEntity(c.o3d_planeAngle)
        pd = m.ksPlaneAngleDefinition(plane.GetDefinition())
        pd.SetPlane(part.GetDefaultEntity(c.o3d_planeYOZ))
        pd.SetAxis(part.GetDefaultEntity(c.o3d_axisOY))
        pd.angle = alpha
        if not plane.Create():
            raise RuntimeError("плоскость под углом не создана")
        return plane

    def _plane_axes(self, alpha, log=None):
        """3D directions of the sketch x and y axes on the plane at ``alpha``
        degrees to YOZ around the Y axis (0: YOZ itself). Found on a test part:
        a cube is cut by a circle R1 at sketch (10, 0) and R2 at (0, 10), and
        the walls of the holes are looked for at the candidate places
        (the first reading of api_test15 by eye was wrong)."""
        cache = self.__dict__.setdefault("_axes", {})
        key = round(alpha, 3)
        if key in cache:
            return cache[key]
        known = _known_axes().get(f"angle:{key}")
        if known:  # found on an earlier run: no test part this time
            cache[key] = tuple(tuple(v) for v in known)
            return cache[key]
        a = math.radians(alpha)
        y_axis, w = (0.0, 1.0, 0.0), (math.sin(a), 0.0, math.cos(a))
        try:
            found = self._probe_plane_axes(alpha, y_axis, w)
            (log or self.log)(f"  оси эскиза на плоскости {alpha:.1f}°: x = {_vec(found[0])}, "
                              f"y = {_vec(found[1])}")
            _remember_axes(f"angle:{key}", found)
        except Exception as exc:
            found = (y_axis, w)
            (log or self.log)(f"  оси эскиза на плоскости {alpha:.1f}° не найдены ({exc!r}) — "
                              "беру x = Y")
        cache[key] = found
        return found

    def _probe_plane_axes(self, alpha, y_axis, w):
        c, m = self.constants, self.m
        doc = self._new_part(self.log, invisible=True)  # the test part is not shown
        try:
            part = doc.GetPart(c.pTop_Part)
            sk = part.NewEntity(c.o3d_sketch)
            sd = m.ksSketchDefinition(sk.GetDefinition())
            sd.SetPlane(part.GetDefaultEntity(c.o3d_planeXOY))
            sk.Create()
            d2 = sd.BeginEdit()
            for x1, y1, x2, y2 in ((-30, -30, 30, -30), (30, -30, 30, 30), (30, 30, -30, 30),
                                   (-30, 30, -30, -30)):
                d2.ksLineSeg(x1, y1, x2, y2, 1)
            sd.EndEdit()
            ext = part.NewEntity(c.o3d_baseExtrusion)
            ed = m.ksBaseExtrusionDefinition(ext.GetDefinition())
            ed.directionType = c.dtBoth
            ed.SetSideParam(True, c.etBlind, 30.0, 0.0, False)
            ed.SetSideParam(False, c.etBlind, 30.0, 0.0, False)
            ed.SetSketch(sk)
            if not ext.Create():
                raise RuntimeError("пробный куб не создан")
            plane = part.GetDefaultEntity(c.o3d_planeYOZ) if abs(alpha) < 1e-9 \
                else self._angle_plane(part, alpha)
            sk2 = part.NewEntity(c.o3d_sketch)
            sd2 = m.ksSketchDefinition(sk2.GetDefinition())
            sd2.SetPlane(plane)
            sk2.Create()
            d3 = sd2.BeginEdit()
            d3.ksCircle(10.0, 0.0, 1.0, 1)
            d3.ksCircle(0.0, 10.0, 2.0, 1)
            sd2.EndEdit()
            cut = part.NewEntity(c.o3d_cutExtrusion)
            cd = m.ksCutExtrusionDefinition(cut.GetDefinition())
            cd.cut = True
            cd.directionType = c.dtBoth
            cd.SetSideParam(True, c.etBlind, 20.0, 0.0, False)
            cd.SetSideParam(False, c.etBlind, 20.0, 0.0, False)
            cd.SetSketch(sk2)
            if not cut.Create():
                raise RuntimeError("пробный вырез не выполнен")

            def wall(direction, r):
                # a point on the wall of a hole of radius r centred 10 mm along
                # direction: off the centre square to the direction, in the plane
                sides = [y_axis] if abs(direction[1]) < 0.5 else [w, w2]
                for side in sides:
                    p = [10.0 * direction[k] + r * side[k] for k in range(3)]
                    faces = part.EntityCollection(c.o3d_face)
                    faces.SelectByPoint(*p)
                    if faces.GetCount() > 0:
                        return True
                return False

            w2 = (-w[0], w[1], w[2])
            cands = [y_axis, tuple(-v for v in y_axis), w, tuple(-v for v in w)]
            if abs(w[0]) > 1e-6:  # the plane may turn either way around Y
                cands += [w2, tuple(-v for v in w2)]
            ex = [v for v in cands if wall(v, 1.0)]
            ey = [v for v in cands if wall(v, 2.0)]
            if len(ex) != 1 or len(ey) != 1:
                raise RuntimeError(f"неоднозначно: x {len(ex)}, y {len(ey)}")
            return ex[0], ey[0]
        finally:
            _close(doc)

    def _plane_sketch(self, part, plane, loops):
        m = self.m
        sketch = part.NewEntity(self.constants.o3d_sketch)
        sdef = m.ksSketchDefinition(sketch.GetDefinition())
        sdef.SetPlane(part.GetDefaultEntity(plane))
        sketch.Create()
        with _editing(sdef) as d2:
            self._draw5(d2, loops)
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

    def _sketch5(self, d2, loops, axis: bool = True):
        for loop in loops:
            for seg in loop:
                if seg[0] == "line":
                    (ax, ay), (bx, by) = seg[1], seg[2]
                    if math.hypot(bx - ax, by - ay) > 1e-6:
                        d2.ksLineSeg(ax, ay, bx, by, 1)
                else:
                    (cx, cy), r, a1, a2 = seg[1], seg[2], seg[3], seg[4]
                    d2.ksArcByAngle(cx, cy, r, a1, a2, 1, 1)
        if axis:
            x0, x1 = self._sketch_extent(loops)
            d2.ksLineSeg(x0 - 5.0, 0.0, x1 + 5.0, 0.0, 3)  # the axis of revolution

    def _sketch7(self, loops, d2, with_axis: bool = True) -> tuple[int, int]:
        """Sketch objects through API7 + constraints that define the sketch
        fully (model3d.sketch_dof): joints, horizontal/vertical lines, tangent
        fillets, then fixed points and lengths for what is still free — each
        only if it is not implied by the others (no over-definition)."""
        from ..model3d.sketch_dof import full_definition

        saved = (self.parametric, self._drawing7)
        self.parametric, self._drawing7 = True, None  # the active document: the sketch
        try:
            x0, x1 = self._sketch_extent(loops)
            axis = ((x0 - 5.0, 0.0), (x1 + 5.0, 0.0)) if with_axis else None
            segments, jobs, left = full_definition(loops, axis)
            objs = []
            for seg in (segments[:-1] if with_axis else segments):
                objs.append(self.line(seg[1], seg[2], 1) if seg[0] == "line"
                            else self._sketch_arc(d2, seg))
            if with_axis:
                objs.append(self.line(axis[0], axis[1], 3))  # the axis of revolution
            if not all(objs):
                raise RuntimeError("не все объекты эскиза созданы")
            made, failed, dims = 0, {}, 0
            for job in jobs:
                b = objs[job.b] if job.b is not None else None
                ok = False
                if job.kind in ("fixed_length", "radius"):
                    # a driving dimension, as a designer sizes a sketch; a
                    # fixed length when KOMPAS takes no dimension here
                    try:
                        ok = self._sketch_dimension(objs[job.a], segments[job.a])
                    except Exception as exc:
                        self._once("sketch_dim", f"  размер в эскизе: {exc!r} — фиксирую длину")
                        ok = False
                    dims += ok
                    if not ok and job.kind == "radius":
                        # no radius dimension: the arc's ends fixed instead
                        ok = all(self.constrain("fixed_point", objs[job.a], None, k, None)
                                 for k in (0, 1))
                    if ok:
                        made += 1
                        continue
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
            if dims:
                self.log(f"  управляющих размеров в эскизе: {dims}")
            if failed:
                self.log("  не наложены: " + ", ".join(f"{k} {v}" for k, v in failed.items()))
            if left:
                self.log(f"  эскиз недоопределён: свободных степеней {left}")
            elif not failed:
                self.log("  по расчёту эскиз полностью определён (степеней свободы 0)")
            return made, len(jobs)
        finally:
            self.parametric, self._drawing7 = saved

    def _new_part(self, log, invisible: bool = False):
        """A new part document. When KOMPAS refuses (code -2 after a long
        session: a sketch left open, test parts piling up), the documents
        nobody sees are closed and it is asked once more."""
        doc3d = self.kompas.Document3D()
        if doc3d.Create(invisible, True):
            return doc3d
        code = self.last_error()
        closed = self._close_hidden_documents()
        log(f"  КОМПАС не создал деталь (код {code}); закрыто невидимых документов: {closed}, "
            "пробую ещё раз")
        doc3d = self.kompas.Document3D()
        if doc3d.Create(invisible, True):
            return doc3d
        raise RuntimeError(
            f"КОМПАС не создаёт новую деталь (код {self.last_error()}). Закройте лишние "
            "документы в КОМПАС или перезапустите его и постройте ещё раз.")

    def _close_hidden_documents(self) -> int:
        closed = 0
        try:
            from win32com.client import gencache

            app = gencache.EnsureDispatch("Kompas.Application.7")
            docs = [app.Documents.Item(i) for i in range(app.Documents.Count)]
            for doc in docs:
                try:
                    if not doc.Visible:
                        doc.Close(getattr(self.constants, "kdDoNotSaveChanges", 0))
                        closed += 1
                except Exception:
                    continue
        except Exception as exc:
            self._once("close_hidden", f"  закрыть невидимые документы: {exc!r}")
        return closed

    def extrude_part(self, loops, thickness: float, path: str, log=None,
                     parametric: bool = True) -> bool:
        """A part made by extruding closed loops (the outline and its through
        cuts) on the XOY plane by ``thickness`` mm along Z."""
        log = log or self.log
        m, c = self.m, self.constants
        doc3d = self._new_part(log)
        self._doc3d = doc3d
        part = doc3d.GetPart(c.pTop_Part)
        sketch = part.NewEntity(c.o3d_sketch)
        sdef = m.ksSketchDefinition(sketch.GetDefinition())
        sdef.SetPlane(part.GetDefaultEntity(c.o3d_planeXOY))
        sketch.Create()
        with _editing(sdef) as d2:
            if not parametric:
                log("Эскиз без параметризации: простые отрезки и дуги")
                self._sketch5(d2, loops, axis=False)
            else:
                try:
                    made, tried = self._sketch7(loops, d2, with_axis=False)
                    log(f"Эскиз через API7: связей и размеров создано {made} из {tried}")
                except Exception as exc:
                    log(f"Эскиз через API7 не удался ({exc!r}) — строю через API5, без связей")
                    self._sketch5(d2, loops, axis=False)
        ext = part.NewEntity(c.o3d_baseExtrusion)
        ed = m.ksBaseExtrusionDefinition(ext.GetDefinition())
        ed.directionType = c.dtNormal
        ed.SetSideParam(True, c.etBlind, float(thickness), 0.0, False)
        ed.SetSketch(sketch)
        if not ext.Create():
            raise RuntimeError(f"Выдавливание не выполнено (код {self.last_error()})")
        log(f"Выдавливание на {thickness:g} мм")
        return bool(doc3d.SaveAs(path))

    def _sketch_dimension(self, obj, seg) -> bool:
        """A driving dimension in the sketch (api_test14/15): a line's length
        (horizontal, vertical or along it) tied to its ends, an arc's radius on
        the arc; made driving by the constraint «фиксированный размер»."""
        from win32com.client import CastTo

        if isinstance(obj, int):
            return False
        c = self.constants
        symbols = CastTo(self._api7_view(), "ISymbols2DContainer")
        if seg[0] == "line":
            (ax, ay), (bx, by) = seg[1], seg[2]
            n = math.hypot(bx - ax, by - ay) or 1.0
            nx, ny = -(by - ay) / n, (bx - ax) / n  # off the line, 3 mm
            dim = symbols.LineDimensions.Add()
            dim.X1, dim.Y1, dim.X2, dim.Y2 = ax, ay, bx, by
            dim.X3, dim.Y3 = (ax + bx) / 2 + 3.0 * nx, (ay + by) / 2 + 3.0 * ny
            if abs(ay - by) < 1e-9:
                dim.Orientation = c.ksLinDHorizontal
            elif abs(ax - bx) < 1e-9:
                dim.Orientation = c.ksLinDVertical
            else:
                dim.Orientation = c.ksLinDParallel
            if not dim.Update():
                return False
            for k in (0, 1):
                if not self.constrain("coincident", dim, obj, k, k):
                    return False
        else:
            (cx, cy), r, a1, a2 = seg[1], seg[2], seg[3], seg[4]
            dim = symbols.RadialDimensions.Add()
            dim.Xc, dim.Yc, dim.Radius = cx, cy, r
            dim.Angle = (a1 + ((a2 - a1) % 360.0) / 2) % 360.0
            CastTo(dim, "IRadialDimension").BaseObject = obj
            if not dim.Update():
                return False
        con = _interface(dim, "IDrawingObject1").NewConstraint()
        con.ConstraintType = c.ksCFixedDim
        return bool(con.Create())

    def table(self, top_left, widths, heights, cells, text_height) -> bool:
        """A KOMPAS table: API7 first, then API5 (ksTable: the table's lines
        and the texts of its cells, each after ksColumnNumber of its cell)."""
        try:
            if self._table7(top_left, widths, heights, cells, text_height):
                return True
            self._once("table7", "  таблица через API7 не обновилась — строю через API5 (ksTable)")
        except Exception as exc:
            self._once("table7", f"  таблица через API7: {exc!r} — строю через API5 (ksTable)")
        return self._table5(top_left, widths, heights, cells, text_height)

    def _table5(self, top_left, widths, heights, cells, text_height) -> bool:
        doc = self.doc
        if not doc.ksTable():
            raise RuntimeError(f"ksTable не начал таблицу (код {self.last_error()})")
        x0, y0 = top_left
        xs = [x0 + sum(widths[:k]) for k in range(len(widths) + 1)]
        ys = [y0 - sum(heights[:k]) for k in range(len(heights) + 1)]
        for y in ys:
            doc.ksLineSeg(xs[0], y, xs[-1], y, 1)
        for x in xs:
            doc.ksLineSeg(x, ys[0], x, ys[-1], 1)
        number = 0
        for r, row in enumerate(cells):  # cells numbered left to right, top to bottom
            for k, value in enumerate(row):
                number += 1
                if not value:
                    continue
                text = value if isinstance(value, str) else "".join(p[0] for p in value)
                h = min(text_height, 0.7 * heights[r])
                doc.ksColumnNumber(number)
                doc.ksText(xs[k] + 1.0, ys[r + 1] + (heights[r] - h) / 2, 0.0, h, 1.0, 0,
                           kompas_text(text))
        ref = doc.ksEndObj()
        return bool(ref[0] if isinstance(ref, tuple) else ref)

    def _table7(self, top_left, widths, heights, cells, text_height) -> bool:
        """A KOMPAS table (API7 IDrawingTables) at ``top_left`` on the sheet:
        column widths, row heights (top first), cell texts — a string, or
        [text, "normal"|"sub"|"sup"] parts for indices. False when KOMPAS
        makes none (the caller then draws its lines and texts)."""
        from win32com.client import CastTo

        rows, cols = len(heights), len(widths)
        view = self._api7_view()
        coll = None
        for iface in ("IDrawingContainer", "ISymbols2DContainer"):
            try:
                coll = CastTo(view, iface).DrawingTables
                break
            except Exception:
                continue
        if coll is None:
            raise NotImplementedError("нет коллекции таблиц (DrawingTables)")
        height, width = sum(heights) / rows, sum(widths) / cols
        table = None
        for args in ((rows, cols, height, width, 0), (rows, cols, height, width)):
            try:
                table = coll.Add(*args)
                break
            except Exception:
                continue
        if table is None:
            raise NotImplementedError("таблица не добавлена")
        table.X, table.Y = top_left
        grid = CastTo(table, "ITable")
        sized = True
        for k, w in enumerate(widths):
            try:
                grid.Cell(0, k).Width = w
            except Exception:
                sized = False
        for k, h in enumerate(heights):
            try:
                grid.Cell(k, 0).Height = h
            except Exception:
                sized = False
        uneven = max(widths) - min(widths) > 0.15 * width or max(heights) - min(heights) > 0.15 * height
        if not sized and uneven:
            try:
                table.Delete()
            except Exception:
                pass
            raise NotImplementedError("размеры колонок таблицы не задаются")
        for r, row in enumerate(cells):
            for k, value in enumerate(row):
                if not value:
                    continue
                text = CastTo(grid.Cell(r, k).Text, "IText")
                parts = value if isinstance(value, list) else [[value, "normal"]]
                line = text.Add()
                for s, kind in index_items([tuple(p) for p in parts]):
                    item = line.Add()
                    item.ItemType = kind
                    item.Str = s
                    try:
                        item.ItemFont.Height = text_height
                    except Exception:
                        pass
                    item.Update()
        return bool(table.Update())

    def model_view(self, source: str, at, scale: float, angle: float = 0.0,
                   projection: str = "#Спереди", hidden: bool = False) -> bool:
        """A view of a saved part, linked to it (the view follows the model):
        the model's origin at ``at`` on the sheet, turned by ``angle``°;
        ``hidden`` shows the hidden edges (bores) dashed. API5 first (the SDK
        example), then API7; the projection's name with and without «#»
        (KOMPAS versions differ)."""
        names = [projection, projection.lstrip("#")] if projection.startswith("#") else [projection]
        # API5 first: the way of the SDK's own example
        for api, make in (("API5", self._model_view5), ("API7", self._model_view7)):
            for name in names:
                try:
                    if make(source, at, scale, angle, name, hidden):
                        self.log(f"  вид модели: {api}, проекция «{name}»")
                        self._model_views = getattr(self, "_model_views", 0) + 1
                        return True
                except Exception as exc:
                    self.log(f"  вид модели через {api} («{name}»): {exc!r}")
        return False

    def model_gabarit(self, source: str):
        """(x1, y1, z1, x2, y2, z2) of a saved part: opened unseen, measured,
        closed."""
        doc = self.kompas.Document3D()
        if not doc.Open(source, True):
            raise RuntimeError(f"КОМПАС не открыл модель {source} (код {self.last_error()})")
        try:
            part = doc.GetPart(self.constants.pTop_Part)
            got = part.GetGabarit(True, True)
            nums = [float(v) for v in (got if isinstance(got, (tuple, list)) else [got])
                    if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if len(nums) < 6:
                raise RuntimeError(f"габарит модели не прочитан: {got!r}")
            return tuple(nums[-6:])
        finally:
            _close(doc)

    def export_mesh(self, source: str, out_stl: str) -> bool:
        """The saved part as an STL mesh (for views drawn by the program).
        Several ways, as KOMPAS versions differ; the file is checked."""
        from pathlib import Path

        out = Path(out_stl)

        def written() -> bool:
            return out.exists() and out.stat().st_size > 84

        doc = self.kompas.Document3D()
        if not doc.Open(source, True):
            raise RuntimeError(f"КОМПАС не открыл модель {source} (код {self.last_error()})")
        try:
            # API5: ksDocument3D.SaveAsToAdditionFormat + ksAdditionFormatParam
            try:
                par = self._param("ko_AdditionFormatParam", "ksAdditionFormatParam")
                par.Init()
                for key, value in (("format", getattr(self.constants, "format_STL", 3)),
                                   ("formatBinary", True), ("angle", 5.0), ("length", 0.05),
                                   ("maxLength", 2.0)):
                    try:
                        setattr(par, key, value)
                    except Exception as exc:
                        self.log(f"    ksAdditionFormatParam.{key}: {exc!r}")
                doc.SaveAsToAdditionFormat(str(out), par)
                if written():
                    self.log("  STL: API5 SaveAsToAdditionFormat")
                    return True
            except Exception as exc:
                self.log(f"  STL через API5 SaveAsToAdditionFormat: {exc!r}")
            # the document saved under an .stl name (KOMPAS picks the format)
            for how in ("SaveAs", "ksSaveDocument"):
                try:
                    getattr(doc, how)(str(out))
                    if written():
                        self.log(f"  STL: API5 {how}")
                        return True
                except Exception as exc:
                    self.log(f"  STL через API5 {how}: {exc!r}")
        finally:
            _close(doc)
        try:  # API7: open unseen, SaveAs with the .stl name
            from win32com.client import gencache

            app = gencache.EnsureDispatch("Kompas.Application.7")
            doc7 = app.Documents.Open(source, False, True)
            try:
                doc7.SaveAs(str(out))
            finally:
                doc7.Close(getattr(self.constants, "kdDoNotSaveChanges", 0))
            if written():
                self.log("  STL: API7 SaveAs")
                return True
        except Exception as exc:
            self.log(f"  STL через API7 SaveAs: {exc!r}")
        return False

    def _model_view7(self, source, at, scale, angle, projection, hidden) -> bool:
        from win32com.client import CastTo, gencache

        app = gencache.EnsureDispatch("Kompas.Application.7")
        doc2d = CastTo(app.ActiveDocument, "IKompasDocument2D")
        view = doc2d.ViewsAndLayersManager.Views.Add(self.constants.vt_Arbitrary)
        assoc = CastTo(view, "IAssociationView")
        assoc.SourceFileName = source
        assoc.ProjectionName = projection
        for key, value in (("HiddenLinesVisible", bool(hidden)), ("TangentEdgesVisible", True),
                           ("VisibleLinesStyle", 1), ("HiddenLinesStyle", 4),
                           ("TangentEdgesStyle", 2)):
            try:
                setattr(assoc, key, value)
            except Exception as exc:
                self.log(f"    IAssociationView.{key}: {exc!r}")
        view.X, view.Y = at
        view.Scale = scale
        view.Angle = angle
        view.Name = "Модель"
        ok = bool(view.Update())
        if not ok:
            try:
                view.Delete()
            except Exception:
                pass
        self._drawing7 = None
        return ok

    def _model_view5(self, source, at, scale, angle, projection, hidden) -> bool:
        """API5 as the KOMPAS SDK's own example does it: the file, the
        projection and how its lines are drawn on ksAssociationViewParam; the
        place, scale and name on ITS view parameters (GetViewParam) — set on
        the association parameters themselves (as before) they were refused
        or lost, and the view came out empty. Line styles given: left at 0,
        the edges are drawn in no style at all."""
        par = self._param("ko_AssociationViewParam", "ksAssociationViewParam")
        par.Init()
        for key, value in (("disassembly", False), ("fileName", source),
                           ("hiddenLinesShow", bool(hidden)), ("projectionLink", False),
                           ("projectionName", projection), ("scale_", scale), ("section", False),
                           ("sameHatch", True), ("tangentEdgesShow", True),
                           ("visibleLinesStyle", 1), ("hiddenLinesStyle", 4),
                           ("tangentEdgesStyle", 2)):
            try:
                setattr(par, key, value)
            except Exception as exc:
                self.log(f"    ksAssociationViewParam.{key}: {exc!r}")
        view = self._sub("ksViewParam", par.GetViewParam())
        view.Init()
        view.angle, view.color, view.name, view.scale_ = angle, 0, "Модель", scale
        view.state = 3  # the current view, open for its contents
        view.x, view.y = at
        ref = self.doc.ksCreateSheetArbitraryView(par, 0)
        number = ref[0] if isinstance(ref, tuple) else ref
        self._drawing7 = None
        if not number:
            self.log(f"    ksCreateSheetArbitraryView: 0 (код {self.last_error()})")
        return bool(number)

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


def _vec(v) -> str:
    names = ("X", "Y", "Z")
    parts = [f"{'-' if x < 0 else '+'}{abs(x):.2f}{n}" for x, n in zip(v, names) if abs(x) > 1e-6]
    return "".join(parts).lstrip("+") or "0"


def _map_loop(loop, f):
    """Segments through the linear map f of the plane (arcs turned so they
    still run counter-clockwise when f mirrors)."""
    a, b = f((1.0, 0.0)), f((0.0, 1.0))
    mirrored = a[0] * b[1] - a[1] * b[0] < 0
    out = []
    for seg in loop:
        if seg[0] == "line":
            out.append(("line", f(seg[1]), f(seg[2])))
            continue
        (cx, cy), r, a1, a2 = seg[1], seg[2], seg[3], seg[4]
        c = f((cx, cy))

        def ang(t):
            p = f((cx + math.cos(math.radians(t)), cy + math.sin(math.radians(t))))
            return math.degrees(math.atan2(p[1] - c[1], p[0] - c[0])) % 360.0

        b1, b2 = ang(a1), ang(a2)
        out.append(("arc", c, r, b2, b1) if mirrored else ("arc", c, r, b1, b2))
    return out


def _hole_geometry(flange, h):
    """(alpha, point, reach) of an angled hole: the plane angle to YOZ around
    the Y axis (degrees), the point of the hole's axis on that plane through
    the origin (X, Y, Z) and how far the cut must reach both ways."""
    beta = math.radians(h.tilt)
    s = -float(h.into)  # +1: from the face at x1 towards x0
    dx, dz = -s * math.cos(beta), h.mv * math.sin(beta)
    x_face = flange.x1 if h.into < 0 else flange.x0
    alpha = math.atan2(-dz, dx)  # plane normal (cos α, 0, −sin α) along the hole
    if math.cos(alpha) < 0:
        alpha = math.atan2(dz, -dx)
    t = x_face * dx + h.v * dz
    point = (x_face - t * dx, h.u, h.v - t * dz)
    # the hole: from the face (t) to where it leaves the flats, and a margin
    sb = max(math.sin(beta), 1e-6)
    length = max(0.5, (flange.inner - abs(h.v)) / sb)
    # the hole's far side leaves the flat r/tan β further, and leaves room
    margin = h.radius * (1.0 / sb + math.cos(beta) / sb) + 1.0
    reach = max(abs(t), abs(t + length)) + margin
    return math.degrees(alpha), point, reach, (dx, 0.0, dz)


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


def _axes_file():
    import os
    from pathlib import Path

    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "KompasAI" / "plane_axes.json"


def _known_axes() -> dict:
    """Sketch axes of KOMPAS planes found on test parts by earlier runs: the
    same on every run of this KOMPAS, so each is probed once per computer."""
    import json

    try:
        return json.loads(_axes_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remember_axes(key: str, found) -> None:
    import json

    data = _known_axes()
    data[key] = [list(v) for v in found]
    try:
        path = _axes_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


class _editing:
    """``with _editing(sdef) as d2:`` — a sketch edited and always closed: a
    sketch left open after an error kept KOMPAS from making new parts."""

    def __init__(self, sdef):
        self.sdef = sdef

    def __enter__(self):
        return self.sdef.BeginEdit()

    def __exit__(self, *exc):
        try:
            self.sdef.EndEdit()
        except Exception:
            pass
        return False


def _close(doc) -> None:
    """Close an API5 document (its method is spelled differently by versions)."""
    for name in ("close", "Close", "ksCloseDocument"):
        try:
            getattr(doc, name)()
            return
        except Exception:
            continue
