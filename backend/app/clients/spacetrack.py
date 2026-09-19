"""Optional Space-Track.org client for GP elements — both the current
catalog ("gp" class) and historical archive ("gp_history").

Explicitly optional per the task statement ("источник не является
обязательным"). Space-Track is run by the 18th Space Defense Squadron on
different infrastructure/policy than CelesTrak; it exists here both for
the historical mode (where it's the only source of genuinely dated
elements) and as an automatic fallback for the *current* mode when
CelesTrak itself is unreachable (observed in practice: some cloud hosts,
including some free-tier PaaS, have their outbound traffic to
celestrak.org blocked or rate-limited — see README). If credentials are
not configured, callers must treat historical orbit geometry as a
documented reconstruction using the nearest data actually available,
never silently substitute today's orbit for a past one; for current mode,
callers must not treat a missing Space-Track fallback as an error by
itself — CelesTrak remains the primary, working source for most
deployments.
"""
from __future__ import annotations

from datetime import datetime

from ..config import settings
from ..http import new_client


class SpaceTrackNotConfigured(Exception):
    pass


def _row_to_gp(row: dict) -> dict:
    return {
        "name": row.get("OBJECT_NAME", "unknown"),
        "line1": row["TLE_LINE1"],
        "line2": row["TLE_LINE2"],
        "epoch": row.get("EPOCH"),
        "creation_date": row.get("CREATION_DATE"),
        "source_url": settings.spacetrack_query_url,
    }


async def _login_and_query(query_path: str) -> list[dict]:
    if not settings.spacetrack_identity or not settings.spacetrack_password:
        raise SpaceTrackNotConfigured("Space-Track credentials not configured")

    async with new_client() as client:
        login = await client.post(
            settings.spacetrack_login_url,
            data={
                "identity": settings.spacetrack_identity,
                "password": settings.spacetrack_password,
            },
        )
        login.raise_for_status()
        resp = await client.get(f"{settings.spacetrack_query_url}/{query_path}")
        resp.raise_for_status()
        return resp.json()


async def fetch_historical_tle(norad_id: int, at: datetime) -> dict:
    date_str = at.strftime("%Y-%m-%d")
    rows = await _login_and_query(
        f"class/gp_history/NORAD_CAT_ID/{norad_id}/EPOCH/%3C{date_str}/orderby/EPOCH%20desc/limit/1/format/json"
    )
    if not rows:
        raise ValueError(f"no GP_HISTORY records for NORAD {norad_id} before {date_str}")
    return _row_to_gp(rows[0])


async def fetch_current_tle(norad_id: int) -> dict:
    """Latest available elements from Space-Track's live "gp" class — used
    as a fallback for current-mode orbit when CelesTrak itself is
    unreachable, not as the primary source (CelesTrak needs no account and
    is preferred whenever it works)."""
    rows = await _login_and_query(f"class/gp/NORAD_CAT_ID/{norad_id}/orderby/EPOCH%20desc/limit/1/format/json")
    if not rows:
        raise ValueError(f"no GP records for NORAD {norad_id}")
    return _row_to_gp(rows[0])
