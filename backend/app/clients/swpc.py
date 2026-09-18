"""NOAA SWPC client: current space-weather scales (S/G/R) and active alert
messages. No API key required. These are the 'current obstanovka' signals
for the space-weather factor.
"""
from __future__ import annotations

from ..config import settings
from ..http import new_client


async def fetch_scales() -> dict:
    """noaa-scales.json: nested {"0": {...today...}, "1": {...+1d...}, ...},
    each day holding S/G/R sub-objects with a 'Scale' string ("0".."5") and
    descriptive text. Format is not formally versioned by NOAA, so all
    parsing downstream is defensive (missing keys tolerated)."""
    async with new_client() as client:
        resp = await client.get(settings.swpc_scales_url)
        resp.raise_for_status()
        return resp.json()


async def fetch_alerts() -> list[dict]:
    """alerts.json: list of {"product_id", "issue_datetime", "message"}.
    Includes active watches/warnings/alerts for geomagnetic storms, solar
    radiation storms and radio blackouts."""
    async with new_client() as client:
        resp = await client.get(settings.swpc_alerts_url)
        resp.raise_for_status()
        return resp.json()


async def fetch_kp_index() -> list[list]:
    """noaa-planetary-k-index.json: list of rows, first row is the header
    (e.g. ["time_tag","Kp","a_running","station_count"])."""
    async with new_client() as client:
        resp = await client.get(settings.swpc_kp_url)
        resp.raise_for_status()
        return resp.json()
