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


def test_thread_from_metric_dimension():
    d = ir.Drawing(source="synthetic")
    d.scale = ir.Scale(value=2.0, text="2:1", source="title_block")
    y0, k = 100.0, 2.0
    pts = [(0, 10), (30, 10), (30, 15), (70, 15), (70, -15), (30, -15), (30, -10), (0, -10)]
    pts = [(50 + x * k, y0 + y * k) for x, y in pts]
    d.entities = [_line(i, a, b) for i, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1]))]
    d.entities.append(_line(99, (40.0, y0), (200.0, y0), ir.STYLE_AXIAL))
    d.entities.append(ir.Dimension("D1", 0.95, [], dim_type="linear", text="M20×1,5"))
    from kompas_ai.model3d.revolve import profile_segments, thread_specs

    p = find_revolve_profile(d)
    (t,) = thread_specs(d, p, profile_segments(p))
    assert (t.diameter, t.pitch, t.outside) == (20.0, 1.5, True)
    assert abs(t.radius - 10.0) < 1e-6 and 0.0 < t.x < 30.0


def test_multiplication_sign_for_kompas():
    from kompas_ai.kompas.api5 import kompas_text

    assert kompas_text("1×45°") == "1x45°" and kompas_text("M22×1,5") == "M22x1,5"


def test_revolve_verdict():
    from kompas_ai import ir
    from kompas_ai.model3d.revolve import revolve_verdict

    axis = ir.Line("L1", p1=(0, 50), p2=(100, 50), style=ir.STYLE_AXIAL)
    d = ir.Drawing(entities=[axis, ir.Dimension("D1", text="40", p1=(0, 30), p2=(100, 30))])
    assert revolve_verdict(d)[0] is False  # a plate: sizes, none a diameter across the axis
    d.entities.append(ir.Dimension("D2", text="Ø20", p1=(30, 40), p2=(30, 60)))
    assert revolve_verdict(d)[0] is True
    assert revolve_verdict(ir.Drawing(entities=[axis]))[0] is None


def test_end_view_is_no_profile_axis():
    from kompas_ai import ir
    from kompas_ai.model3d.revolve import _end_view

    axis = ((0.0, 50.0), (100.0, 50.0))
    d = ir.Drawing(entities=[ir.Circle("C1", center=(50, 50), radius=45)])
    assert _end_view(d, axis)
    d = ir.Drawing(entities=[ir.Circle("C1", center=(50, 50), radius=5)])
    assert not _end_view(d, axis)


def test_forgotten_diameter_sign():
    from kompas_ai import ir
    from kompas_ai.pipeline import implied_diameters

    axis = ir.Line("L1", p1=(0, 50), p2=(100, 50), style=ir.STYLE_AXIAL)
    signed = ir.Dimension("D1", text="Ø20", p1=(30, 40), p2=(30, 60))
    bare = ir.Dimension("D2", text="30", p1=(60, 35), p2=(60, 65))
    d = ir.Drawing(entities=[axis, signed, bare])
    assert implied_diameters(d) == ["Ø30"] and bare.text == "Ø30"

    # no Ø anywhere, but the same diameter is a circle on the end view
    bare = ir.Dimension("D2", text="30", p1=(60, 35), p2=(60, 65))
    end = ir.Circle("C1", center=(200, 50), radius=15)
    d = ir.Drawing(entities=[axis, bare, end])
    assert implied_diameters(d) == ["Ø30"]

    # a symmetric width with nothing round about it stays as written
    bare = ir.Dimension("D2", text="30", p1=(60, 35), p2=(60, 65))
    d = ir.Drawing(entities=[axis, bare])
    assert implied_diameters(d) == [] and bare.text == "30"


def test_width_across_a_round_view_is_no_diameter():
    from kompas_ai import ir
    from kompas_ai.pipeline import implied_diameters

    # the end view: centre lines through a circle, a width of flats across them
    axis = ir.Line("L1", p1=(0, 50), p2=(60, 50), style=ir.STYLE_AXIAL)
    rim = ir.Circle("C1", center=(30, 50), radius=25)
    flats = ir.Dimension("D1", text="32", p1=(20, 34), p2=(20, 66))
    other = ir.Dimension("D2", text="Ø40", p1=(25, 30), p2=(25, 70))
    d = ir.Drawing(entities=[axis, rim, flats, other, ir.Circle("C2", center=(0, 0), radius=16)])
    assert implied_diameters(d) == []


def test_channels_across_the_axis():
    """An injector: the end view with a pair of parallel lines across the
    wall, the main view with a small circle of the same size on the section."""
    from types import SimpleNamespace

    from kompas_ai import ir
    from kompas_ai.model3d.channels import find_channels

    d = ir.Drawing(scale=ir.Scale(value=5.0, text="5:1"))
    c = (113.0, 120.0)  # the end view: outer Ø10, the cavity Ø4,6
    d.entities = [ir.Circle("C1", center=c, radius=25.0), ir.Circle("C2", center=c, radius=11.5),
                  # a channel Ø0,8 going up, 1,9 mm left of the centre
                  ir.Line("L1", p1=(101.5, 120.0), p2=(101.5, 142.0)),
                  ir.Line("L2", p1=(105.5, 129.5), p2=(105.5, 144.3)),
                  # the main view, along x = 113: the channel cut, 4,67 above the end
                  ir.Circle("C3", center=(103.5, 190.7), radius=2.0),
                  ir.Dimension("D1", text="Ø0,8", nominal=0.8, p1=(101.5, 137.0), p2=(105.5, 137.0)),
                  ir.Dimension("D2", text="4,67", nominal=4.67, p1=(113.0, 190.7),
                               p2=(113.0, 167.35))]
    profile = SimpleNamespace(axis=((113.0, 164.15), (113.0, 219.2)),
                              rings=[[(0.64, 0.0), (10.0, 0.0), (10.0, 5.0), (0.64, 5.0)]])
    (ch,) = find_channels(d, profile)
    assert ch.along == 2 and ch.sign == 1  # along the view's vertical, upwards
    assert abs(ch.offset + 1.9) < 0.01 and ch.radius == 0.4
    assert abs(ch.x - 4.67) < 0.01
