from kompas_ai import ir
from kompas_ai.model3d.revolve import find_revolve_profile


def _line(i, a, b, style=ir.STYLE_MAIN):
    return ir.Line(f"L{i}", 0.97, [], p1=a, p2=b, style=style)


def test_stepped_shaft_profile_from_outline():
    """Ø20×30 + Ø30×40 shaft drawn 2:1 around a horizontal axis at y = 100."""
    d = ir.Drawing(source="synthetic")
    d.scale = ir.Scale(value=2.0, text="2:1", source="title_block")
    y0, k = 100.0, 2.0
    pts = [(0, 10), (30, 10), (30, 15), (70, 15), (70, -15), (30, -15), (30, -10), (0, -10)]
    pts = [(50 + x * k, y0 + y * k) for x, y in pts]
    d.entities = [_line(i, a, b) for i, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1]))]
    d.entities.append(_line(99, (40.0, y0), (200.0, y0), ir.STYLE_AXIAL))
    d.entities.append(_line(98, (110.0, y0 + 30), (110.0, y0 - 30)))  # the shoulder line

    profile = find_revolve_profile(d)
    assert profile is not None and profile.source == "outline"
    xs = [x for r in profile.rings for x, _ in r]
    ys = [y for r in profile.rings for _, y in r]
    assert abs((max(xs) - min(xs)) - 70.0) < 1e-6
    assert abs(max(ys) - 15.0) < 1e-6 and min(ys) == 0.0
    assert abs(profile.area - (30 * 10 + 40 * 15)) < 1e-3
