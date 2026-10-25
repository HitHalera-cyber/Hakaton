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
