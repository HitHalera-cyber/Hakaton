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

from .backend import DimText, Point

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

    def __init__(self, visible: bool = True, log=print):
        _prepare_win32com()
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
            item.str = text.value
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
        return self.doc.ksLineSeg(p1[0], p1[1], p2[0], p2[1], style)

    def circle(self, center, radius, style):
        return self.doc.ksCircle(center[0], center[1], radius, style)

    def arc(self, center, radius, start, end, style):
        return self.doc.ksArcByAngle(center[0], center[1], radius, start, end, 1, style)

    def point(self, p):
        return self.doc.ksPoint(p[0], p[1], 0)

    def text(self, p, value, height, angle):
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

    def _api7_drawing(self):
        if self._drawing7 is None:
            from win32com.client import CastTo, gencache

            app = gencache.EnsureDispatch("Kompas.Application.7")
            doc2d = CastTo(app.ActiveDocument, "IKompasDocument2D")
            view = doc2d.ViewsAndLayersManager.Views.ActiveView
            self._drawing7 = CastTo(view, "IDrawingContainer")
        return self._drawing7

    def linear_dim(self, p1, p2, offset, kind, text):
        par = self._param("ko_LDimParam", "ksLDimParam")
        src = self._sub("ksLDimSourceParam", par.GetSPar())
        src.Init()
        src.x1, src.y1, src.x2, src.y2 = p1[0], p1[1], p2[0], p2[1]
        src.dx, src.dy = offset
        src.basePoint, src.ps = 1, kind
        self._sub("ksDimDrawingParam", par.GetDPar()).Init()
        self._set_text(self._sub("ksDimTextParam", par.GetTPar()), text)
        return self.doc.ksLinDimension(par)

    def radial_dim(self, center, radius, angle, diameter, text):
        par = self._param("ko_RDimParam", "ksRDimParam")
        src = self._sub("ksRDimSourceParam", par.GetSPar())
        src.Init()
        src.xc, src.yc, src.rad = center[0], center[1], radius
        drw = self._sub("ksRDimDrawingParam", par.GetDPar())
        drw.Init()
        drw.ang = angle
        self._set_text(self._sub("ksDimTextParam", par.GetTPar()), text)
        method = self.doc.ksDiamDimension if diameter else self.doc.ksRadDimension
        return method(par)

    def angular_dim(self, center, start, end, radius, text):
        par = self._param("ko_ADimParam", "ksADimParam")
        src = self._sub("ksADimSourceParam", par.GetSPar())
        src.Init()
        src.xc, src.yc, src.ang1, src.ang2, src.rad, src.dir = \
            center[0], center[1], start, end, radius, 1
        self._sub("ksDimDrawingParam", par.GetDPar()).Init()
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
