from datetime import datetime, timezone
from unittest.mock import patch

from app.cache import SourceUnavailable
from app.clients import celestrak as celestrak_client, spacetrack
from app.clients.celestrak import parse_socrates_for_norad
from app.clients.spacetrack import parse_cdm_events
from app.config import settings
from app.factors import conjunction
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


def test_parse_cdm_events_matches_norad_and_converts_meters_to_km():
    """Field names come from a live modeldef call, never hardcoded — this
    test fixes one plausible real schema and checks both the discovery
    (via the regex candidates) and the meters->km unit conversion (the CDM
    spec documents MISS_DISTANCE in meters, unlike SOCRATES' own km field)."""
    payload = {
        "fields": {"TCA", "MISS_DISTANCE", "PC", "SAT_1_ID", "SAT_2_ID", "SAT_1_NAME", "SAT_2_NAME"},
        "rows": [
            {
                "TCA": "2024-05-10T06:00:00.000000",
                "MISS_DISTANCE": "437",  # meters
                "PC": "0.0002",
                "SAT_1_ID": "25544",
                "SAT_2_ID": "44444",
                "SAT_1_NAME": "ISS",
                "SAT_2_NAME": "DEBRIS A",
            },
            {
                # unrelated pair, must be excluded
                "TCA": "2024-05-10T07:00:00.000000",
                "MISS_DISTANCE": "1000",
                "PC": "",
                "SAT_1_ID": "11111",
                "SAT_2_ID": "22222",
                "SAT_1_NAME": "OTHER",
                "SAT_2_NAME": "OTHER",
            },
        ],
    }
    events = parse_cdm_events(payload, 25544)
    assert len(events) == 1
    ev = events[0]
    assert ev["other_object"] == "DEBRIS A"
    assert abs(ev["miss_distance_km"] - 0.437) < 1e-9


def test_parse_cdm_events_missing_fields_degrade_gracefully_not_fabricated():
    """If the live schema doesn't expose a field we recognize, that value
    must come back as None, never a guessed/fabricated number."""
    payload = {"fields": {"SAT_1_ID"}, "rows": [{"SAT_1_ID": "25544"}]}
    events = parse_cdm_events(payload, 25544)
    assert len(events) == 1
    assert events[0]["tca"] is None
    assert events[0]["miss_distance_km"] is None
    assert events[0]["max_probability"] is None


async def _failing_socrates():
    raise ConnectionError("simulated CelesTrak block")


async def test_assess_current_falls_back_to_spacetrack_cdm_when_socrates_fails():
    async def fake_cdm(norad_id, limit=50):
        return {
            "rows": [
                {
                    "TCA": "2024-05-10T06:00:00.000000",
                    "MISS_DISTANCE": "437",
                    "PC": "0.0002",
                    "SAT_1_ID": "25544",
                    "SAT_2_ID": "44444",
                    "SAT_1_NAME": "ISS",
                    "SAT_2_NAME": "DEBRIS A",
                }
            ],
            "fields": ["TCA", "MISS_DISTANCE", "PC", "SAT_1_ID", "SAT_2_ID", "SAT_1_NAME", "SAT_2_NAME"],
            "source_url": "https://www.space-track.org/basicspacedata/query/class/cdm_public/test",
        }

    window_start = datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2024, 5, 10, 12, 0, tzinfo=timezone.utc)

    with patch.object(settings, "spacetrack_identity", "test-user"), \
         patch.object(settings, "spacetrack_password", "test-pass"), \
         patch.object(celestrak_client, "fetch_socrates_csv", _failing_socrates), \
         patch.object(spacetrack, "fetch_cdm_conjunctions", fake_cdm):
        result = await conjunction.assess_current(window_start, window_end, [], [])

    assert result.data_sufficient is True
    assert len(result.signals) == 1
    assert "Space-Track" in result.signals[0].source_name
    assert "DEBRIS A" in result.signals[0].label


async def test_assess_current_without_spacetrack_credentials_reports_insufficient_data():
    window_start = datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2024, 5, 10, 12, 0, tzinfo=timezone.utc)

    with patch.object(settings, "spacetrack_identity", None), \
         patch.object(settings, "spacetrack_password", None), \
         patch.object(celestrak_client, "fetch_socrates_csv", _failing_socrates):
        result = await conjunction.assess_current(window_start, window_end, [], [])

    assert result.data_sufficient is False
    assert result.signals == []


async def test_assess_historical_without_credentials_reports_insufficient_data():
    cutoff = datetime(2024, 5, 10, 6, 0, tzinfo=timezone.utc)
    with patch.object(settings, "spacetrack_identity", None), \
         patch.object(settings, "spacetrack_password", None):
        result = await conjunction.assess_historical(cutoff, cutoff, cutoff.replace(hour=18))

    assert result.data_sufficient is False
    assert result.signals == []


async def test_assess_historical_uses_spacetrack_cdm_archive_within_cutoff():
    """Unlike SOCRATES, Space-Track's cdm_public keeps its full history, so
    with credentials configured a genuine past-forecast replay is possible
    for conjunctions too — this is the whole point of the new fallback."""
    cutoff = datetime(2024, 5, 10, 6, 0, tzinfo=timezone.utc)
    window_start = cutoff
    window_end = cutoff.replace(hour=18)

    async def fake_cdm_window(norad_id, cutoff_arg, limit=200):
        return {
            "rows": [
                {
                    "TCA": "2024-05-10T10:00:00.000000",  # inside the window
                    "MISS_DISTANCE": "437",
                    "PC": "0.0002",
                    "SAT_1_ID": "25544",
                    "SAT_2_ID": "44444",
                    "SAT_1_NAME": "ISS",
                    "SAT_2_NAME": "DEBRIS A",
                    "CREATION_DATE": "2024-05-09T00:00:00.000000",  # before cutoff
                },
            ],
            "fields": [
                "TCA", "MISS_DISTANCE", "PC", "SAT_1_ID", "SAT_2_ID",
                "SAT_1_NAME", "SAT_2_NAME", "CREATION_DATE",
            ],
            "source_url": "https://www.space-track.org/basicspacedata/query/class/cdm_public/test",
        }

    with patch.object(settings, "spacetrack_identity", "test-user"), \
         patch.object(settings, "spacetrack_password", "test-pass"), \
         patch.object(spacetrack, "fetch_cdm_conjunctions_for_window", fake_cdm_window):
        result = await conjunction.assess_historical(cutoff, window_start, window_end)

    assert result.data_sufficient is True
    assert len(result.signals) == 1
    assert "DEBRIS A" in result.signals[0].label
    assert "исторический архив" in result.signals[0].source_name
