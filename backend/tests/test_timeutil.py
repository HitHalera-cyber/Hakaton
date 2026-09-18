"""Regression test for a real bug hit against live NOAA data: alerts.json's
`issue_datetime` often has no explicit UTC offset (e.g. a trailing literal
"UTC" instead of "Z"/"+00:00"), which used to produce a naive datetime and
crash the moment it was compared against a timezone-aware window bound."""
from datetime import timezone

from app.timeutil import parse_utc_datetime


def test_parses_noaa_style_trailing_utc_suffix():
    dt = parse_utc_datetime("2024-05-10 12:34:00.000 UTC")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0
    assert dt.year == 2024 and dt.hour == 12 and dt.minute == 34


def test_parses_iso_with_z():
    dt = parse_utc_datetime("2024-05-10T12:34:00Z")
    assert dt.tzinfo is not None


def test_parses_iso_with_explicit_offset():
    dt = parse_utc_datetime("2024-05-10T12:34:00+00:00")
    assert dt.utcoffset() == timezone.utc.utcoffset(None)


def test_naive_iso_gets_utc_attached_not_left_naive():
    dt = parse_utc_datetime("2024-05-10T12:34:00")
    assert dt.tzinfo is not None


def test_none_and_empty_return_none():
    assert parse_utc_datetime(None) is None
    assert parse_utc_datetime("") is None


def test_unparseable_returns_none_instead_of_raising():
    assert parse_utc_datetime("not a date") is None
