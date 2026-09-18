"""Criterion O3/T3: window comparison, recommendation, and correct handling
of the 'insufficient basis for a recommendation' case (never silently
defaulting to 'safe')."""
from datetime import datetime, timezone
from unittest.mock import patch

from app.analysis import run_analysis
from app.clients import celestrak, swpc
from app.models import AnalyzeRequest, Mode
from .conftest import SAMPLE_TLE


async def _fake_tle(norad_id=None):
    return SAMPLE_TLE


async def _fake_scales_quiet():
    return {"0": {"S": {"Scale": "0"}, "G": {"Scale": "0"}, "R": {"Scale": "0"}}}


async def _fake_alerts_empty():
    return []


async def _fake_socrates_empty():
    return ""


def _base_request(**overrides):
    defaults = dict(
        mode=Mode.current,
        reference_time=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        search_period_hours=0.0,
        step_minutes=60.0,
    )
    defaults.update(overrides)
    return AnalyzeRequest(**defaults)


async def test_at_least_two_windows_even_with_zero_search_period():
    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(swpc, "fetch_scales", _fake_scales_quiet), \
         patch.object(swpc, "fetch_alerts", _fake_alerts_empty), \
         patch.object(celestrak, "fetch_socrates_csv", _fake_socrates_empty):
        resp = await run_analysis(_base_request(search_period_hours=0.0))
    assert len(resp.windows) >= 2
    durations = {round(w.duration_hours, 3) for w in resp.windows}
    assert durations == {2.0}  # all compared windows share the same duration


async def test_all_sources_failing_yields_no_false_safe_recommendation():
    async def boom(*a, **kw):
        raise RuntimeError("source down")

    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(swpc, "fetch_scales", boom), \
         patch.object(swpc, "fetch_alerts", boom), \
         patch.object(celestrak, "fetch_socrates_csv", boom):
        resp = await run_analysis(_base_request(search_period_hours=3.0))

    assert resp.recommendation.has_recommendation is False
    for w in resp.windows:
        assert w.combined_score is None


async def test_recommendation_prefers_lower_risk_window():
    call_count = {"n": 0}

    async def variable_scales():
        # First call (earlier window) is stormy, later calls are quiet —
        # simulates a real severity gradient across compared windows by
        # varying what "today" looks like is not directly controllable here,
        # so instead we drive severity via alerts timing below.
        return {"0": {"S": {"Scale": "0"}, "G": {"Scale": "0"}, "R": {"Scale": "0"}}}

    async def alerts_with_one_early_storm():
        return [
            {
                "product_id": "ALTS03",
                "issue_datetime": "2026-01-01T00:15:00Z",
                "message": "Strong event near reference time",
            }
        ]

    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(swpc, "fetch_scales", variable_scales), \
         patch.object(swpc, "fetch_alerts", alerts_with_one_early_storm), \
         patch.object(celestrak, "fetch_socrates_csv", _fake_socrates_empty):
        resp = await run_analysis(_base_request(search_period_hours=6.0, step_minutes=60.0))

    assert resp.recommendation.has_recommendation is True
    rec_idx = resp.recommendation.recommended_window_index
    rec_window = resp.windows[rec_idx]
    # the recommended window's score must be the minimum among all scored windows
    scored = [w.combined_score for w in resp.windows if w.combined_score is not None]
    assert rec_window.combined_score == min(scored)
