import math

from kompas_ai import ir
from kompas_ai.geometry.regularize import regularize


def test_geometry_follows_written_dimensions():
    # A 60 × 40 plate measured slightly off in the PDF, with a Ø20 hole drawn Ø19.96.
    d = ir.Drawing(scale=ir.Scale(value=1.0))
    d.entities = [
        ir.Line("L1", p1=(10.0, 10.0), p2=(70.06, 10.02)),  # bottom, a hair tilted
        ir.Line("L2", p1=(70.06, 10.02), p2=(70.06, 49.97)),
        ir.Line("L3", p1=(70.06, 49.97), p2=(10.0, 49.97)),
        ir.Line("L4", p1=(10.0, 49.97), p2=(10.0, 10.0)),
        ir.Circle("C1", center=(40.03, 30.0), radius=9.98),
        ir.Dimension("D1", dim_type="linear", text="60", nominal=60, measured=60.06,
                     p1=(10.0, 49.97), p2=(70.06, 49.97), line_point=(40, 60),
                     orientation="horizontal"),
        ir.Dimension("D2", dim_type="linear", text="40", nominal=40, measured=39.97,
                     p1=(70.06, 10.02), p2=(70.06, 49.97), line_point=(80, 30),
                     orientation="vertical"),
        ir.Dimension("D3", dim_type="diameter", text="Ø20", nominal=20, measured=19.96,
                     center=(40.03, 30.0), radius=9.98, ref="C1"),
    ]
    report = regularize(d)
    lines = {e.id: e for e in d.of_type(ir.Line)}
    assert lines["L1"].p1[1] == lines["L1"].p2[1]  # straightened
    assert math.isclose(lines["L3"].p1[0] - lines["L3"].p2[0], 60.0, abs_tol=1e-6)
    assert math.isclose(lines["L2"].p2[1] - lines["L2"].p1[1], 40.0, abs_tol=1e-6)
    assert d.of_type(ir.Circle)[0].radius == 10.0
    assert report.dimensions_used == 2 and report.radii_set == 1 and not report.skipped


def test_contradicting_dimension_is_not_used():
    d = ir.Drawing(scale=ir.Scale(value=1.0))
    d.entities = [
        ir.Line("L1", p1=(0.0, 0.0), p2=(50.0, 0.0)),
        ir.Dimension("D1", dim_type="linear", text="45", nominal=45, measured=50,
                     p1=(0.0, 0.0), p2=(50.0, 0.0), orientation="horizontal"),
    ]
    report = regularize(d)
    assert report.skipped == ["D1"]
    assert d.of_type(ir.Line)[0].p2 == (50.0, 0.0)
