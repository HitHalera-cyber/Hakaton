"""Dimension layout details and the fully defined revolve sketch."""

from kompas_ai import ir
from kompas_ai.kompas.writer import _side_extent
from kompas_ai.model3d.revolve import _refillet
from kompas_ai.model3d.sketch_dof import full_definition
from kompas_ai.pdf.vector_extractor import RawText
from kompas_ai.semantics.dimensions import FoundDimension, attach_deviations, parse_dim_text


def _text(s, origin, last, angle=0.0, h=5.0):
    return RawText(s, origin, angle, h, "", (0, 0, 0, 0), last_origin=last)


def test_raised_deviation_joins_its_dimension():
    dt = parse_dim_text(_text("R3", (10.0, 10.0), (13.0, 10.0)))
    d = FoundDimension("radius", dt, 12.0)
    other = _text("+0,2", (17.0, 13.0), (22.0, 13.0), h=3.5)
    far = _text("+0,2", (60.0, 13.0), (65.0, 13.0), h=3.5)
    left = attach_deviations([d], [other, far])
    assert d.text.raw.text == "R3+0,2" and left == [far]


def test_angle_side_reach_from_the_drawn_cone_side():
    d = ir.Drawing()
    d.entities.append(ir.Line("L1", p1=(10.0, 0.0), p2=(20.0, 0.0)))
    d.entities.append(ir.Line("L2", p1=(-10.0, 0.0), p2=(-1.0, 0.0)))  # behind the vertex
    assert abs(_side_extent(d, (0.0, 0.0), 0.0) - 20.0) < 1e-9
    assert _side_extent(d, (0.0, 0.0), 90.0) == 0.0


def _shaft_with_fillets():
    # stepped shaft half-profile, fillet R1 at the inner corner of the step
    pts = [(0, 0), (40, 0), (40, 5), (21, 5)]
    segs = [["line", pts[i], pts[i + 1]] for i in range(3)]
    segs.append(["arc", (21.02, 6.01), 1.004, 180.0, 270.0])
    segs.append(["line", (20.0, 6.0), (20.0, 10.0)])
    segs.append(["line", (20.0, 10.0), (0.0, 10.0)])
    segs.append(["line", (0.0, 10.0), (0.0, 0.0)])
    return segs


def test_fillet_rebuilt_tangent_with_written_radius():
    segs = _refillet(_shaft_with_fillets(), radii=[1.0])
    arc = segs[3]
    assert arc[1] == (21.0, 6.0) and arc[2] == 1.0
    assert segs[2][2] == (21.0, 5.0) and segs[4][1] == (20.0, 6.0)


def test_revolve_sketch_fully_defined_without_redundant_constraints():
    loop = [tuple(s) for s in _refillet(_shaft_with_fillets(), radii=[1.0])]
    segments, jobs, left = full_definition([loop], ((-5.0, 0.0), (45.0, 0.0)))
    assert left == 0
    kinds = {j.kind for j in jobs}
    assert {"coincident", "tangent", "horizontal", "vertical", "fixed_point"} <= kinds
    # joints first: the loop stays closed whatever else KOMPAS refuses
    assert [j.kind for j in jobs[:2]] == ["coincident", "coincident"]
