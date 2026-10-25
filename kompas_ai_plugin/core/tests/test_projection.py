"""Views of a part drawn by the program from its mesh («Чертёж по модели»
when KOMPAS' linked views stay empty)."""

import math

from meshes import plate_with_hole, revolve, write_stl
from test_writer import FakeBackend

from kompas_ai import ir
from kompas_ai.gui.workers import _drawing_from_mesh
from kompas_ai.model3d.projection import axis_of_revolution, build_mesh, model_drawing, read_stl

SHAFT = [(0, 8), (0, 15), (30, 15), (30, 20), (70, 20), (70, 12), (100, 12), (100, 8)]


def _styles(d, cls):
    return [e for e in d.entities if isinstance(e, cls)]


def test_shaft_front_and_left_views_with_hidden_bore():
    d, notes = model_drawing(revolve(SHAFT))
    s = d.scale.value
    assert axis_of_revolution(build_mesh(revolve(SHAFT))) is not None
    assert any("вид сверху не нужен" in n for n in notes)
    circles = _styles(d, ir.Circle)
    # left view: Ø40, Ø30 and the bore Ø16 seen, Ø24 at the far end hidden
    radii = sorted((round(c.radius / s, 1), c.style) for c in circles)
    assert radii == [(8.0, "main"), (12.0, "dashed"), (15.0, "main"), (20.0, "main")]
    assert len({(round(c.center[0], 3), round(c.center[1], 3)) for c in circles}) == 1
    # front view: the bore dashed along the whole length, the axis through it
    lines = _styles(d, ir.Line)
    dashed = [l for l in lines if l.style == "dashed"]
    assert len(dashed) == 2 and all(abs(math.dist(l.p1, l.p2) - 100 * s) < 0.5 for l in dashed)
    assert any(l.style == "axial" and math.dist(l.p1, l.p2) > 100 * s for l in lines)
    steps = sorted(round(math.dist(l.p1, l.p2) / s, 1) for l in lines
                   if l.style == "main" and abs(l.p1[0] - l.p2[0]) < 1e-6)
    for height in (30.0, 40.0, 24.0):  # the shoulders, seen as vertical edges
        assert height in steps


def test_plate_with_hole_views(tmp_path):
    write_stl(tmp_path / "p.stl", plate_with_hole(80, 50, 10, 10))
    d, _ = model_drawing(read_stl(tmp_path / "p.stl"))
    s = d.scale.value
    circles = _styles(d, ir.Circle)
    assert [round(c.radius / s, 2) for c in circles] == [10.0]
    lines = _styles(d, ir.Line)
    lengths = sorted(round(math.dist(l.p1, l.p2) / s, 1) for l in lines if l.style == "main")
    assert lengths.count(80.0) >= 4 and lengths.count(50.0) >= 4  # front, top, left
    hidden = [l for l in lines if l.style == "dashed"]
    assert len(hidden) == 4 and all(abs(math.dist(l.p1, l.p2) / s - 10) < 0.2 for l in hidden)
    assert sum(1 for l in lines if l.style == "axial") == 2  # the hole's centre mark


def test_views_from_mesh_are_written_into_kompas(tmp_path):
    write_stl(tmp_path / "shaft.stl", revolve(SHAFT))
    backend = FakeBackend(allow_view=True)
    report = _drawing_from_mesh(backend, tmp_path / "shaft.m3d", tmp_path / "shaft.stl",
                                tmp_path / "shaft.cdw", None, lambda *_: None)
    assert backend.of("new_sheet") and backend.of("save")
    assert len(backend.of("circle")) == 4 and backend.of("line") and backend.of("arc")
    assert "не связаны с моделью" in report
