"""Regression test: assess_current must not crash on real NOAA-style alert
timestamps without an explicit UTC offset (see tests/test_timeutil.py)."""
from datetime import datetime, timezone
from unittest.mock import patch

from app.clients import donki, swpc
from app.factors import space_weather


async def test_assess_current_handles_noaa_style_alert_timestamp():
    async def fake_scales():
        return {}

    async def fake_alerts():
        return [
            {
                "product_id": "ALTK08",
                "issue_datetime": "2024-05-10 06:00:00.000 UTC",  # no offset, like real NOAA data
                "message": "Geomagnetic storm alert",
            }
        ]

    async def fake_notifications(start, end, msg_type="all"):
        return []

    window_start = datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2024, 5, 10, 12, 0, tzinfo=timezone.utc)

    with patch.object(swpc, "fetch_scales", fake_scales), \
         patch.object(swpc, "fetch_alerts", fake_alerts), \
         patch.object(donki, "fetch_notifications", fake_notifications):
        result = await space_weather.assess_current(window_start, window_end, [], [])

    assert result.data_sufficient is True
    assert len(result.signals) == 1
    assert result.signals[0].published_at.tzinfo is not None


async def test_assess_current_includes_donki_as_independent_source():
    """DONKI must contribute its own signals in current mode too (not just
    historical replay), alongside — not instead of — NOAA SWPC."""
    async def fake_scales():
        return {}

    async def fake_alerts():
        return []

    async def fake_notifications(start, end, msg_type="all"):
        return [
            {
                "messageType": "SEP",
                "messageIssueTime": "2024-05-10T05:00Z",
                "messageBody": "Solar energetic particle event expected to persist.",
                "messageID": "SEP-1",
            }
        ]

    window_start = datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2024, 5, 10, 12, 0, tzinfo=timezone.utc)

    with patch.object(swpc, "fetch_scales", fake_scales), \
         patch.object(swpc, "fetch_alerts", fake_alerts), \
         patch.object(donki, "fetch_notifications", fake_notifications):
        result = await space_weather.assess_current(window_start, window_end, [], [])

    assert result.data_sufficient is True
    assert len(result.signals) == 1
    assert "DONKI" in result.signals[0].source_name
    assert result.signals[0].severity > 0


async def test_assess_current_donki_unavailable_does_not_block_swpc_signals():
    async def fake_scales():
        return {}

    async def fake_alerts():
        return [
            {
                "product_id": "ALTK08",
                "issue_datetime": "2024-05-10 06:00:00.000 UTC",
                "message": "Geomagnetic storm alert",
            }
        ]

    async def failing_notifications(start, end, msg_type="all"):
        raise ConnectionError("simulated DONKI outage")

    window_start = datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2024, 5, 10, 12, 0, tzinfo=timezone.utc)

    with patch.object(swpc, "fetch_scales", fake_scales), \
         patch.object(swpc, "fetch_alerts", fake_alerts), \
         patch.object(donki, "fetch_notifications", failing_notifications):
        result = await space_weather.assess_current(window_start, window_end, [], [])

    assert result.data_sufficient is True  # SWPC alert still counts as sufficient
    assert len(result.signals) == 1
    assert "DONKI недоступен" in result.notes


async def test_assess_current_deduplicates_repeated_donki_message_id():
    """T1: 'дубли сообщений' — the same messageID appearing twice in one
    DONKI response (e.g. an update re-issued under the same id) must count
    as one signal, not double the severity contribution."""
    async def fake_scales():
        return {}

    async def fake_alerts():
        return []

    async def fake_notifications(start, end, msg_type="all"):
        return [
            {
                "messageType": "SEP",
                "messageIssueTime": "2024-05-10T05:00Z",
                "messageBody": "Solar energetic particle event expected to persist.",
                "messageID": "SEP-DUP-1",
            },
            {
                "messageType": "SEP",
                "messageIssueTime": "2024-05-10T05:00Z",
                "messageBody": "Solar energetic particle event expected to persist.",
                "messageID": "SEP-DUP-1",
            },
        ]

    window_start = datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2024, 5, 10, 12, 0, tzinfo=timezone.utc)

    with patch.object(swpc, "fetch_scales", fake_scales), \
         patch.object(swpc, "fetch_alerts", fake_alerts), \
         patch.object(donki, "fetch_notifications", fake_notifications):
        result = await space_weather.assess_current(window_start, window_end, [], [])

    assert len(result.signals) == 1
