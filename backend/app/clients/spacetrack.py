"""Optional Space-Track.org client for historical GP elements (GP_HISTORY).

Explicitly optional per the task statement ("источник не является
обязательным"). If EVA_SPACETRACK_IDENTITY/EVA_SPACETRACK_PASSWORD are not
configured, callers must treat historical orbit geometry as a documented
reconstruction using the nearest data actually available, never silently
substitute today's orbit for a past one.
"""
from __future__ import annotations

from datetime import datetime

from ..config import settings
from ..http import new_client


class SpaceTrackNotConfigured(Exception):
    pass


async def fetch_historical_tle(norad_id: int, at: datetime) -> dict:
    if not settings.spacetrack_identity or not settings.spacetrack_password:
        raise SpaceTrackNotConfigured("Space-Track credentials not configured")

    date_str = at.strftime("%Y-%m-%d")
    query = (
        f"{settings.spacetrack_query_url}/class/gp_history/NORAD_CAT_ID/{norad_id}"
        f"/EPOCH/%3C{date_str}/orderby/EPOCH%20desc/limit/1/format/json"
    )
    async with new_client() as client:
        login = await client.post(
            settings.spacetrack_login_url,
            data={
                "identity": settings.spacetrack_identity,
                "password": settings.spacetrack_password,
            },
        )
        login.raise_for_status()
        resp = await client.get(query)
        resp.raise_for_status()
        rows = resp.json()
    if not rows:
        raise ValueError(f"no GP_HISTORY records for NORAD {norad_id} before {date_str}")
    row = rows[0]
    return {
        "name": row.get("OBJECT_NAME", f"NORAD {norad_id}"),
        "line1": row["TLE_LINE1"],
        "line2": row["TLE_LINE2"],
        "epoch": row.get("EPOCH"),
        "creation_date": row.get("CREATION_DATE"),
        "source_url": settings.spacetrack_query_url,
    }
