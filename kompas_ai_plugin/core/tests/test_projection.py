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
    """A part that is no body of revolution: no hidden lines; the side views
    are sections through the hole, hatched, the planes marked on the main
    view; the overall sizes and the hole's diameter."""
    write_stl(tmp_path / "p.stl", plate_with_hole(80, 50, 10, 10))
    d, notes = model_drawing(read_stl(tmp_path / "p.stl"))
    s = d.scale.value
    assert not [e for e in d.entities if getattr(e, "style", "") == ir.STYLE_DASHED]
    assert [round(c.radius / s, 2) for c in d.of_type(ir.Circle)] == [10.0]
    assert any("разрезы А-А, Б-Б" in n for n in notes)
    # two sections, each the plate cut through the hole: two hatched pieces
    assert len(d.of_type(ir.Hatch)) == 4
    labels = {t.text for t in d.of_type(ir.Text)}
    assert {"А-А", "Б-Б", "А", "Б"} <= labels
    texts = sorted(x.text for x in d.of_type(ir.Dimension))
    assert "80" in texts and "50" in texts and "Ø20" in texts


def test_views_from_mesh_are_written_into_kompas(tmp_path):
    write_stl(tmp_path / "shaft.stl", revolve(SHAFT))
    backend = FakeBackend(allow_view=True)
    report = _drawing_from_mesh(backend, tmp_path / "shaft.m3d", tmp_path / "shaft.stl",
                                tmp_path / "shaft.cdw", None, lambda *_: None)
    assert backend.of("new_sheet") and backend.of("save")
    assert len(backend.of("circle")) == 3 and backend.of("line") and backend.of("hatch")
    assert len(backend.of("linear_dim")) >= 7  # the diameters and the lengths
    assert "не связаны с моделью" in report


def test_hole_positions_and_a_bolt_circle():
    """Holes of the main view placed from the biggest hole's centre; equal
    holes round a boss get its pitch circle and diameter, not positions."""
    from kompas_ai.model3d.projection import _hole_positions

    s = 0.5
    holes = [ir.Circle("C1", center=(100, 100), radius=26), ir.Circle("C2", center=(157.5, 126), radius=12.5),
             ir.Circle("C3", center=(127.5, 120), radius=2.5)]
    holes += [ir.Circle(f"B{k}", center=(157.5 + 9 * math.cos(a), 126 + 9 * math.sin(a)), radius=1.0)
              for k, a in enumerate((0.785, 2.356, 3.927, 5.498))]
    holes.sort(key=lambda e: -e.radius)
    out = _hole_positions(holes, s, 1)
    pitch = [e for e in out if isinstance(e, ir.Circle)]
    assert len(pitch) == 1 and abs(pitch[0].radius - 9) < 1e-6 and pitch[0].style == ir.STYLE_AXIAL
    texts = sorted(e.text for e in out if isinstance(e, ir.Dimension))
    assert texts == sorted(["Ø36", "115", "52", "55", "40"])  # radius 9 on the sheet at 1:2
