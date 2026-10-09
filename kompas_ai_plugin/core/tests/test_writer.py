"""Writer tests with a recording backend (no KOMPAS needed)."""

import math

from kompas_ai import ir
from kompas_ai.kompas.backend import LINEAR_HORIZONTAL, LINEAR_VERTICAL
from kompas_ai.kompas.writer import DrawingWriter
from kompas_ai.pipeline import recognize_pdf
from synthetic import plate_with_hole


class FakeBackend:
    def __init__(self, allow_view=False):
        self.calls = []
        self.allow_view = allow_view

    def __getattr__(self, name):
        def record(*args):
            self.calls.append((name, args))
            if name == "open_view":
                return self.allow_view
            return 1000 + len(self.calls)
        return record

    def of(self, name):
        return [args for n, args in self.calls if n == name]


def drawing_5_to_1():
    d = ir.Drawing(sheet=ir.Sheet(format="A3", orientation="landscape"),
                   scale=ir.Scale(value=5.0, text="5:1", source="title_block"))
    d.entities = [
        ir.Line("L1", p1=(10, 10), p2=(60, 10), style="main"),
        ir.Line("L2", p1=(35, 0), p2=(35, 40), style="axial"),
        ir.Circle("C1", center=(35, 20), radius=12.5),
        ir.Dimension("D1", dim_type="linear", text="Ø10", nominal=10, measured=50,
                     p1=(10, 10), p2=(60, 10), line_point=(35, 0), orientation="horizontal"),
        ir.Dimension("D2", dim_type="diameter", text="Ø5", nominal=5, measured=25,
                     p1=(35 + 12.5, 20), center=(35, 20), radius=12.5),
        ir.Dimension("D3", dim_type="angular", text="45°", nominal=45, measured=45.4,
                     p1=(80, 10), p2=(70 + 10 * math.cos(math.radians(45.4)), 10 + 10 * math.sin(math.radians(45.4))),
                     center=(70, 10), radius=20),
        ir.Hatch("H1", angle=45, spacing=2, contours=[[(0, 0), (5, 0), (5, 5), (0, 0)]]),
    ]
    return d


def test_sheet_mode_writes_values_by_hand():
    b = FakeBackend()
    report = DrawingWriter(b).write(drawing_5_to_1())
    assert b.of("new_sheet") == [(3, True)]
    assert b.of("line")[1][2] == 3  # axial style
    assert b.of("circle") == [((35, 20), 12.5, 1)]  # sheet mm, unscaled
    (p1, p2, offset, kind, text), = b.of("linear_dim")
    assert kind == LINEAR_HORIZONTAL and offset == (0.0, -10.0)
    assert not text.auto and text.value == "10" and text.diameter_sign
    (_, _, _, diameter, rtext), = b.of("radial_dim")
    assert diameter and rtext.value == "5"
    (_, a1, a2, _, atext), = b.of("angular_dim")
    # measured 45.4° is drawn as exactly 45° around the same bisector
    assert atext.auto and abs(a1 - 0.2) < 1e-6 and abs(a2 - 45.2) < 1e-6
    assert report.created == {"hatch": 1, "line": 2, "circle": 1, "dimension": 3}
    assert not report.failed


def test_view_mode_scales_geometry_and_uses_auto_values():
    b = FakeBackend(allow_view=True)
    report = DrawingWriter(b, mode="view").write(drawing_5_to_1())
    assert report.mode == "view"
    assert b.of("circle") == [((7.0, 4.0), 2.5, 1)]
    assert all(args[-1].auto for args in b.of("linear_dim"))


def test_view_refused_falls_back_to_sheet():
    b = FakeBackend(allow_view=False)
    report = DrawingWriter(b, mode="view").write(drawing_5_to_1())
    assert report.mode == "sheet" and report.notes
    assert b.of("circle") == [((35, 20), 12.5, 1)]


def test_recognised_pdf_is_written_completely(tmp_path):
    plate_with_hole(tmp_path / "plate.pdf")
    d = recognize_pdf(tmp_path / "plate.pdf")
    b = FakeBackend()
    report = DrawingWriter(b).write(d)
    assert not report.failed
    assert sum(report.created.values()) == len(d.entities)
    vertical = [a for a in b.of("linear_dim") if a[3] == LINEAR_VERTICAL]
    assert not vertical


def test_json_round_trip(tmp_path):
    plate_with_hole(tmp_path / "plate.pdf")
    d = recognize_pdf(tmp_path / "plate.pdf")
    d.save_json(tmp_path / "d.json")
    loaded = ir.Drawing.load_json(tmp_path / "d.json")
    assert [e.id for e in loaded.entities] == [e.id for e in d.entities]
    assert loaded.of_type(ir.Circle)[0].center == d.of_type(ir.Circle)[0].center


def test_indexed_text_falls_back_to_parts():
    class NoRich(FakeBackend):
        def rich_text(self, *args):
            raise NotImplementedError

    d = ir.Drawing()
    d.entities = [ir.Text("T1", text="pкав=3,38", position=(10, 10), height=5,
                          parts=[["p", "normal", 10, 10, 5], ["кав", "sub", 13, 9, 3.5],
                                 ["=3,38", "normal", 20, 10, 5]])]
    b = NoRich()
    report = DrawingWriter(b).write(d)
    assert [a[1] for a in b.of("text")] == ["p", "кав", "=3,38"]
    assert report.created == {"text": 1}

    rich = FakeBackend()
    DrawingWriter(rich).write(d)
    assert rich.of("rich_text")[0][1] == [("p", "normal"), ("кав", "sub"), ("=3,38", "normal")]


def test_index_item_sequence():
    """Order confirmed on KOMPAS v23 (prototype/api_test8.py, variant 3)."""
    from kompas_ai.kompas.api5 import index_items

    assert index_items([("P", "normal"), ("кав", "sub"), ("=3,38", "normal")]) == [
        ("P", 0), ("", 7), ("", 8), ("кав", 9), ("", 16), ("=3,38", 0)]
    assert index_items([("D", "normal"), ("2", "sup")]) == [
        ("D", 0), ("", 7), ("2", 8), ("", 9), ("", 16)]
