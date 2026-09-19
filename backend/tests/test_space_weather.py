"""Criterion T4: strict publication-time cutoff for the historical
'forecast from the past' replay — later notifications must be excluded from
the calculation and only usable for separate verification."""
from datetime import datetime, timezone
from unittest.mock import patch

from app.clients import donki
from app.factors import space_weather


def _notif(msg_type, issue_iso, body="test"):
    return {"messageType": msg_type, "messageIssueTime": issue_iso, "messageBody": body, "messageID": issue_iso}


async def test_notifications_after_cutoff_are_excluded_from_calculation():
    cutoff = datetime(2024, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    notifications = [
        _notif("SEP", "2024-05-11T10:00Z"),  # before cutoff -> included
        _notif("GST", "2024-05-11T13:00Z"),  # after cutoff -> excluded
        _notif("SEP", "2024-05-12T00:00Z"),  # well after cutoff -> excluded
    ]

    async def fake_fetch(start, end, msg_type="all"):
        return notifications

    with patch.object(donki, "fetch_notifications", fake_fetch):
        result = await space_weather.assess_historical(
            cutoff, cutoff, cutoff.replace(hour=18)
        )

    included_times = [s.published_at for s in result.signals]
    assert all(t <= cutoff for t in included_times)
    assert len(result.signals) == 1  # only the SEP notification issued before cutoff
    assert "1 уведомлений" in result.notes or "учтено 1" in result.notes


async def test_historical_date_outside_supported_range_is_insufficient_data():
    from app.models import ConfidenceLevel

    cutoff = datetime(2023, 1, 1, tzinfo=timezone.utc)
    result = await space_weather.assess_historical(cutoff, cutoff, cutoff)
    assert result.data_sufficient is False
    assert result.overall_confidence == ConfidenceLevel.insufficient_data


async def test_verification_signals_are_not_used_in_calculation_but_available_separately():
    cutoff = datetime(2024, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    all_notifications = [
        _notif("SEP", "2024-05-11T10:00Z"),
        _notif("GST", "2024-05-11T15:00Z"),  # only visible in verification pass
    ]

    async def fake_fetch(start, end, msg_type="all"):
        return all_notifications

    with patch.object(donki, "fetch_notifications", fake_fetch):
        calc = await space_weather.assess_historical(cutoff, cutoff, cutoff.replace(hour=18))
        verify = await space_weather.verification_signals(cutoff, cutoff.replace(hour=18))

    assert len(calc.signals) == 1
    assert len(verify) == 2  # verification sees the full archive, unfiltered by cutoff


async def test_historical_deduplicates_repeated_donki_message_id():
    """T1: 'дубли сообщений' — a repeated messageID must not be counted twice."""
    cutoff = datetime(2024, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    notif = _notif("SEP", "2024-05-11T10:00Z")
    notifications = [notif, dict(notif)]  # same messageID appears twice

    async def fake_fetch(start, end, msg_type="all"):
        return notifications

    with patch.object(donki, "fetch_notifications", fake_fetch):
        result = await space_weather.assess_historical(cutoff, cutoff, cutoff.replace(hour=18))

    assert len(result.signals) == 1
    assert "дублей" in result.notes
