"""Criterion O3/T3: window comparison, recommendation, and correct handling
of the 'insufficient basis for a recommendation' case (never silently
defaulting to 'safe')."""
from datetime import datetime, timezone
from unittest.mock import patch

from app.analysis import compare_dates, run_analysis
from app.clients import celestrak, donki, swpc
from app.models import AnalyzeRequest, CompareDatesRequest, Mode
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


async def test_compare_dates_never_recommends_the_riskier_window_over_a_quiet_one():
    """Distinct from search_period_hours (which only compares start times
    clustered around ONE reference date): compares two entirely different
    dates against each other, reusing _recommend across their merged
    windows. Recommendation is time-localized, not date-wide — date A's own
    *other* window can legitimately still be exactly as quiet as date B's
    windows (a real DONKI signal issued at-or-before a historical cutoff can
    never reach a window starting a full duration_hours later, since its
    influence span is a fixed 30 minutes — see the comment below). So the
    one guarantee actually worth asserting is that the specific window whose
    time genuinely overlaps the hazard scores higher and is never the pick,
    not which exact tied-quiet window numerically wins."""
    date_a = datetime(2024, 5, 10, 6, 0, tzinfo=timezone.utc)  # first window overlaps a SEP event
    date_b = datetime(2024, 5, 20, 6, 0, tzinfo=timezone.utc)  # quiet

    async def fake_notifications(start, end, msg_type="all"):
        if start <= date_a.date() <= end:
            return [
                {
                    "messageType": "SEP",
                    # Must satisfy two constraints at once: issued no later
                    # than the cutoff (06:00, strict "forecast from the
                    # past") AND close enough before the compared window
                    # (06:00-08:00) that its default 30-minute signal span
                    # still overlaps it — 05:45 is issued 15 minutes before
                    # cutoff, whose [05:45, 06:15) span overlaps the window
                    # by 15 minutes.
                    "messageIssueTime": "2024-05-10T05:45Z",
                    "messageBody": "Severe SEP event",
                    "messageID": "SEP-A",
                }
            ]
        return []

    req = CompareDatesRequest(
        mode=Mode.historical,
        date_a=date_a,
        date_b=date_b,
        duration_hours=2.0,
        search_period_hours=0.0,
        step_minutes=60.0,
    )

    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(donki, "fetch_notifications", fake_notifications):
        resp = await compare_dates(req)

    assert resp.result_a.windows and resp.result_b.windows
    assert resp.overall_recommendation.has_recommendation is True

    risky_window = resp.result_a.windows[0]  # 06:00-08:00, overlaps the SEP event
    assert risky_window.combined_score is not None and risky_window.combined_score > 0.0

    picked_windows = resp.result_a.windows if resp.winning_date == "a" else resp.result_b.windows
    picked = picked_windows[resp.winning_window_index]
    assert picked.combined_score is not None
    assert picked.combined_score < risky_window.combined_score
    assert picked is not risky_window


async def test_compare_dates_shares_duration_and_settings_across_both_scenarios():
    date_a = datetime(2024, 5, 10, 6, 0, tzinfo=timezone.utc)
    date_b = datetime(2024, 5, 20, 6, 0, tzinfo=timezone.utc)

    async def fake_notifications(start, end, msg_type="all"):
        return []

    req = CompareDatesRequest(
        mode=Mode.historical, date_a=date_a, date_b=date_b,
        duration_hours=3.5, search_period_hours=0.0, step_minutes=60.0,
    )

    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(donki, "fetch_notifications", fake_notifications):
        resp = await compare_dates(req)

    assert resp.result_a.request.duration_hours == 3.5
    assert resp.result_b.request.duration_hours == 3.5
    assert resp.result_a.request.reference_time == date_a
    assert resp.result_b.request.reference_time == date_b
