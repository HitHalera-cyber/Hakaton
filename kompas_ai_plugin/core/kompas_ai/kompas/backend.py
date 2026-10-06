"""What the writer needs from KOMPAS, as a small interface.

The writer (IR → drawing commands) only talks to a :class:`Backend`. The real
implementation, :class:`~kompas_ai.kompas.api5.Api5Backend`, calls KOMPAS
through COM; tests use a recording fake. All coordinates are in the units of
the current drawing space (sheet mm in sheet mode, model mm inside a view).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

Point = tuple[float, float]

# KOMPAS system line styles.
STYLE_IDS = {"main": 1, "thin": 2, "axial": 3, "dashed": 4}

# ksDimSourceParam.ps
LINEAR_PARALLEL, LINEAR_VERTICAL, LINEAR_HORIZONTAL = 0, 1, 2


@dataclass
class DimText:
    """Dimension text: ``auto`` lets KOMPAS write the measured value;
    otherwise ``value`` is written as is. ``diameter_sign`` adds Ø."""

    auto: bool
    value: str = ""
    diameter_sign: bool = False


class Backend(Protocol):
    def new_sheet(self, format_index: int, landscape: bool) -> None: ...

    def open_view(self, origin: Point, scale: float, name: str) -> bool:
        """Create a view and make it current; False if KOMPAS refuses."""
        ...

    def line(self, p1: Point, p2: Point, style: int) -> int: ...

    def circle(self, center: Point, radius: float, style: int) -> int: ...

    def arc(self, center: Point, radius: float, start: float, end: float, style: int) -> int:
        """Counter-clockwise arc from ``start`` to ``end`` degrees."""
        ...

    def point(self, p: Point) -> int: ...

    def text(self, p: Point, value: str, height: float, angle: float) -> int: ...

    def linear_dim(self, p1: Point, p2: Point, offset: Point, kind: int, text: DimText) -> int: ...

    def radial_dim(self, center: Point, radius: float, angle: float, diameter: bool,
                   text: DimText) -> int: ...

    def angular_dim(self, center: Point, start: float, end: float, radius: float,
                    text: DimText) -> int: ...

    def hatch(self, contours: list[list[Point]], angle: float, step: float) -> int: ...

    def save(self, path: str) -> bool: ...
