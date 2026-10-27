"""Sizes put on a finished drawing: views found, sizes laid out by ГОСТ 2.307."""

import ezdxf
import pytest

from kompas_ai import dimensioning as dm
from kompas_ai import ir


def _kompas_dxf(path, with_dim=False):
    """An A3 sheet as KOMPAS saves it: the frame, a stepped shaft drawn about
    its axis (2:1) and a plate with holes, the line types named K5LT_…"""
    doc = ezdxf.new("R2018")
    for name in ("K5LT_BASIC", "K5LT_THIN", "K5LT_AXLED"):
        doc.linetypes.add(name, pattern=[0.0])
    msp = doc.modelspace()
    main = {"linetype": "K5LT_BASIC"}

    def poly(points, attribs=main):
        for a, b in zip(points, points[1:]):
            msp.add_line(a, b, dxfattribs=attribs)

    poly([(20, 5), (415, 5), (415, 292), (20, 292), (20, 5)])  # the frame
    poly([(230, 5), (230, 60), (415, 60)])  # the title block
    msp.add_text("2:1", height=3.5, dxfattribs={"insert": (390, 20)})
    # the shaft: Ø40 × 30, Ø30 × 40, Ø20 × 20 (model mm), at 2:1, axis y = 200
    y = 200
    xs, rs = [40, 100, 180, 220], [40, 30, 20]
    top = [(xs[0], y)]
    for k, r in enumerate(rs):
        top += [(xs[k], y + r), (xs[k + 1], y + r)]
    top.append((xs[-1], y))
    poly(top)
    poly([(p[0], 2 * y - p[1]) for p in top])
    for x in xs[1:-1]:
        poly([(x, y - rs[xs.index(x)]), (x, y + rs[xs.index(x)])])
    msp.add_line((35, y), (225, y), dxfattribs={"linetype": "K5LT_AXLED"})
    # the plate 60 × 40 with two Ø10 holes, at 2:1
    poly([(280, 160), (400, 160), (400, 240), (280, 240), (280, 160)])
    for cx in (310, 370):
        msp.add_circle((cx, 200), 10, dxfattribs=main)
    if with_dim:
        msp.add_linear_dim(base=(250, 150), p1=(280, 160), p2=(400, 160), angle=0,
                           text="60").render()
    doc.header["$EXTMIN"] = (0, 0, 0)
    doc.header["$EXTMAX"] = (420, 297, 0)
    doc.saveas(path)
    return path


@pytest.fixture
def sheet(tmp_path):
    return _kompas_dxf(tmp_path / "sheet.dxf")


def _lines_apart(dims):
    """No two parallel dimension lines closer than 5 mm over a common stretch."""
    lin = [d for d in dims if d.dim_type == "linear" and "диаметр" not in d.notes]
    for i, a in enumerate(lin):
        for b in lin[i + 1:]:
            if a.orientation != b.orientation:
                continue
            k = 1 if a.orientation == "horizontal" else 0
            a_lo, a_hi = sorted((a.p1[1 - k], a.p2[1 - k]))
            b_lo, b_hi = sorted((b.p1[1 - k], b.p2[1 - k]))
            if min(a_hi, b_hi) - max(a_lo, b_lo) > 1.0:
                assert abs(a.line_point[k] - b.line_point[k]) >= 5.0 - 1e-6, (a.text, b.text)


def test_views_and_sizes(sheet):
    src = dm.read_dxf(sheet)
    assert src.scale == 2.0
    result = dm.dimension(src)
    views = dm.find_views(src.drawing)
    assert len(views) == 2  # the frame and the title block are no view
    assert src.drawing.sheet.format == "A3"
    texts = {d.text for d in result.added}
    assert {"Ø40", "Ø30", "Ø20"} <= texts  # the shaft's diameters
    assert "90" in texts  # its overall length
    assert "2 отв. Ø10" in texts and "60" in texts and "40" in texts
    _lines_apart(result.added)
    # the first line 10 mm off the contour, all inside the frame
    for d in result.added:
        if d.dim_type == "linear" and "диаметр" not in d.notes:
            assert 20 <= d.line_point[0] <= 415 and 5 <= d.line_point[1] <= 292


def test_chain_left_open(sheet):
    result = dm.dimension(dm.read_dxf(sheet))
    steps = [d.text for d in result.added if "длина" in d.notes]
    # 30, 40, 20: the longest step is left out of the chain, the overall given
    assert sorted(steps) == ["20", "30"]


def test_existing_sizes_kept_and_not_repeated(tmp_path):
    path = _kompas_dxf(tmp_path / "dims.dxf", with_dim=True)
    src = dm.read_dxf(path)
    old = src.drawing.of_type(ir.Dimension)
    assert len(old) == 1 and old[0].text == "60"
    result = dm.dimension(src)
    assert not any(d.text == "60" for d in result.added)
    assert not result.removed
    again = dm.dimension(dm.read_dxf(path), replace=True)
    assert len(again.removed) == 1 and any(d.text == "60" for d in again.added)


def test_written_dxf(sheet, tmp_path):
    result = dm.dimension(dm.read_dxf(sheet))
    out = tmp_path / "out.dxf"
    dm.write_dxf(sheet, result, out)
    dims = [e for e in ezdxf.readfile(out).modelspace() if e.dxftype() == "DIMENSION"]
    assert len(dims) == len(result.added)


def test_plain_text():
    assert dm.plain_text(r"\H5.0;\W0.965;\Q15;∅\H5.0;\Q15;26h12") == "Ø26h12"
