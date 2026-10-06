"""Vector PDF → Drawing IR.

Stages (each in its own module):
  1. extract raw strokes, fills and texts           pdf.vector_extractor
  2. sheet format, origin, frame, title block       semantics.sheet
  3. chords → chains → lines / arcs / circles       geometry.chains, geometry.segmentation
  4. arrowheads                                     semantics.arrows
  5. hatching, dash-patterned lines                 semantics.hatch, geometry.linetypes
  6. dimensions and the scale check                 semantics.dimensions, geometry.scaling
  7. hatch boundaries, constraints, confidences     semantics.regions, geometry.constraints
"""

from __future__ import annotations

import math
from pathlib import Path

from . import ir
from .geometry.chains import build_chains
from .geometry.constraints import find_constraints
from .geometry.linetypes import merge_dashed
from .geometry.scaling import check_dimension, resolve_scale, scale_text, snap_scale
from .geometry.segmentation import Primitive, merge_cocircular, segment_chain
from .pdf.vector_extractor import extract_page
from .semantics.arrows import arrows_from_chains, find_arrows, merge_arrow_sources
from .semantics.axes import mark_axis_lines
from .semantics.dimensions import FoundDimension, find_dimensions, parse_dim_text
from .semantics.hatch import detect_hatches
from .semantics.regions import hatch_regions
from .semantics.sheet import analyse_sheet, is_title_block_text, read_title_block


def recognize_pdf(pdf_path: str | Path, page: int = 0) -> ir.Drawing:
    content = extract_page(pdf_path, page)
    drawing = ir.Drawing(source=str(pdf_path))
    if not content.is_vector:
        drawing.warnings.append(
            "Страница не содержит векторной геометрии (скан или изображение). "
            "Растровое распознавание будет добавлено на этапе 2.")
        return drawing

    layout = analyse_sheet(content)
    drawing.sheet = layout.sheet
    title_scale = read_title_block(content, layout)

    chains = build_chains(content.segments)
    outline_arrows, chains = arrows_from_chains(chains)
    arrows = merge_arrow_sources(outline_arrows, find_arrows(content.fills))

    prims = merge_cocircular([p for chain in chains for p in segment_chain(chain)])
    prims = [p for p in prims if not layout.is_sheet_graphic(p.points)]
    widths = sorted({round(p.width, 3) for p in prims})
    thin_w = widths[0] if len(widths) > 1 else -1.0  # one width only: everything is main

    def is_thin(p: Primitive) -> bool:
        return abs(round(p.width, 3) - thin_w) < 1e-6

    hatch_groups, _ = detect_hatches([p for p in prims if is_thin(p) and p.kind == "line"])
    hatch_ids = {id(l) for g in hatch_groups for l in g.lines}
    prims = [p for p in prims if id(p) not in hatch_ids]
    if thin_w > 0:
        prims = merge_dashed(prims, thin_w)

    # Dimensions
    texts = [t for t in content.texts if not is_title_block_text(t, layout)]
    dim_texts, plain_texts = [], []
    for t in texts:
        parsed = parse_dim_text(t)
        (dim_texts if parsed else plain_texts).append(parsed or t)
    thin_free = [p for p in prims if is_thin(p) and not p.tags & {"axial", "dashed"}]
    main_curves = [p for p in prims if not is_thin(p) and p.kind in ("circle", "arc")]
    axes = [p for p in prims if "axial" in p.tags]
    found = find_dimensions(dim_texts, arrows, thin_free, main_curves, axes)
    used = {id(p) for d in found for p in d.used}
    matched_texts = {id(d.text) for d in found}
    suspicious: set[int] = set()
    for dt in dim_texts:
        if id(dt) not in matched_texts:
            plain_texts.append(dt.raw)
            # Numbers on graph axes and in tables are plain text; only a number
            # with arrowheads around it is a dimension that was not assembled.
            reach = 4 * dt.raw.height + 10.0
            # Single digits next to arrows are usually labels of vectors or
            # positions (u₂, 1, 2…), not dimension values.
            looks_like_value = dt.prefix or dt.angular or dt.decimals or dt.value >= 10
            if looks_like_value and any(math.dist(a.tip, dt.center) <= reach for a in arrows):
                suspicious.add(id(dt.raw))
                drawing.warnings.append(
                    f"Текст «{dt.raw.text}» похож на размер (рядом стрелки), "
                    "но размерная линия не найдена — добавлен как текст.")

    ratios = [d.measured / d.text.value for d in found
              if d.dim_type != "angular" and d.text.value > 0]
    drawing.scale = resolve_scale(title_scale, ratios)
    drawing.warnings.extend(drawing.scale.conflicts)

    geometry = [p for p in prims if id(p) not in used]
    contour = [p for p in geometry if not is_thin(p)]
    mark_axis_lines([p for p in geometry if is_thin(p)], contour)
    regions, orphan_groups = hatch_regions(hatch_groups, contour)

    _build_entities(drawing, geometry, is_thin, found, plain_texts, regions, orphan_groups,
                    suspicious)
    drawing.constraints = find_constraints(drawing.entities)
    if content.unknown_symbols:
        drawing.warnings.append(
            "Неизвестные символы шрифта: " + " ".join(sorted(content.unknown_symbols)))
    return drawing


def _build_entities(drawing, geometry, is_thin, found, plain_texts, regions, orphan_groups,
                    suspicious=frozenset()):
    counters: dict[str, int] = {}

    def new_id(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}{counters[prefix]}"

    ref_ids: dict[int, str] = {}
    for p in sorted(geometry, key=lambda p: (p.kind, -p.length)):
        style = ir.STYLE_AXIAL if "axial" in p.tags else ir.STYLE_DASHED if "dashed" in p.tags \
            else ir.STYLE_THIN if is_thin(p) else ir.STYLE_MAIN
        conf, notes = _geometry_confidence(p)
        if p.kind == "line":
            e = ir.Line(new_id("L"), conf, notes, p1=_r(p.p1), p2=_r(p.p2), style=style)
        elif p.kind == "circle":
            e = ir.Circle(new_id("C"), conf, notes, center=_r(p.center), radius=round(p.radius, 4),
                          style=style)
        else:
            e = ir.Arc(new_id("A"), conf, notes, center=_r(p.center), radius=round(p.radius, 4),
                       start_angle=round(p.start_angle, 3), end_angle=round(p.end_angle, 3),
                       style=style)
        ref_ids[id(p)] = e.id
        drawing.entities.append(e)

    for d in found:
        drawing.entities.append(_dimension_entity(d, new_id("D"), ref_ids, drawing.scale.value))

    for t in plain_texts:
        conf, notes = (0.6, ["Похоже на размер, но собран как текст"]) if id(t) in suspicious \
            else (0.9, [])
        drawing.entities.append(ir.Text(new_id("T"), conf, notes, text=t.text,
                                        position=_r(t.origin), height=t.height, angle=t.angle))

    for region in regions:
        drawing.entities.append(ir.Hatch(new_id("H"), 0.9, [], angle=round(region.angle, 2),
                                         spacing=round(region.spacing, 3),
                                         contours=region.contours(), line_count=region.line_count))
    for g in orphan_groups:
        drawing.entities.append(ir.Hatch(
            new_id("H"), 0.5, ["Граница штриховки не найдена"], angle=round(g.angle, 2),
            spacing=round(g.spacing, 3), contours=[], line_count=len(g.lines)))


def _geometry_confidence(p: Primitive) -> tuple[float, list[str]]:
    notes: list[str] = []
    conf = 0.97
    if p.kind == "line" and p.length < (1.0 if p.width < 0.3 else 0.5):
        conf, notes = 0.6, ["Очень короткий отрезок — возможно, артефакт"]
    elif p.kind in ("circle", "arc") and p.error > 0.06:
        conf = 0.85
        notes.append(f"Отклонение точек от окружности {p.error:.3f} мм")
    if p.kind == "arc" and "axial" in p.tags:
        conf = min(conf, 0.85)
        notes.append("Штрихпунктирная дуга собрана из штрихов")
    return conf, notes


def _dimension_entity(d: FoundDimension, dim_id: str, ref_ids, scale: float) -> ir.Dimension:
    check = check_dimension(d.dim_type, d.measured, d.text.value, d.text.decimals, scale)
    notes = []
    conf = 0.95 if d.tips >= 2 else 0.8
    unit = "°" if d.dim_type == "angular" else " мм"
    if not check.ok:
        other = _other_view_scale(d, scale)
        if other:
            conf = 0.85
            notes.append(f"Размер соответствует масштабу {other} — видимо, вид в другом масштабе")
        else:
            conf = 0.6
            notes.append(f"Надпись {d.text.raw.text}, а по геометрии {check.model_value:.3f}{unit} "
                         f"(расхождение {check.deviation:+.3f}{unit})")
    return ir.Dimension(
        dim_id, conf, notes, dim_type=d.dim_type, text=d.text.raw.text, nominal=d.text.value,
        measured=round(d.measured, 4), p1=_r(d.p1), p2=_r(d.p2), line_point=_r(d.line_point),
        center=_r(d.center), radius=round(d.radius, 4) if d.radius else None,
        orientation=d.orientation, ref=ref_ids.get(id(d.ref)) if d.ref is not None else None)


def _other_view_scale(d: FoundDimension, sheet_scale: float) -> str | None:
    """Scale text (e.g. "3:1") if the dimension fits another standard scale exactly."""
    if d.dim_type == "angular" or not d.text.value:
        return None
    ratio = d.measured / d.text.value
    snapped = snap_scale(ratio)
    if snapped == ratio or abs(snapped - sheet_scale) < 1e-9:
        return None
    if check_dimension(d.dim_type, d.measured, d.text.value, d.text.decimals, snapped).ok:
        return scale_text(snapped)
    return None


def _r(p):
    return None if p is None else (round(float(p[0]), 4), round(float(p[1]), 4))
