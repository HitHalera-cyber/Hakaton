import math

import ezdxf
import pytest

from kompas_ai import ir
from kompas_ai.export.dxf_writer import write_dxf
from kompas_ai.pipeline import recognize_pdf
from kompas_ai.report.preview import render_preview
from synthetic import plate_with_hole


@pytest.mark.parametrize("bezier", [False, True], ids=["chords", "bezier"])
def test_plate_with_hole(tmp_path, bezier):
    truth = plate_with_hole(tmp_path / "plate.pdf", bezier=bezier)
    d = recognize_pdf(tmp_path / "plate.pdf")

    (c, r) = truth["circle"]
    circles = d.of_type(ir.Circle)
    assert len(circles) == 1
    assert math.dist(circles[0].center, c) < 0.05 and abs(circles[0].radius - r) < 0.05

    main = [l for l in d.of_type(ir.Line) if l.style == ir.STYLE_MAIN]
    assert len(main) == 4
    for a, b in truth["lines"]:
        assert any(min(math.dist(a, l.p1) + math.dist(b, l.p2),
                       math.dist(a, l.p2) + math.dist(b, l.p1)) < 0.1 for l in main)

    axial = [l for l in d.of_type(ir.Line) if l.style == ir.STYLE_AXIAL]
    assert len(axial) == 2

    dims = {x.text: x for x in d.of_type(ir.Dimension)}
    assert set(dims) == set(truth["dims"])
    for text, (kind, value) in truth["dims"].items():
        assert dims[text].dim_type == kind
        assert abs(dims[text].measured - value) < 0.1
        assert dims[text].confidence >= 0.9
    assert d.scale.value == 1.0 and not d.warnings


def test_wrong_dimension_value_goes_to_review(tmp_path):
    plate_with_hole(tmp_path / "plate.pdf", width_text="50")  # drawn 60 mm, written 50
    d = recognize_pdf(tmp_path / "plate.pdf")
    wrong = next(x for x in d.of_type(ir.Dimension) if x.text == "50")
    assert wrong in d.review and wrong.notes


def test_outputs(tmp_path):
    plate_with_hole(tmp_path / "plate.pdf")
    d = recognize_pdf(tmp_path / "plate.pdf")
    d.save_json(tmp_path / "d.json")
    write_dxf(d, tmp_path / "d.dxf")
    render_preview(d, tmp_path / "plate.pdf", tmp_path / "p.png", dpi=50)
    msp = ezdxf.readfile(tmp_path / "d.dxf").modelspace()
    assert len(msp.query("CIRCLE")) == 1 and len(msp.query("DIMENSION")) == 2
    assert (tmp_path / "p.png").stat().st_size > 1000
