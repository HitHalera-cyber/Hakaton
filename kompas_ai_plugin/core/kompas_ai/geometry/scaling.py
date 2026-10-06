"""Drawing scale: from the title block, cross-checked against every dimension.

Each linear/diameter/radius dimension gives ``measured_on_sheet / nominal``.
Their median is the scale implied by the dimensions. Disagreement with the
title block, or a dimension that does not match the geometry it is drawn on,
is reported — never silently corrected.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from ..ir import Scale

STANDARD_SCALES = [1, 2, 2.5, 4, 5, 10, 15, 20, 25, 40, 50, 75, 100, 200, 400, 500, 800, 1000]
SNAP_TOLERANCE = 0.015
CONFLICT_TOLERANCE = 0.02


@dataclass
class DimensionCheck:
    model_value: float
    deviation: float  # model_value - nominal (mm or degrees)
    tolerance: float
    ok: bool


def scale_text(value: float) -> str:
    def fmt(v):
        return f"{v:g}".replace(".", ",")
    return f"{fmt(value)}:1" if value >= 1 else f"1:{fmt(1 / value)}"


def snap_scale(value: float) -> float:
    for s in STANDARD_SCALES:
        for candidate in (float(s), 1.0 / s):
            if abs(value / candidate - 1) <= SNAP_TOLERANCE:
                return candidate
    return value


def resolve_scale(title: Scale, ratios: list[float]) -> Scale:
    """Combine the title-block scale with the ratios measured on dimensions."""
    scale = Scale(value=title.value, text=title.text, source=title.source)
    if ratios:
        estimate = median(ratios)
        scale.dimension_estimate = round(estimate, 4)
        if title.source == "default":
            snapped = snap_scale(estimate)
            scale.value, scale.text, scale.source = snapped, scale_text(snapped), "dimensions"
        elif abs(estimate / title.value - 1) > CONFLICT_TOLERANCE:
            scale.conflicts.append(
                f"Масштаб в основной надписи {title.text}, а по размерам получается "
                f"{scale_text(snap_scale(estimate))} (≈{estimate:.3f}). Проверьте масштаб.")
        spread = [r for r in ratios if abs(r / scale.value - 1) > CONFLICT_TOLERANCE]
        if spread and len(spread) < len(ratios):
            scale.conflicts.append(
                f"{len(spread)} из {len(ratios)} размеров не соответствуют масштабу "
                f"{scale.text} — они отмечены как требующие проверки.")
    return scale


def check_dimension(dim_type: str, measured: float, nominal: float, decimals: int,
                    scale: float) -> DimensionCheck:
    """Does the written value match the drawn geometry (within rounding)?"""
    if dim_type == "angular":
        model = measured
        tolerance = 0.6 * 10 ** -decimals + 0.3
    else:
        model = measured / scale
        tolerance = 0.6 * 10 ** -decimals + max(0.01, 0.005 * nominal)
    deviation = model - nominal
    return DimensionCheck(model, deviation, tolerance, abs(deviation) <= tolerance)
