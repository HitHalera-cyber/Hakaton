"""Criterion O3/T3: window comparison, recommendation, and correct handling
of the 'insufficient basis for a recommendation' case (never silently
defaulting to 'safe')."""
from datetime import datetime, timedelta, timezone
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


async def test_conjunction_signal_contributes_to_window_score():
    """Regression: a conjunction event's TCA is a single instant. The
    window-overlap scoring computes overlap as
    min(signal_end,window_end) - max(signal_start,window_start); a
    zero-width [tca, tca] "span" (observed_or_expected_end set to tca
    itself) always evaluates to exactly zero overlap minutes with ANY
    window, even one that fully contains tca — silently dropping every
    conjunction signal's contribution to combined_score, in every window,
    always. Fixed by leaving observed_or_expected_end unset so the same
    default-span fallback DONKI/NOAA-alert signals already use applies
    here too (see conjunction.py)."""
    socrates_csv = (
        "NORAD_CAT_ID_1,NORAD_CAT_ID_2,TCA,MIN_RNG,MAX_PROB,SAT1_NAME,SAT2_NAME\n"
        "25544,44444,2026-01-01 01:00:00,0.3,0.0005,ISS,DEBRIS A\n"
    )

    async def fake_socrates():
        return socrates_csv

    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(swpc, "fetch_scales", _fake_scales_quiet), \
         patch.object(swpc, "fetch_alerts", _fake_alerts_empty), \
         patch.object(celestrak, "fetch_socrates_csv", fake_socrates):
        resp = await run_analysis(_base_request(search_period_hours=0.0))

    hit = resp.windows[0]  # covers 2026-01-01T00:00-02:00; TCA 01:00 falls inside
    assert hit.combined_score is not None and hit.combined_score > 0.0
    conj = next(c for c in hit.factor_contributions if c.factor.value == "conjunction_mmod")
    assert conj.time_weighted_severity > 0.0
    assert conj.driving_signals


async def test_donki_signal_scores_nearby_windows_but_not_ones_far_beyond_the_horizon():
    """Regression: DONKI notifications also had no explicit
    observed_or_expected_end, so they fell back to the same 30-minute
    default span — far shorter than how long a real solar/geomagnetic
    event's elevated-risk period actually lasts. A user comparing windows
    across a wide search period (e.g. the default 12h) would see every
    window past the first one or two read as "0 risk", which looked
    exactly like "verified safe" even though it really meant "beyond our
    signal's reach". Widened to settings.forecast_horizon_hours (6h,
    already an established project constant) — this test checks BOTH ends:
    a window close to the event must now score it, and a window genuinely
    far beyond any reasonable forecast horizon must still honestly show no
    contribution (not a fabricated score)."""
    async def fake_notifications(start, end, msg_type="all"):
        return [
            {
                "messageType": "RBE",
                "messageIssueTime": "2024-05-10T00:00Z",
                "messageBody": "test radio blackout event",
                "messageID": "RBE-1",
            }
        ]

    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(swpc, "fetch_scales", _fake_scales_quiet), \
         patch.object(swpc, "fetch_alerts", _fake_alerts_empty), \
         patch.object(celestrak, "fetch_socrates_csv", _fake_socrates_empty), \
         patch.object(donki, "fetch_notifications", fake_notifications):
        resp = await run_analysis(_base_request(
            mode=Mode.historical,
            reference_time=datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc),  # within the supported historical range
            duration_hours=4.0, search_period_hours=24.0, step_minutes=120.0,
        ))

    # windows step every 2h starting at cutoff (00:00): #0=00:00-04:00,
    # #1=02:00-06:00, #2=04:00-08:00, ... The event is issued at 00:00, so
    # window #0 would overlap it even under the OLD 30-minute-default span
    # (it starts exactly when the event does) — that wouldn't distinguish
    # old from new behavior. Window #2 (starts 4h after the event) is the
    # one that only the new 6h-wide span reaches; the old 30-minute default
    # would show zero overlap with it.
    near_window = resp.windows[2]  # 04:00-08:00: inside the new 6h horizon, outside the old 30-min one
    assert near_window.combined_score is not None and near_window.combined_score > 0.0

    far_window = resp.windows[-1]  # starts 24h after the event, well beyond 6h
    assert far_window.combined_score == 0.0


async def test_donki_old_notification_still_scores_todays_window_in_current_mode():
    """Regression: assess_current deliberately looks back up to 7 days for
    DONKI notifications ("still describing an ongoing/expected event" —
    see the comment above donki_query_start), but a notification's scoring
    span used to be tied only to issued+forecast_horizon_hours. A
    notification issued, say, 3 days ago had already "expired" for scoring
    purposes long before today's candidate windows — it still showed up
    with real severity in the factors list while silently never
    contributing to any window's score (reported live: 7 real DONKI
    signals shown, every window still 0.00). Fixed by anchoring the
    signal's end to max(issued, now) + forecast_horizon_hours, so a
    notification still being surfaced as relevant context stays
    scoring-relevant through the near-term future from "now" — see
    test_donki_far_future_window_still_shows_zero_not_a_uniform_blanket
    for why this is anchored to "now" and not the whole compared range."""
    now = datetime.now(timezone.utc)
    issued_3_days_ago = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%MZ")

    async def fake_notifications(start, end, msg_type="all"):
        return [
            {
                "messageType": "CME",
                "messageIssueTime": issued_3_days_ago,
                "messageBody": "test coronal mass ejection",
                "messageID": "CME-1",
            }
        ]

    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(swpc, "fetch_scales", _fake_scales_quiet), \
         patch.object(swpc, "fetch_alerts", _fake_alerts_empty), \
         patch.object(celestrak, "fetch_socrates_csv", _fake_socrates_empty), \
         patch.object(donki, "fetch_notifications", fake_notifications):
        resp = await run_analysis(_base_request(reference_time=now, duration_hours=4.0, search_period_hours=0.0))

    hit = resp.windows[0]
    assert hit.combined_score is not None and hit.combined_score > 0.0


async def test_donki_far_future_window_still_shows_zero_not_a_uniform_blanket():
    """Regression on the FIRST attempted fix for the bug above: extending a
    signal's end to window_end (the far edge of the WHOLE compared range)
    blanketed every compared window with the identical severity, collapsing
    a wide comparison to one flat number — reported live as a flat/empty-
    looking chart and an unclear "best window" pick, since everything was
    tied. Anchoring to "now" instead means a window far enough into the
    future (beyond the forecast horizon from now) must still honestly show
    no contribution from an old notification, preserving real
    differentiation between near and far windows."""
    now = datetime.now(timezone.utc)
    issued_3_days_ago = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%MZ")

    async def fake_notifications(start, end, msg_type="all"):
        return [
            {
                "messageType": "CME",
                "messageIssueTime": issued_3_days_ago,
                "messageBody": "test coronal mass ejection",
                "messageID": "CME-1",
            }
        ]

    with patch.object(celestrak, "fetch_current_tle", _fake_tle), \
         patch.object(swpc, "fetch_scales", _fake_scales_quiet), \
         patch.object(swpc, "fetch_alerts", _fake_alerts_empty), \
         patch.object(celestrak, "fetch_socrates_csv", _fake_socrates_empty), \
         patch.object(donki, "fetch_notifications", fake_notifications):
        resp = await run_analysis(_base_request(
            reference_time=now, duration_hours=4.0, search_period_hours=18.0, step_minutes=60.0,
        ))

    near_window = resp.windows[0]  # starts at "now", well within the forecast horizon
    far_window = resp.windows[-1]  # starts ~18h from "now", well beyond it
    assert near_window.combined_score is not None and near_window.combined_score > 0.0
    assert far_window.combined_score == 0.0
    assert far_window.combined_score != near_window.combined_score


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
