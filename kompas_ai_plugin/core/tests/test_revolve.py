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


def test_profile_segments_close_and_keep_arcs():
    """A Ø20 rod with an R2 rounded end (2:1): one arc, loop closed exactly."""
    import math

    d = ir.Drawing(source="synthetic")
    d.scale = ir.Scale(value=2.0, text="2:1", source="title_block")
    k, y0 = 2.0, 100.0
    P = lambda x, y: (50 + x * k, y0 + y * k)  # noqa: E731
    d.entities = [_line(1, P(0, 10), P(28, 10)), _line(2, P(30, 8), P(30, -8)),
                  _line(3, P(28, -10), P(0, -10)), _line(4, P(0, -10), P(0, 10)),
                  _line(9, (40.0, y0), (130.0, y0), ir.STYLE_AXIAL)]
    for i, (a0, a1) in enumerate(((0.0, 90.0), (270.0, 360.0))):
        d.entities.append(ir.Arc(f"A{i}", 0.97, [], center=P(28, 8 if i == 0 else -8), radius=4.0,
                                 start_angle=a0, end_angle=a1))
    from kompas_ai.model3d.revolve import profile_segments

    p = find_revolve_profile(d)
    (loop,) = profile_segments(p)
    arcs = [s for s in loop if s[0] == "arc"]
    assert len(arcs) == 1 and abs(arcs[0][2] - 2.0) < 1e-3

    def ends(s):
        if s[0] == "line":
            return s[1], s[2]
        c, r, a1, a2 = s[1:]
        return ((c[0] + r * math.cos(math.radians(a1)), c[1] + r * math.sin(math.radians(a1))),
                (c[0] + r * math.cos(math.radians(a2)), c[1] + r * math.sin(math.radians(a2))))
    for s1, s2 in zip(loop, loop[1:] + loop[:1]):
        assert min(math.dist(a, b) for a in ends(s1) for b in ends(s2)) < 1e-6
