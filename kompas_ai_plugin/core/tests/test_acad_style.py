"""PDFs whose lines are drawn "not like KOMPAS" (AutoCAD-style plots) are read
as their KOMPAS originals: same dimensions, a clean contour, the same model."""

from pathlib import Path

import pytest

from acadstyle import VARIANTS, variant
from kompas_ai import ir
from kompas_ai.gui.workers import judge_model
from kompas_ai.pipeline import recognize_pdf

DRAWINGS = Path(__file__).resolve().parents[2] / "test_drawings"


def _summary(pdf):
    d = recognize_pdf(pdf)
    ok, why = judge_model(d, True)
    dims = sorted((x.text, x.nominal) for x in d.of_type(ir.Dimension))
    return d, dims, ok, why.split(":")[0]


@pytest.mark.parametrize("name", ["flanets", "plita", "vtulka", "prokladka"])
@pytest.mark.parametrize("style", VARIANTS)
def test_autocad_style_lines_read_as_the_original(tmp_path, name, style):
    src = DRAWINGS / f"{name}.pdf"
    if not src.exists():
        pytest.skip("sample drawing missing")
    _, dims, ok, kind = _summary(src)
    d, v_dims, v_ok, v_kind = _summary(variant(src, style, tmp_path / f"{name}_{style}.pdf"))
    assert v_dims == dims
    assert (v_ok, v_kind) == (ok, kind)
    assert not d.issues


def test_one_width_plot_is_told_apart_by_role(tmp_path):
    src = DRAWINGS / "flanets.pdf"
    if not src.exists():
        pytest.skip("sample drawing missing")
    d = recognize_pdf(variant(src, "hair", tmp_path / "hair.pdf"))
    assert any("одной толщины" in w for w in d.warnings)
    styles = {e.style for e in d.entities if isinstance(e, (ir.Line, ir.Arc, ir.Circle))}
    assert "main" in styles and len(styles) > 1


def test_short_stepped_arrow_of_an_autocad_plot():
    """A 1.5 × 0.9 mm arrow filled row by row (as AutoCAD plots it): found,
    pointing straight down, its tip at the narrow end."""
    from kompas_ai.semantics.arrows import _arrow_from_points

    rows = [(12.19, 25.74, 26.67), (12.02, 25.82, 26.67), (11.85, 25.91, 26.59),
            (11.6, 25.91, 26.5), (11.43, 25.99, 26.5), (11.26, 25.99, 26.42),
            (11.09, 26.08, 26.33), (10.92, 26.08, 26.33), (10.75, 26.16, 26.25),
            (10.67, 26.16, 26.25)]
    pts = [p for y, a, b in rows for p in ((a, y), (b, y))]
    arrow = _arrow_from_points(pts)
    assert arrow is not None
    assert abs(arrow.direction[0]) < 0.08 and arrow.direction[1] < -0.99
    assert abs(arrow.tip[1] - 10.67) < 0.1


def test_a_solid_axis_of_one_width_is_found_by_symmetry():
    """Plotted without lineweights, the axis is as thick as the outline: the
    line the outline is mirrored across is the axis."""
    from kompas_ai.geometry.segmentation import Primitive
    from kompas_ai.semantics.linewidth import _symmetry_axes

    def line(a, b):
        return Primitive("line", [a, b], 0.035, 0.0, p1=a, p2=b)

    half = [((0, 20), (40, 20)), ((40, 20), (40, 12)), ((40, 12), (70, 12)), ((70, 12), (70, 0))]
    lines = [line(a, b) for a, b in half] + \
        [line((a[0], -a[1]), (b[0], -b[1])) for a, b in half] + [line((0, 20), (0, -20))]
    axis = line((-5, 0), (75, 0))
    found = _symmetry_axes(lines + [axis], set())
    assert found == {id(axis)}
