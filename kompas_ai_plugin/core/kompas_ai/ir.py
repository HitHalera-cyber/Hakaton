"""Drawing IR — the intermediate representation shared by all modules.

The recognition core produces a :class:`Drawing`; the KOMPAS writer (and the
DXF exporter, the preview, the evaluator) only consume it. Changing the
recognition algorithms therefore never touches the KOMPAS integration.

Coordinates are **sheet millimetres** with the origin in the bottom-left
corner of the sheet and Y pointing up — the same system KOMPAS uses for a
drawing sheet. Model (real part) size = sheet size / ``Drawing.scale.value``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

Point = tuple[float, float]

# Line styles, named after the KOMPAS system styles they map to.
STYLE_MAIN = "main"  # основная
STYLE_THIN = "thin"  # тонкая
STYLE_AXIAL = "axial"  # осевая
STYLE_DASHED = "dashed"  # штриховая

REVIEW_THRESHOLD = 0.8


@dataclass
class Entity:
    id: str
    confidence: float = 1.0
    notes: list[str] = field(default_factory=list)

    @property
    def kind(self) -> str:
        return type(self).__name__.lower()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.kind
        return data


@dataclass
class Line(Entity):
    p1: Point = (0.0, 0.0)
    p2: Point = (0.0, 0.0)
    style: str = STYLE_MAIN


@dataclass
class Circle(Entity):
    center: Point = (0.0, 0.0)
    radius: float = 0.0
    style: str = STYLE_MAIN


@dataclass
class Arc(Entity):
    """Counter-clockwise arc from ``start_angle`` to ``end_angle`` (degrees)."""

    center: Point = (0.0, 0.0)
    radius: float = 0.0
    start_angle: float = 0.0
    end_angle: float = 0.0
    style: str = STYLE_MAIN


@dataclass
class PointMark(Entity):
    position: Point = (0.0, 0.0)


@dataclass
class Text(Entity):
    text: str = ""
    position: Point = (0.0, 0.0)  # baseline start
    height: float = 3.5
    angle: float = 0.0  # degrees, CCW from +X
    # Text with indices: [text, kind, x, y, height] per part, kind normal|sub|sup.
    parts: list | None = None


@dataclass
class Hatch(Entity):
    """Hatched region bounded by ``contours`` (first = outer, others = holes)."""

    angle: float = 45.0
    spacing: float = 2.0
    contours: list[list[Point]] = field(default_factory=list)  # empty = boundary not found
    line_count: int = 0


@dataclass
class Dimension(Entity):
    """A dimension as drawn on the sheet.

    ``dim_type``: linear | diameter | radius | angular.
    For linear dims ``p1``/``p2`` are the measured points and ``line_point`` a
    point of the dimension line. ``measured`` is in sheet mm (degrees for
    angular); ``nominal`` is the value written on the drawing.
    """

    dim_type: str = "linear"
    text: str = ""
    nominal: float | None = None
    measured: float | None = None
    p1: Point | None = None
    p2: Point | None = None
    line_point: Point | None = None
    center: Point | None = None
    radius: float | None = None
    orientation: str = "aligned"  # horizontal | vertical | aligned
    ref: str | None = None  # id of the measured entity (circle/arc), if known
    text_id: str | None = None


@dataclass
class Constraint:
    type: str  # coincident | horizontal | vertical | parallel | perpendicular | concentric | tangent
    a: str
    b: str | None = None


@dataclass
class Scale:
    value: float = 1.0  # sheet / model, e.g. 5.0 for "5:1"
    text: str = "1:1"
    source: str = "default"  # title_block | dimensions | default
    dimension_estimate: float | None = None
    conflicts: list[str] = field(default_factory=list)


@dataclass
class Sheet:
    format: str = "A4"
    orientation: str = "portrait"
    width: float = 210.0
    height: float = 297.0
    frame_found: bool = False
    offset: Point = (0.0, 0.0)  # PDF->sheet translation applied to everything
    title_block: dict[str, str] = field(default_factory=dict)


@dataclass
class Drawing:
    source: str = ""
    sheet: Sheet = field(default_factory=Sheet)
    scale: Scale = field(default_factory=Scale)
    entities: list[Entity] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    processing: list[str] = field(default_factory=list)  # what was corrected and how

    def of_type(self, cls: type) -> list:
        return [e for e in self.entities if isinstance(e, cls)]

    def get(self, entity_id: str) -> Entity | None:
        return next((e for e in self.entities if e.id == entity_id), None)

    @property
    def review(self) -> list[Entity]:
        return [e for e in self.entities if e.confidence < REVIEW_THRESHOLD]

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entities:
            counts[e.kind] = counts.get(e.kind, 0) + 1
        counts["review"] = len(self.review)
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "sheet": asdict(self.sheet),
            "scale": asdict(self.scale),
            "summary": self.summary(),
            "review": [e.id for e in self.review],
            "warnings": self.warnings,
            "processing": self.processing,
            "entities": [e.to_dict() for e in self.entities],
            "constraints": [asdict(c) for c in self.constraints],
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                              encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Drawing":
        kinds = {c.__name__.lower(): c for c in ENTITY_TYPES}
        entities = []
        for raw in data.get("entities", []):
            raw = dict(raw)
            entity_cls = kinds[raw.pop("type")]
            entities.append(entity_cls(**{k: _tuples(v) for k, v in raw.items()}))
        sheet = dict(data.get("sheet", {}))
        sheet["offset"] = tuple(sheet.get("offset", (0.0, 0.0)))
        return cls(
            source=data.get("source", ""),
            sheet=Sheet(**sheet),
            scale=Scale(**data.get("scale", {})),
            entities=entities,
            constraints=[Constraint(**c) for c in data.get("constraints", [])],
            warnings=list(data.get("warnings", [])),
            processing=list(data.get("processing", [])),
        )

    @classmethod
    def load_json(cls, path: str | Path) -> "Drawing":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


ENTITY_TYPES = (Line, Circle, Arc, PointMark, Text, Hatch, Dimension)


def _tuples(value):
    """JSON turns tuples into lists; points are restored as tuples."""
    if isinstance(value, list):
        if len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
            return (float(value[0]), float(value[1]))
        return [_tuples(v) for v in value]
    return value
