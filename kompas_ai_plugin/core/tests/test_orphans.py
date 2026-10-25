"""Sizes whose dimension line was not found: what they may measure, and a
dimension made of the user's choice."""

from kompas_ai import ir
from kompas_ai.gui.refine import questions
from kompas_ai.semantics.orphans import NOTE, apply, candidates, describe, key_of, parse


def _shaft():
    """A step of a shaft at 1:1 (Ø30 between y=85 and y=115), a Ø10 hole, and
    two numbers kept as text."""
    d = ir.Drawing(scale=ir.Scale(value=1.0))
    d.entities = [
        ir.Line("L1", p1=(50, 85), p2=(110, 85)),
        ir.Line("L2", p1=(50, 115), p2=(110, 115)),
        ir.Line("L3", p1=(50, 85), p2=(50, 115)),
        ir.Line("L4", p1=(110, 85), p2=(110, 115)),
        ir.Circle("C1", center=(150, 100), radius=5.0),
        ir.Text("T1", 0.6, [NOTE], text="Ø30-0,2", position=(75, 100), height=3.5),
        ir.Text("T2", 0.6, [NOTE], text="Ø10H7", position=(160, 108), height=3.5),
        ir.Text("T3", 0.6, [NOTE], text="60", position=(78, 120), height=3.5),
    ]
    return d


def test_parse_size_texts():
    assert parse("Ø23-0,2") == ("diameter", 23.0)
    assert parse("R5") == ("radius", 5.0)
    assert parse("M10x1,5") == ("diameter", 10.0)
    assert parse("45") == ("linear", 45.0)
    assert parse("30°")[0] == "angular"


def test_candidates_by_size_then_nearness():
    d = _shaft()
    c1 = candidates(d, d.get("T1"))
    assert c1 and c1[0]["kind"] == "linear" and sorted(c1[0]["refs"]) == ["L1", "L2"]
    c2 = candidates(d, d.get("T2"))
    assert c2[0]["kind"] == "diameter" and c2[0]["refs"] == ["C1"]
    c3 = candidates(d, d.get("T3"))
    assert any(sorted(c["refs"]) in (["L3", "L4"], ["L1"], ["L2"]) for c in c3)
    assert [o["id"] for o in describe(d)] == ["T1", "T2", "T3"]


def test_choices_make_dimensions_and_questions():
    d = _shaft()
    choice = key_of(candidates(d, d.get("T1"))[0])
    made, kept = apply(d, {"T1": choice, "T2": key_of(candidates(d, d.get("T2"))[0]), "T3": None})
    assert (made, kept) == (2, 1)
    dims = {x.text: x for x in d.of_type(ir.Dimension)}
    assert dims["Ø30-0,2"].nominal == 30 and dims["Ø30-0,2"].orientation == "vertical"
    assert abs(dims["Ø30-0,2"].measured - 30) < 1e-6
    assert dims["Ø10H7"].dim_type == "diameter" and dims["Ø10H7"].ref == "C1"
    assert d.get("T3") is not None and NOTE not in d.get("T3").notes
    d.orphans = describe(d)
    assert not [q for q in questions(d) if q.get("orphan")]


def test_unattached_numbers_are_asked_about():
    d = _shaft()
    d.orphans = describe(d)
    asked = [q for q in questions(d) if q.get("orphan")]
    assert [q["id"] for q in asked] == ["T1", "T2", "T3"]


def _pdf_with_a_lost_size(path, height=31.0):
    """A 60 × ``height`` outline (written Ø30 across it, arrows on both lines
    but no dimension line between them), a 60 dimension, a hole, a frame."""
    import pymupdf

    mm, H = 72 / 25.4, 297

    def P(x, y):
        return pymupdf.Point(x * mm, (H - y) * mm)

    doc = pymupdf.open()
    page = doc.new_page(width=210 * mm, height=297 * mm)
    sh = page.new_shape()
    top = 85 + height
    for poly in ([(50, 85), (110, 85), (110, top), (50, top), (50, 85)],
                 [(20, 5), (205, 5), (205, 292), (20, 292), (20, 5)]):
        for a, b in zip(poly, poly[1:]):
            sh.draw_line(P(*a), P(*b))
    sh.draw_circle(P(150, 100), 8 * mm)
    sh.finish(color=(0, 0, 0), width=0.5 * mm)
    sh.draw_line(P(50, 70), P(110, 70))
    sh.draw_line(P(50, 85), P(50, 68))
    sh.draw_line(P(110, 85), P(110, 68))
    sh.finish(color=(0, 0, 0), width=0.25 * mm)
    for (x, y), (dx, dy) in (((50, 70), (1, 0)), ((110, 70), (-1, 0)),
                             ((80, 85), (0, -1)), ((80, top), (0, 1))):
        tri = [P(x, y), P(x + 5 * dx - 0.9 * dy, y + 5 * dy - 0.9 * dx),
               P(x + 5 * dx + 0.9 * dy, y + 5 * dy + 0.9 * dx), P(x, y)]
        sh.draw_polyline(tri)
        sh.finish(color=(0, 0, 0), fill=(0, 0, 0), width=0.1)
    sh.commit()
    size = 3.5 / 0.684 / 25.4 * 72
    page.insert_text(P(76, 71.5), "60", fontsize=size, fontname="helv")
    page.insert_text(P(82, 98), "Ø30", fontsize=size, fontname="helv", rotate=90)
    doc.save(str(path))


def test_a_lost_size_attached_holds_on_the_next_recognition(tmp_path):
    from kompas_ai.pipeline import recognize_pdf

    pdf = tmp_path / "lost.pdf"
    _pdf_with_a_lost_size(pdf)
    d = recognize_pdf(pdf)
    lost = d.orphans
    assert [o["text"] for o in lost] == ["Ø30"]
    pick = lost[0]["candidates"][0]
    assert pick["kind"] == "linear" and abs(pick["measured"] - 31) < 0.05

    d2 = recognize_pdf(pdf, attach={lost[0]["id"]: key_of(pick)})
    dim = next(x for x in d2.of_type(ir.Dimension) if x.text == "Ø30")
    assert "привязан вручную" in dim.notes and not d2.orphans and not d2.issues
    sides = [abs(e.p1[1] - e.p2[1]) for e in d2.of_type(ir.Line)
             if e.style == ir.STYLE_MAIN and abs(e.p1[0] - e.p2[0]) < 1e-6 and 50 <= e.p1[0] <= 110]
    assert sides and all(abs(h - 30) < 1e-6 for h in sides)  # the outline follows Ø30
