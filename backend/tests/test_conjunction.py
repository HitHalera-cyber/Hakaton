from app.clients.celestrak import parse_socrates_for_norad
from app.factors.conjunction import _severity_from_event


SOCRATES_CSV = """NORAD_CAT_ID_1,NORAD_CAT_ID_2,TCA,MIN_RNG,MAX_PROB,SAT1_NAME,SAT2_NAME
25544,44444,2024-05-10 06:00:00,0.5,0.0002,ISS,DEBRIS A
25544,44444,2024-05-10 06:00:00,0.5,0.0002,ISS,DEBRIS A
99999,25544,2024-05-11 03:00:00,15.0,,OBJECT B,ISS
11111,22222,2024-05-10 06:00:00,0.1,0.001,OTHER,OTHER
"""


def test_parses_and_dedupes_events_for_target_norad():
    events = parse_socrates_for_norad(SOCRATES_CSV, 25544)
    assert len(events) == 2  # duplicate row collapsed, unrelated pair excluded
    others = {e["other_object"] for e in events}
    assert "DEBRIS A" in others
    assert "OBJECT B" in others


def test_severity_prefers_probability_when_available():
    assert _severity_from_event("50", "0.0002") == 1.0  # capped at 1.0 (well above 1e-4 reference)


def test_severity_falls_back_to_distance_bucket_without_probability():
    assert _severity_from_event("15", "") == 0.3
    assert _severity_from_event("0.5", "") == 0.9
    assert _severity_from_event("", "") == 0.2  # unknown geometry: low-confidence baseline, never zero
