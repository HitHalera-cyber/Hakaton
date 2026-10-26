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


def test_shaft_section_end_view_and_sizes():
    """A body of revolution: the main view a section along the axis (hatched,
    no hidden lines), the end view beside it, the main sizes put on."""
    d, notes = model_drawing(revolve(SHAFT))
    s = d.scale.value
    assert axis_of_revolution(build_mesh(revolve(SHAFT))) is not None
    assert any("разрез по оси" in n for n in notes)
    assert d.of_type(ir.Hatch) and not [e for e in d.entities
                                        if getattr(e, "style", "") == ir.STYLE_DASHED]
    # the end view: Ø40, Ø30 and the bore Ø16 seen from the x = 0 end
    radii = sorted({round(c.radius / s, 1) for c in d.of_type(ir.Circle)})
    assert radii == [8.0, 15.0, 20.0]
    texts = sorted(x.text for x in d.of_type(ir.Dimension))
    for t in ("Ø16", "Ø24", "Ø30", "Ø40", "100", "30", "40"):
        assert t in texts, (t, texts)
    lines = d.of_type(ir.Line)
    assert any(l.style == "axial" and math.dist(l.p1, l.p2) > 100 * s for l in lines)


def test_a_part_turned_around_z_is_laid_along_its_axis():
    """The model's axis is Z (as KOMPAS parts often are): the main view still
    shows it lying, the section across its length."""
    m = revolve(SHAFT)[:, :, [1, 2, 0]]
    d, _ = model_drawing(m)
    s = d.scale.value
    hatch = d.of_type(ir.Hatch)
    xs = [p[0] for h in hatch for ring in h.contours for p in ring]
    ys = [p[1] for h in hatch for ring in h.contours for p in ring]
    assert abs((max(xs) - min(xs)) / s - 100) < 0.5 and abs((max(ys) - min(ys)) / s - 40) < 0.5


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
    assert len(backend.of("circle")) == 3 and backend.of("line") and backend.of("hatch")
    assert len(backend.of("linear_dim")) >= 7  # the diameters and the lengths
    assert "не связаны с моделью" in report
