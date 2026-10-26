"""Tolerances and roughness: read off the size texts, limits by ISO 286 for
H/h/JS/js, the user's own value and tolerance; a sketch without a frame in
the middle of the sheet; a drilled hole in an unhatched view."""

import math

import pytest

from kompas_ai import ir
from kompas_ai.semantics.tolerance import deviations, limits_text, middle, roughness, split_size


@pytest.mark.parametrize("text, parts", [
    ("Ø23-0,2", ("Ø", "23", "-0,2")),
    ("Ø26h12", ("Ø", "26", "h12")),
    ("23,5±0,1", ("", "23,5", "±0,1")),
    ("2 отв. Ø8H7", ("2 отв. Ø", "8", "H7")),
    ("M22×1,5-6g", ("M", "22×1,5-6g", "")),
    ("55,5", ("", "55,5", "")),
])
def test_split_size(text, parts):
    assert split_size(text) == parts


def test_limits_and_middle():
    assert limits_text(23, "-0,2") == "22,8 … 23"
    assert limits_text(26, "h12") == "25,79 … 26"  # IT12 for 18–30 mm: 0,21
    assert deviations(8, "H7") == pytest.approx((0.015, 0.0))
    assert deviations(40, "+0,2/-0,1") == pytest.approx((0.2, -0.1))
    assert middle(30, "+1") == pytest.approx(30.5)
    assert "f7" in limits_text(30, "f7")  # not tabulated: the field is named
    assert roughness("Rz 20 (√)") == ("Rz", 20.0) and roughness("Ra 3,2") == ("Ra", 3.2)


def test_users_value_and_tolerance_reach_the_drawing():
    from kompas_ai.pipeline import _apply_overrides

    d = ir.Drawing()
    d.entities = [ir.Dimension("D1", text="Ø23-0,2", nominal=23.0),
                  ir.Dimension("D2", text="M22×1,5", nominal=22.0),
                  ir.Text("T1", text="Rz 20 (√)")]
    _apply_overrides(d, {"D1": {"value": 24.0, "tol": "h11"}, "D2": 24.0,
                         "T1": {"text": "Ra 3,2 (√)"}})
    assert d.get("D1").text == "Ø24h11" and d.get("D1").nominal == 24.0
    assert d.get("D2").text == "M24×1,5"
    assert d.get("T1").text == "Ra 3,2 (√)"


def test_sizes_dialog_tolerance_and_roughness(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from kompas_ai.gui.refine import LIMITS_COLUMN, TOL_COLUMN, VALUE_COLUMN, RefineDialog

    QApplication.instance() or QApplication([])
    d = ir.Drawing()
    d.entities = [ir.Dimension("D1", text="Ø23-0,2", nominal=23.0, measured=23.0),
                  ir.Text("T1", text="Rz 20 (√)")]
    dialog = RefineDialog(d, {})
    assert dialog.table.item(0, TOL_COLUMN).text() == "-0,2"
    assert dialog.table.item(0, LIMITS_COLUMN).text() == "22,8 … 23"
    dialog.table.item(0, TOL_COLUMN).setText("h12")
    assert dialog.table.item(0, LIMITS_COLUMN).text() == "22,79 … 23"
    dialog.rough_table.item(0, 2).setText("Ra 6,3 (√)")
    dialog._apply()
    assert dialog.overrides == {"D1": {"value": None, "tol": "h12"}, "T1": {"text": "Ra 6,3 (√)"}}
    dialog = RefineDialog(d, {})
    dialog.table.selectRow(0)
    dialog.to_middle()
    assert dialog.table.item(0, VALUE_COLUMN).text() == "22,9"


def test_a_sketch_without_a_frame_is_centred_and_enlarged():
    from test_writer import FakeBackend

    from kompas_ai.kompas.writer import DrawingWriter

    d = ir.Drawing(sheet=ir.Sheet(format="custom", width=70, height=69),
                   scale=ir.Scale(value=1.0))
    d.entities = [ir.Line("L1", p1=(5, 10), p2=(60, 10)), ir.Line("L2", p1=(60, 10), p2=(60, 52)),
                  ir.Text("T1", text="Rz 20", position=(60, 60), height=1.4),
                  ir.Dimension("D1", text="55", nominal=55, measured=55, p1=(5, 10),
                               p2=(60, 10), line_point=(32.5, 5), orientation="horizontal")]
    b = FakeBackend(allow_view=True)
    report = DrawingWriter(b, mode="view").write(d)
    (origin, scale, _), = b.of("open_view")
    assert scale == 2.5 and any("2,5:1" in n for n in report.notes)
    # the outline in the middle of the A4 field, not in its corner
    xs = [origin[0] + x * scale for (p1, p2, _) in b.of("line") for x in (p1[0], p2[0])]
    assert 40 < min(xs) and max(xs) < 200 and abs((min(xs) + max(xs)) / 2 - 117.5) < 25


def test_a_drilled_hole_in_an_unhatched_view():
    """A turned part drawn without hatching, a Ø9 hole with a drill point:
    the hole is no material of the profile."""
    from kompas_ai.model3d.revolve import find_revolve_profile

    d = ir.Drawing(scale=ir.Scale(value=1.0))
    pts = [(0, 20), (60, 20), (60, 4.5), (30, 4.5), (27.4, 0)]
    lines = []
    for sign in (1, -1):
        ring = [(x, 50 + sign * y) for x, y in pts]
        lines += list(zip(ring, ring[1:]))
        lines += [((0, 50 + sign * 20), (0, 50)), ((60, 50 + sign * 4.5), (60, 50))]
    d.entities = [ir.Line(f"L{i}", p1=a, p2=b) for i, (a, b) in enumerate(lines, 1)]
    d.entities.append(ir.Line("L99", p1=(-5, 50), p2=(65, 50), style=ir.STYLE_AXIAL))
    p = find_revolve_profile(d)
    # along the axis from its start (x = -5 on the sheet)
    xs_on_axis = sorted(x - 5 for ring in p.rings for x, y in ring if abs(y) < 1e-6)
    assert any(abs(x - 27.4) < 0.1 for x in xs_on_axis)  # the drill point
    assert not any(abs(x - 60) < 0.1 for x in xs_on_axis)  # the hole open at the face
    assert math.isclose(max(y for ring in p.rings for _, y in ring), 20, abs_tol=1e-6)
