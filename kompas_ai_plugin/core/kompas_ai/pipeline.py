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
from .geometry.ellipses import chord_fillets, chords_to_arcs, merge_ellipses
from .geometry.linetypes import merge_dashed
from .geometry.regularize import regularize, snap_annotations, solve_contour
from .geometry.rules import check as check_rules
from .geometry.scaling import check_dimension, resolve_scale, scale_text, snap_scale
from .geometry.segmentation import Primitive, merge_cocircular, segment_chain, snap_concentric
from .pdf.vector_extractor import extract_page
from .semantics.arrows import arrows_from_chains, find_arrows, merge_arrow_sources
from .semantics.axes import mark_axis_lines
from .semantics.dimensions import (FoundDimension, attach_deviations, find_dimensions,
                                   parse_dim_text)
from .semantics.hatch import detect_hatches
from .semantics.regions import hatch_regions
from .semantics.sheet import analyse_sheet, is_title_block_text, read_title_block


# what recognize_pdf reports through ``progress``, in this order
STAGES = ["Читаю PDF", "Рамка и основная надпись", "Линии, дуги и стрелки", "Размеры",
          "Контур и штриховки", "Выравниваю по размерам", "Замыкаю контур",
          "Привязываю размеры"]


def recognize_pdf(pdf_path: str | Path, page: int = 0, exact: bool = True,
                  progress=None) -> ir.Drawing:
    """Recognise one PDF page. ``exact`` corrects the geometry to the written
    dimensions (see geometry/regularize.py); False keeps the measured PDF values.
    ``progress(stage)`` is called with each of STAGES as it starts."""
    step = progress or (lambda stage: None)
    step(STAGES[0])
    content = extract_page(pdf_path, page)
    drawing = ir.Drawing(source=str(pdf_path))
    if not content.is_vector:
        drawing.warnings.append(
            "Страница не содержит векторной геометрии (скан или изображение). "
            "Растровое распознавание будет добавлено на этапе 2.")
        return drawing

    if not content.texts:
        drawing.warnings.append(
            "В PDF нет текстового слоя: надписи и числа размеров нарисованы линиями. "
            "Геометрия распознана, но размеры, масштаб и тексты — нет (масштаб принят 1:1). "
            "Если возможно, сохраните PDF заново с выводом текста как текста (шрифты TrueType, "
            "без «текст в кривые»).")
    step(STAGES[1])
    layout = analyse_sheet(content)
    drawing.sheet = layout.sheet
    title_scale = read_title_block(content, layout)

    step(STAGES[2])
    chains = build_chains(content.segments)
    outline_arrows, chains = arrows_from_chains(chains)
    arrows = merge_arrow_sources(outline_arrows, find_arrows(content.fills))

    prims = snap_concentric(merge_cocircular([p for chain in chains for p in segment_chain(chain)]))
    prims = [p for p in prims if not layout.is_sheet_graphic(p.points)]
    widths = sorted({round(p.width, 3) for p in prims})
    thin_w = widths[0] if len(widths) > 1 else -1.0  # one width only: everything is main

    def is_thin(p: Primitive) -> bool:
        return abs(round(p.width, 3) - thin_w) < 1e-6

    # A thin line with an arrowhead at its end is a dimension or leader line,
    # never a hatch stroke (even when it runs at the hatch angle).
    hatch_candidates = [p for p in prims if is_thin(p) and p.kind == "line"
                        and not _ends_in_arrow(p, arrows)]
    hatch_groups, _ = detect_hatches(hatch_candidates)
    hatch_ids = {id(l) for g in hatch_groups for l in g.lines}
    prims = [p for p in prims if id(p) not in hatch_ids]
    if thin_w > 0:
        prims = merge_dashed(prims, thin_w, [(a.tip, a.direction) for a in arrows])

    # Dimensions
    texts = [t for t in content.texts if not is_title_block_text(t, layout)]
    dim_texts, plain_texts = [], []
    for t in texts:
        parsed = parse_dim_text(t)
        (dim_texts if parsed else plain_texts).append(parsed or t)
    thin_free = [p for p in prims if is_thin(p) and not p.tags & {"axial", "dashed"}]
    main_curves = [p for p in prims if not is_thin(p) and p.kind in ("circle", "arc")]
    axes = [p for p in prims if "axial" in p.tags]
    main_lines = [p for p in prims if not is_thin(p) and p.kind == "line"]
    step(STAGES[3])
    found = find_dimensions(dim_texts, arrows, thin_free, main_curves, axes, main_lines)
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
    plain_texts = attach_deviations(found, plain_texts)

    ratios = [d.measured / d.text.value for d in found
              if d.dim_type != "angular" and d.text.value > 0]
    drawing.scale = resolve_scale(title_scale, ratios)
    drawing.warnings.extend(drawing.scale.conflicts)

    step(STAGES[4])
    geometry = [p for p in prims if id(p) not in used]
    contour = [p for p in geometry if not is_thin(p)]
    mark_axis_lines([p for p in geometry if is_thin(p)], contour)
    regions, orphan_groups = hatch_regions(hatch_groups, contour)

    _build_entities(drawing, geometry, is_thin, found, plain_texts, regions, orphan_groups,
                    suspicious)
    implied = implied_diameters(drawing)
    if implied:
        drawing.warnings.append(
            "Знак Ø не поставлен, но размер стоит поперёк оси симметрично — понят как диаметр: "
            + ", ".join(implied))
    if exact:
        step(STAGES[5])
        drawing.processing.append(regularize(drawing).text())
        step(STAGES[6])
        solved = solve_contour(drawing)
        drawing.processing.append(
            f"Контур решён как система: узлов {solved.get('nodes', 0)}, направлений задано "
            f"{solved.get('directions', 0)}, наибольший сдвиг {solved.get('moved', 0.0):.3f} мм")
        rebuilt = _rebuild_hatches(drawing)
        if rebuilt:
            drawing.processing.append(f"Штриховки построены заново по точному контуру: {rebuilt}")
        broken = check_rules(drawing)
        if broken:
            drawing.warnings.append(f"Правила контура не выполнены ({len(broken)}): "
                                    + "; ".join(broken[:15]))
        step(STAGES[7])
        snapped = snap_annotations(drawing)
        if snapped:
            drawing.processing.append(f"Точки размеров и штриховок притянуты к контуру: {snapped}")
    drawing.constraints = find_constraints(drawing.entities)
    if content.unknown_symbols:
        drawing.warnings.append(
            "Неизвестные символы шрифта: " + " ".join(sorted(content.unknown_symbols)))
    return drawing


def implied_diameters(drawing: ir.Drawing) -> list[str]:
    """A size across the axis of a turned part is a diameter even when the Ø
    sign was forgotten: the sign is added (the number stays as written).

    Symmetry alone is not enough (the width of a channel, a developed blade
    are symmetric too), so the axis must be a turned part's: another size
    across it carries the Ø sign, or the same diameter is a circle elsewhere
    on the sheet (the end view). Never across the centre lines of a circular
    view or section (widths of flats, keyways), nor on a drawing that marks
    squares (□)."""
    texts = [t.text for t in drawing.of_type(ir.Text)] + \
        [d.text for d in drawing.of_type(ir.Dimension)]
    if any("□" in (t or "") for t in texts):
        return []
    circles = [c for c in drawing.of_type(ir.Circle) if c.style == ir.STYLE_MAIN]

    def round_view(a, b):
        n = math.dist(a, b)
        for c in circles:
            s, t = _across(c.center, a, b)
            if abs(s) < 0.2 and -0.1 * n < t < 1.1 * n and 2 * c.radius >= 0.4 * n:
                return True
        return False

    axes = [(l.p1, l.p2) for l in drawing.of_type(ir.Line)
            if l.style == ir.STYLE_AXIAL and math.dist(l.p1, l.p2) >= 20.0
            and not round_view(l.p1, l.p2)]

    def across(d, a, b):
        (s1, t1), (s2, t2) = _across(d.p1, a, b), _across(d.p2, a, b)
        n = math.dist(a, b)
        return s1 * s2 < 0 and abs(t1 - t2) <= 0.2 and -2.0 <= t1 <= n + 2.0 \
            and abs(abs(s1) - abs(s2)) <= 0.2 + 0.02 * max(abs(s1), abs(s2))

    linear = [d for d in drawing.of_type(ir.Dimension)
              if d.dim_type == "linear" and d.p1 and d.p2]
    out = []
    for d in linear:
        text = (d.text or "").strip()
        if not text[:1].isdigit():
            continue
        size = math.dist(d.p1, d.p2)
        for a, b in axes:
            if not across(d, a, b):
                continue
            signed = any(o is not d and (o.text or "").startswith("Ø") and across(o, a, b)
                         for o in linear)
            seen = any(abs(2 * c.radius - size) <= 0.01 * size + 0.1 for c in circles)
            if signed or seen:
                d.text = "Ø" + text
                d.notes.append("знак Ø добавлен: размер поперёк оси")
                out.append(d.text)
                break
    return out


def _across(p, a, b):
    """(signed distance of ``p`` off the line a→b, its station along it)."""
    n = math.dist(a, b)
    ux, uy = (b[0] - a[0]) / n, (b[1] - a[1]) / n
    return ((p[0] - a[0]) * uy - (p[1] - a[1]) * ux, (p[0] - a[0]) * ux + (p[1] - a[1]) * uy)


def _ends_in_arrow(line: Primitive, arrows) -> bool:
    ux, uy = line.p2[0] - line.p1[0], line.p2[1] - line.p1[1]
    n = math.hypot(ux, uy) or 1.0
    ux, uy = ux / n, uy / n
    for a in arrows:
        if abs(a.direction[0] * uy - a.direction[1] * ux) > 0.1:
            continue
        if any(math.dist(a.tip, end) <= max(0.35, a.length + 0.5) and
               abs((a.tip[0] - line.p1[0]) * uy - (a.tip[1] - line.p1[1]) * ux) <= 0.35
               for end in (line.p1, line.p2)):
            return True
    return False


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
        parts = [[text, kind, round(x, 4), round(y, 4), h] for text, kind, x, y, h in t.parts] \
            if t.parts else None
        drawing.entities.append(ir.Text(new_id("T"), conf, notes, text=t.text,
                                        position=_r(t.origin), height=t.height, angle=t.angle,
                                        parts=parts))

    for region in regions:
        drawing.entities.append(ir.Hatch(new_id("H"), 0.9, [], angle=round(region.angle, 2),
                                         spacing=round(region.spacing, 3),
                                         contours=region.contours(), line_count=region.line_count))
    for g in orphan_groups:
        drawing.entities.append(ir.Hatch(
            new_id("H"), 0.5, ["Граница штриховки не найдена"], angle=round(g.angle, 2),
            spacing=round(g.spacing, 3), contours=[], line_count=len(g.lines)))
    branches = _radius_branches(drawing)
    if branches:
        drawing.processing.append(f"Дополнительные выноски радиусов: {branches}")
    tails = _drop_arrow_tails(drawing)
    if tails:
        drawing.processing.append(f"Хвосты стрелок угловых размеров убраны: {tails}")
    arcs = chords_to_arcs(drawing, new_id) + chord_fillets(drawing, new_id)
    if arcs:
        drawing.processing.append(f"Скругления, распознанные отрезками, заменены дугами: {arcs}")
    merged = merge_ellipses(drawing, new_id)
    if merged:
        drawing.processing.append(f"Эллипсов собрано из дуг: {merged}")


def _rebuild_hatches(drawing) -> int:
    """Hatch outlines from the faces of the final (exact) contour: the faces
    whose inside lies in the hatch as it was read become its region. The
    outline read from the PDF predates the corrections and stuck out of the
    contour by hundredths."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from .model3d.revolve import main_primitives
    from .semantics.regions import contour_faces

    faces = contour_faces(main_primitives(drawing))
    done = 0
    for h in drawing.of_type(ir.Hatch):
        if not h.contours:
            continue
        old = Polygon(h.contours[0], h.contours[1:]).buffer(0)
        if old.is_empty:
            continue
        # a face is the hatch's when most of it lies in the hatch as read (a
        # small neighbour touching it with its inner point is not)
        mine = [f for f in faces if f.area > 0
                and f.intersection(old).area >= 0.7 * f.area]
        if not mine:
            continue
        new = unary_union(mine)
        if new.geom_type != "Polygon" or abs(new.area - old.area) > 0.1 * old.area:
            continue
        rings = [new.exterior] + list(new.interiors)
        h.contours = [[(float(x), float(y)) for x, y in r.coords] for r in rings]
        done += 1
    return done


def _radius_branches(drawing, near_leader: float = 3.0, on_arc: float = 0.3) -> int:
    """A thin line from a radius value's leader to another arc of the same
    radius is a second leader of that value (one «R1» for two fillets): it
    becomes a branch of the dimension instead of a loose line."""
    arcs = drawing.of_type(ir.Arc)
    made = 0
    drop = set()
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type != "radius" or not (d.p1 and d.text_pos and d.radius):
            continue
        (ax, ay), (bx, by) = d.p1, d.text_pos
        L = math.hypot(bx - ax, by - ay) or 1.0
        for line in drawing.of_type(ir.Line):
            if line.style != ir.STYLE_THIN or line.id in drop:
                continue
            for start, tip in ((line.p1, line.p2), (line.p2, line.p1)):
                off = abs((bx - ax) * (start[1] - ay) - (by - ay) * (start[0] - ax)) / L
                along = ((start[0] - ax) * (bx - ax) + (start[1] - ay) * (by - ay)) / L
                if off > near_leader or not 0.0 <= along <= L + 5.0:
                    continue
                arc = next((a for a in arcs if abs(a.radius - d.radius) <= 0.3 * d.radius
                            and abs(math.dist(tip, a.center) - a.radius) <= on_arc
                            and math.dist(a.center, d.center) > 0.5), None)
                if arc is None:
                    continue
                d.branches.append([tuple(arc.center), arc.radius, tuple(tip), tuple(start)])
                drop.add(line.id)
                made += 1
                break
    drawing.entities = [e for e in drawing.entities if e.id not in drop]
    return made


def _drop_arrow_tails(drawing, tol: float = 0.3, max_angle: float = 25.0) -> int:
    """Thin lines that run on from the tip of an angular dimension's arrow
    along its arc (arrows drawn outside a small angle): KOMPAS draws them
    itself, as separate lines they are strays."""
    tips = []
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type == "angular" and d.center:
            for p in (d.p1, d.p2):
                if p:
                    tips.append((tuple(p), tuple(d.center)))
    drop = set()
    for line in drawing.of_type(ir.Line):
        if line.style != ir.STYLE_THIN:
            continue
        for tip, c in tips:
            for a, b in ((line.p1, line.p2), (line.p2, line.p1)):
                if math.dist(a, tip) > tol:
                    continue
                radial = math.atan2(tip[1] - c[1], tip[0] - c[0])
                along = math.atan2(b[1] - a[1], b[0] - a[0])
                # square to the radius = along the arc's tangent
                off = abs((math.degrees(along - radial) % 180.0) - 90.0)
                if off <= max_angle:
                    drop.add(line.id)
    drawing.entities = [e for e in drawing.entities if e.id not in drop]
    return len(drop)


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
        orientation=d.orientation, ref=ref_ids.get(id(d.ref)) if d.ref is not None else None,
        text_pos=_r(d.text.raw.origin), text_center=_r(_text_center(d.text.raw)))


def _text_center(t) -> tuple[float, float]:
    """Middle of a (possibly turned) text: halfway between its first and last
    character, half a character further on and half the height up."""
    a = math.radians(t.angle)
    end = t.last_origin or t.origin
    along, up = 0.3 * t.height, 0.5 * t.height
    return ((t.origin[0] + end[0]) / 2 + along * math.cos(a) - up * math.sin(a),
            (t.origin[1] + end[1]) / 2 + along * math.sin(a) + up * math.cos(a))


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
