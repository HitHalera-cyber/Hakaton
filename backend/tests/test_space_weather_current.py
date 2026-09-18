"""Regression test: assess_current must not crash on real NOAA-style alert
timestamps without an explicit UTC offset (see tests/test_timeutil.py)."""
from datetime import datetime, timezone
from unittest.mock import patch

from app.clients import swpc
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

    window_start = datetime(2024, 5, 10, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2024, 5, 10, 12, 0, tzinfo=timezone.utc)

    with patch.object(swpc, "fetch_scales", fake_scales), \
         patch.object(swpc, "fetch_alerts", fake_alerts):
        result = await space_weather.assess_current(window_start, window_end, [], [])

    assert result.data_sufficient is True
    assert len(result.signals) == 1
    assert result.signals[0].published_at.tzinfo is not None
