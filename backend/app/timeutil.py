"""Robust timestamp parsing for external sources.

Real-world bug this exists to fix: NOAA SWPC and NASA DONKI do not always
publish timestamps as strict ISO-8601 with an explicit offset (e.g. NOAA
alerts.json's `issue_datetime` commonly looks like
"2024-05-10 12:34:00.000 UTC" — space-separated, a literal "UTC" suffix,
no "+00:00" and no "Z"). `datetime.fromisoformat` either rejects that
outright or, for some near-ISO variants, happily returns a naive datetime.
A naive datetime then blows up the moment it is compared against one of our
own timezone-aware window boundaries (`TypeError: can't compare
offset-naive and offset-aware datetimes`).

Every source is documented UTC, so: try a few known shapes, and if the
result ends up naive, attach UTC rather than leaving it ambiguous.
"""
from __future__ import annotations

from datetime import datetime, timezone

_KNOWN_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


def parse_utc_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if text.upper().endswith("UTC"):
        text = text[:-3].strip()
    text = text.replace("Z", "+00:00")

    dt: datetime | None = None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        for fmt in _KNOWN_FORMATS:
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
