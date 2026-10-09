import math

from kompas_ai.geometry.chains import Chain
from kompas_ai.geometry.fitting import fit_circle, fit_line
from kompas_ai.geometry.segmentation import segment_chain


def circle_points(c, r, n=40, start=0.0, sweep=360.0):
    return [(c[0] + r * math.cos(math.radians(start + sweep * i / n)),
             c[1] + r * math.sin(math.radians(start + sweep * i / n))) for i in range(n + 1)]


def test_fit_line_endpoints():
    fit = fit_line([(0, 0), (5, 0.01), (10, 0)])
    assert math.dist(fit.p1, (0, 0)) < 0.02 and math.dist(fit.p2, (10, 0)) < 0.02


def test_fit_circle_exact():
    fit = fit_circle(circle_points((3, -2), 7.5))
    assert math.dist(fit.center, (3, -2)) < 1e-6 and abs(fit.radius - 7.5) < 1e-6


def test_closed_polyline_is_circle():
    pts = circle_points((10, 10), 4, n=32)
    prims = segment_chain(Chain(pts, 0.6, closed=True))
    assert [p.kind for p in prims] == ["circle"]
    assert abs(prims[0].radius - 4) < 1e-6


def test_slot_line_arc_line():
    # line, then a tangent half circle, then a line back: a slot end
    line1 = [(0, 0), (10, 0)]
    arc = circle_points((10, 5), 5, n=18, start=-90, sweep=180)
    line2 = [(10, 10), (0, 10)]
    pts = line1 + arc[1:] + line2[1:]
    kinds = [p.kind for p in segment_chain(Chain(pts, 0.6, closed=False))]
    assert kinds == ["line", "arc", "line"]


def test_corner_is_two_lines():
    prims = segment_chain(Chain([(0, 0), (10, 0), (10, 10)], 0.6, closed=False))
    assert [p.kind for p in prims] == ["line", "line"]


def test_small_fillet_with_two_chords_is_an_arc():
    """A line, an R2 fillet drawn with two chords, a 45° chamfer (KOMPAS PDF)."""
    import math

    from kompas_ai.geometry.chains import Chain
    from kompas_ai.geometry.segmentation import segment_chain

    c, r = (134.38, 362.25), 2.0
    fillet = [(c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)))
              for a in (270.0, 251.5, 233.0)]
    end = fillet[-1]
    pts = [(149.6, c[1] - r)] + fillet + [(end[0] - 4.0, end[1] + 4.0)]
    prims = segment_chain(Chain(pts, 0.6, False))
    arcs = [p for p in prims if p.kind == "arc"]
    assert len(arcs) == 1 and abs(arcs[0].radius - r) < 0.1 and math.dist(arcs[0].center, c) < 0.1
