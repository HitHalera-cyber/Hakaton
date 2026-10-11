"""Exact mode: the written sizes hold exactly, sizes nobody wrote are round,
two sizes that contradict each other do not bend the outline; tables."""

import math

from kompas_ai import ir
from kompas_ai.geometry.regularize import solve_contour
from kompas_ai.geometry.rules import check


def _plate(dims):
    """A 60 × 40 plate as read from a PDF at 1:1: a few hundredths off."""
    d = ir.Drawing(scale=ir.Scale(value=1.0))
    d.entities = [
        ir.Line("L1", p1=(10.0, 10.0), p2=(70.04, 10.0)),
        ir.Line("L2", p1=(70.04, 10.0), p2=(70.04, 49.97)),
        ir.Line("L3", p1=(70.04, 49.97), p2=(10.0, 49.97)),
        ir.Line("L4", p1=(10.0, 49.97), p2=(10.0, 10.0)),
    ] + dims
    return d


def _dim(i, text, value, p1, p2, orientation):
    return ir.Dimension(i, 0.95, dim_type="linear", text=text, nominal=value, measured=0.0,
                        p1=p1, p2=p2, orientation=orientation)


def _length(d, line_id):
    line = d.get(line_id)
    return math.dist(line.p1, line.p2)


def test_written_sizes_hold_exactly_and_the_rest_is_round():
    d = _plate([_dim("D1", "60", 60.0, (10.0, 49.97), (70.04, 49.97), "horizontal")])
    report = solve_contour(d)
    assert report["dims"] == 1
    assert math.isclose(_length(d, "L3"), 60.0, abs_tol=1e-6)  # written: exactly
    assert math.isclose(_length(d, "L2"), 40.0, abs_tol=1e-6)  # nobody wrote it: 39,97 → 40
    assert check(d) == []


def test_contradicting_size_is_left_out_not_averaged():
    # 60 overall and 25 + 30 along the same side: one of them cannot hold
    d = _plate([_dim("D1", "60", 60.0, (10.0, 49.97), (70.04, 49.97), "horizontal")])
    d.entities.insert(0, ir.Line("L5", p1=(35.0, 10.0), p2=(35.0, 49.97)))
    d.entities += [_dim("D2", "25", 25.0, (10.0, 10.0), (35.0, 10.0), "horizontal"),
                   _dim("D3", "30", 30.0, (35.0, 10.0), (70.04, 10.0), "horizontal")]
    report = solve_contour(d)
    assert report["dims_skipped"]  # the smallest one gives way
    assert math.isclose(_length(d, "L3"), 60.0, abs_tol=1e-6)
    assert check(d) == []  # and the outline stays square


def test_table_is_found_and_read():
    from kompas_ai.semantics.tables import find_tables

    d = ir.Drawing()
    xs, ys = [0.0, 20.0, 40.0, 60.0], [0.0, 10.0, 20.0]
    n = 0
    for y in ys:
        n += 1
        d.entities.append(ir.Line(f"L{n}", p1=(xs[0], y), p2=(xs[-1], y), style=ir.STYLE_THIN))
    for x in xs:
        n += 1
        d.entities.append(ir.Line(f"L{n}", p1=(x, ys[0]), p2=(x, ys[-1]), style=ir.STYLE_THIN))
    d.entities += [ir.Text("T1", text="a", position=(8.0, 13.0), height=3.5),
                   ir.Text("T2", text="b", position=(28.0, 13.0), height=3.5),
                   ir.Text("T3", text="c", position=(48.0, 13.0), height=3.5),
                   ir.Text("T4", text="1,5 2,5 3,5", position=(4.0, 3.0), height=3.5)]
    count = 0

    def new_id(prefix):
        nonlocal count
        count += 1
        return f"{prefix}{count}"

    assert find_tables(d, new_id) == 1
    t = d.of_type(ir.Table)[0]
    assert t.cells == [["a", "b", "c"], ["1,5", "2,5", "3,5"]]
    assert t.widths == [20.0, 20.0, 20.0] and t.heights == [10.0, 10.0]
    assert t.top_left == (0.0, 20.0)
