import pytest

from kompas_ai.geometry.scaling import check_dimension, resolve_scale, snap_scale
from kompas_ai.ir import Scale
from kompas_ai.pdf.vector_extractor import RawText, merge_text_runs
from kompas_ai.semantics.dimensions import parse_dim_text


def raw(text, origin=(0.0, 0.0), angle=0.0):
    return RawText(text, origin, angle, 5.0, "GOSTTypeA",
                   (origin[0], origin[1], origin[0] + 3, origin[1] + 5), origin)


def test_parse_dim_texts():
    d = parse_dim_text(raw("Ø2,68"))
    assert (d.prefix, d.value, d.decimals, d.angular) == ("Ø", 2.68, 2, False)
    assert parse_dim_text(raw("45°")).angular
    assert parse_dim_text(raw("R10")).prefix == "R"
    assert parse_dim_text(raw("120 ±0,1")).tail == "±0,1"
    assert parse_dim_text(raw("Изм.")) is None
    d = parse_dim_text(raw("37°57'"))
    assert d.angular and abs(d.value - 37.95) < 1e-9
    # labels of vectors and graph captions are not dimensions
    for text in ("2u", "1m", "2uср", "130 R, мм", "68,94 50,92"):
        assert parse_dim_text(raw(text)) is None
    assert parse_dim_text(raw("Ø20H7")).tail == "H7"


def test_merge_symbol_and_value():
    merged = merge_text_runs([raw("Ø", (10.0, 0.0)), raw("2,68", (13.4, 0.0))])
    assert [t.text for t in merged] == ["Ø2,68"]


def test_scale_from_dimensions_and_conflict():
    s = resolve_scale(Scale(), [5.01, 4.99, 5.0])
    assert s.value == 5.0 and s.text == "5:1" and s.source == "dimensions"
    s = resolve_scale(Scale(value=1.0, text="1:1", source="title_block"), [2.0, 2.0])
    assert s.conflicts  # title says 1:1, dimensions say 2:1
    assert snap_scale(0.502) == 0.5


def test_dimension_check():
    assert check_dimension("linear", 23.283, 4.67, 2, 5.0).ok
    assert not check_dimension("linear", 30.0, 4.67, 2, 5.0).ok


@pytest.mark.parametrize("text,count,prefix,value", [
    ("6 отв. Ø18", 6, "Ø", 18.0), ("2×Ø8", 2, "Ø", 8.0), ("4 holes Ø9", 4, "Ø", 9.0),
    ("3xM6", 3, "M", 6.0), ("Ø20", 1, "Ø", 20.0)])
def test_hole_count_dimension_text(text, count, prefix, value):
    d = parse_dim_text(RawText(text, (0, 0), 0.0, 3.5, "f", (0, 0, 1, 1)))
    assert (d.count, d.prefix, d.value) == (count, prefix, value)


def test_chamfer_text_is_not_a_hole_count():
    d = parse_dim_text(RawText("2×45°", (0, 0), 0.0, 3.5, "f", (0, 0, 1, 1)))
    assert d.count == 1 and d.value == 2.0 and d.tail == "×45°"
