"""Human-readable recognition report (the text shown in the plugin window)."""

from __future__ import annotations

from pathlib import Path

from .. import ir

TYPE_NAMES = {
    "line": "Отрезок", "circle": "Окружность", "arc": "Дуга", "dimension": "Размер",
    "text": "Текст", "hatch": "Штриховка", "pointmark": "Точка",
}


def summary_text(drawing: ir.Drawing) -> str:
    lines = drawing.of_type(ir.Line)
    s = drawing.sheet
    out = [
        "Распознавание чертежа",
        "=" * 40,
        f"Файл:      {Path(drawing.source).name}",
        f"Формат:    {s.format} ({'книжная' if s.orientation == 'portrait' else 'альбомная'})",
        f"Масштаб:   {drawing.scale.text}" + _scale_note(drawing.scale),
        "",
        "Найдено:",
        f"  Линий:        {len([l for l in lines if l.style != ir.STYLE_AXIAL])}",
        f"  Осевых:       {len([l for l in lines if l.style == ir.STYLE_AXIAL])}",
        f"  Окружностей:  {len(drawing.of_type(ir.Circle))}",
        f"  Дуг:          {len(drawing.of_type(ir.Arc))}",
        f"  Размеров:     {len(drawing.of_type(ir.Dimension))}",
        f"  Текстов:      {len(drawing.of_type(ir.Text))}",
        f"  Штриховок:    {len(drawing.of_type(ir.Hatch))}",
        f"  Связей:       {len(drawing.constraints)}",
        "",
        f"Требуют проверки: {len(drawing.review)}",
    ]
    for e in drawing.review:
        name = TYPE_NAMES.get(e.kind, e.kind)
        note = "; ".join(e.notes) if e.notes else ""
        out.append(f"  - {name} {e.id} (уверенность {e.confidence:.0%}){': ' + note if note else ''}")
    if drawing.warnings:
        out += ["", "Предупреждения:"] + [f"  ! {w}" for w in drawing.warnings]
    dims = drawing.of_type(ir.Dimension)
    if dims:
        out += ["", "Размеры:"]
        for d in dims:
            model = d.measured if d.dim_type == "angular" else d.measured / drawing.scale.value
            unit = "°" if d.dim_type == "angular" else " мм"
            out.append(f"  {d.id:<4} {d.text:<8} {_dim_name(d.dim_type):<10} по геометрии "
                       f"{model:.3f}{unit}  уверенность {d.confidence:.0%}")
    return "\n".join(out)


def _scale_note(scale: ir.Scale) -> str:
    if scale.source == "title_block":
        note = " (из основной надписи"
        if scale.dimension_estimate:
            note += f", по размерам {scale.dimension_estimate:.3f}"
        return note + ")"
    if scale.source == "dimensions":
        return " (вычислен по размерам)"
    return " (не найден, принят 1:1)"


def _dim_name(dim_type: str) -> str:
    return {"linear": "линейный", "diameter": "диаметр", "radius": "радиус",
            "angular": "угловой"}.get(dim_type, dim_type)
