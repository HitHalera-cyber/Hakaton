"""Write a Drawing IR to DXF.

DXF is the fallback route into KOMPAS (Файл → Открыть) and a way to look at
the result in any CAD viewer. Coordinates are written in sheet millimetres,
as in the IR.
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf

from .. import ir

LAYERS = {
    ir.STYLE_MAIN: ("MAIN", 7, "CONTINUOUS", 50),
    ir.STYLE_THIN: ("THIN", 8, "CONTINUOUS", 18),
    ir.STYLE_AXIAL: ("AXIAL", 1, "CENTER", 18),
    ir.STYLE_DASHED: ("DASHED", 5, "DASHED", 18),
    "dim": ("DIMENSIONS", 3, "CONTINUOUS", 18),
    "text": ("TEXT", 7, "CONTINUOUS", 18),
    "hatch": ("HATCH", 8, "CONTINUOUS", 18),
    "review": ("REVIEW", 6, "CONTINUOUS", 18),
}


def _layer(style: str) -> str:
    return LAYERS.get(style, LAYERS[ir.STYLE_MAIN])[0]


def write_dxf(drawing: ir.Drawing, path: str | Path) -> None:
    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.MM
    for name, color, linetype, lw in LAYERS.values():
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=linetype, lineweight=lw)
    msp = doc.modelspace()
    for e in drawing.entities:
        if isinstance(e, ir.Line):
            msp.add_line(e.p1, e.p2, dxfattribs={"layer": _layer(e.style)})
        elif isinstance(e, ir.Circle):
            msp.add_circle(e.center, e.radius, dxfattribs={"layer": _layer(e.style)})
        elif isinstance(e, ir.Ellipse):
            t = math.radians(e.angle)
            msp.add_ellipse(e.center, major_axis=(e.a * math.cos(t), e.a * math.sin(t)),
                            ratio=e.b / e.a, dxfattribs={"layer": _layer(e.style)})
        elif isinstance(e, ir.Arc):
            msp.add_arc(e.center, e.radius, e.start_angle, e.end_angle,
                        dxfattribs={"layer": _layer(e.style)})
        elif isinstance(e, ir.Text):
            for text, _, x, y, h in (e.parts or [(e.text, "normal", *e.position, e.height)]):
                msp.add_text(text, height=h, rotation=e.angle,
                             dxfattribs={"layer": "TEXT", "insert": (x, y)})
        elif isinstance(e, ir.Hatch) and e.contours:
            hatch = msp.add_hatch(dxfattribs={"layer": "HATCH"})
            hatch.set_pattern_fill("ANSI31", scale=e.spacing / 3.175, angle=e.angle - 45.0)
            for i, ring in enumerate(e.contours):
                hatch.paths.add_polyline_path(ring, is_closed=True,
                                              flags=1 if i == 0 else 0)
        elif isinstance(e, ir.Dimension):
            _add_dimension(msp, e, drawing.scale.value)
    doc.saveas(str(path))


def _dim_text(e: ir.Dimension) -> str:
    return e.text.replace("Ø", "%%c").replace("°", "%%d")


def _add_dimension(msp, e: ir.Dimension, scale: float) -> None:
    attribs = {"layer": "DIMENSIONS"}
    override = {"dimtxt": 3.5, "dimasz": 3.0}
    try:
        if e.dim_type == "linear" and e.p1 and e.p2:
            angle = {"horizontal": 0.0, "vertical": 90.0}.get(
                e.orientation, math.degrees(math.atan2(e.p2[1] - e.p1[1], e.p2[0] - e.p1[0])))
            base = e.line_point or e.p1
            dim = msp.add_linear_dim(base=base, p1=e.p1, p2=e.p2, angle=angle, text=_dim_text(e),
                                     dxfattribs=attribs, override=override)
        elif e.dim_type in ("diameter", "radius") and e.center and e.radius:
            angle = math.degrees(math.atan2(e.p1[1] - e.center[1], e.p1[0] - e.center[0])) \
                if e.p1 else 45.0
            add = msp.add_diameter_dim if e.dim_type == "diameter" else msp.add_radius_dim
            dim = add(center=e.center, radius=e.radius, angle=angle, text=_dim_text(e),
                      dxfattribs=attribs, override=override)
        elif e.dim_type == "angular" and e.center and e.p1 and e.p2:
            start, end = _polar(e.center, e.p1), _polar(e.center, e.p2)
            if (end - start) % 360.0 > 180.0:  # measure the angle, not its complement
                start, end = end, start
            dim = msp.add_angular_dim_cra(center=e.center, radius=e.radius or 20.0,
                                          start_angle=start, end_angle=end,
                                          distance=0.0, text=_dim_text(e),
                                          dxfattribs=attribs, override=override)
        else:
            return
        dim.render()
    except Exception:  # a dimension that ezdxf cannot build is written as text
        pos = e.line_point or e.p1 or e.center or (0.0, 0.0)
        msp.add_text(e.text, height=3.5, dxfattribs={"layer": "REVIEW", "insert": pos})


def _polar(center, p) -> float:
    a = math.degrees(math.atan2(p[1] - center[1], p[0] - center[0])) % 360.0
    return a

