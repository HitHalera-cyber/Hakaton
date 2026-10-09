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


def test_arc_state_read_back_from_kompas():
    from kompas_ai.kompas.api5 import arc_state

    assert arc_state(10.0, 80.0, 10.0, 80.0, False) == "ok"
    # stored clockwise from our start: the other three quarters
    assert arc_state(10.0, 80.0, 10.0, 80.0, True) == "flip"
    # an arc through 0° with its angles sorted by KOMPAS
    assert arc_state(270.87, 4.736, 4.736, 270.87, False) == "flip"
    assert arc_state(270.87, 4.736, 4.736, 270.87, True) == "swapped"
    assert arc_state(270.0, 360.0, 270.0, 0.0, False) == "ok"


def test_ellipse_fit_and_merge_from_arcs():
    import math

    import numpy as np

    from kompas_ai.geometry.ellipses import fit_ellipse, merge_ellipses

    t = np.linspace(0, 2 * math.pi, 50)
    pts = np.column_stack([10 + 4 * np.cos(t), 20 + 3 * np.sin(t)])
    (cx, cy), a, b, angle, err = fit_ellipse(pts)
    assert abs(cx - 10) < 1e-6 and abs(a - 4) < 1e-6 and abs(b - 3) < 1e-6 and err < 1e-6
    assert angle % 180 < 1e-6 or abs(angle % 180 - 180) < 1e-6

    # an ellipse 4×3 drawn as four arcs (osculating circles at the vertices
    # stretched to meet): the merge only needs a closed smooth loop near it
    d = ir.Drawing()
    k = 0
    for start in (0, 90, 180, 270):
        mid = math.radians(start + 45)
        k += 1
        # each quarter by the circle through its ends and its middle point
        p = [(4 * math.cos(math.radians(a)), 3 * math.sin(math.radians(a)))
             for a in (start, start + 45, start + 90)]
        (x1, y1), (x2, y2), (x3, y3) = p
        dd = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1)
              + (x3 * x3 + y3 * y3) * (y1 - y2)) / dd
        uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3)
              + (x3 * x3 + y3 * y3) * (x2 - x1)) / dd
        r = math.dist((ux, uy), p[0])
        a1 = math.degrees(math.atan2(y1 - uy, x1 - ux)) % 360
        a2 = math.degrees(math.atan2(y3 - uy, x3 - ux)) % 360
        d.entities.append(ir.Arc(f"A{k}", center=(ux, uy), radius=r, start_angle=a1, end_angle=a2))
        _ = mid
    ids = iter(range(1, 10))
    assert merge_ellipses(d, lambda prefix: f"{prefix}{next(ids)}") == 1
    (e,) = d.of_type(ir.Ellipse)
    assert abs(e.a - 4) < 0.1 and abs(e.b - 3) < 0.1 and not d.of_type(ir.Arc)


def test_flange_outline_closed_exactly():
    import math

    from kompas_ai.model3d.endview import _ends_of, close_loop

    # a flat at y = 9 between two arcs of R20, ends a few hundredths off
    a = math.degrees(math.asin(9 / 20))
    segs = [["line", (-17.85, 9.01), (17.87, 8.99)],
            ["arc", (0.0, 0.0), 20.0, -a, a + 0.05],
            ["line", (17.85, -9.0), (-17.85, -9.02)],
            ["arc", (0.0, 0.0), 20.0, 180 - a - 0.03, 180 + a]]
    out = close_loop(segs)
    for s, t in zip(out, out[1:] + out[:1]):
        gap = min(math.dist(p, q) for p in _ends_of(s) for q in _ends_of(t))
        assert gap < 1e-9
