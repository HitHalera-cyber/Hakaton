"""NASA DONKI client: historical/dated space-weather notifications and
events (GST geomagnetic storms, SEP solar energetic particle events, FLR
flares, CME). Works with the free DEMO_KEY (low rate limit) or a configured
personal key.

Each DONKI notification carries `messageIssueTime`, which is what makes the
strict "forecast from the past" replay mode (criterion T4) possible: we can
filter to only notifications issued at-or-before an arbitrary historical
cutoff instant, and separately fetch the full range for after-the-fact
verification.
"""
from __future__ import annotations

from datetime import date

from ..config import settings
from ..http import new_client


async def fetch_notifications(start: date, end: date, msg_type: str = "all") -> list[dict]:
    url = (
        f"{settings.donki_base_url}/notifications"
        f"?startDate={start.isoformat()}&endDate={end.isoformat()}"
        f"&type={msg_type}&api_key={settings.nasa_api_key}"
    )
    async with new_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def fetch_gst(start: date, end: date) -> list[dict]:
    """Geomagnetic Storm events, each with linked Kp-index sub-records and
    per-record observedTime/kpIndex — the closest DONKI equivalent to an
    archived, dated geomagnetic assessment."""
    url = (
        f"{settings.donki_base_url}/GST"
        f"?startDate={start.isoformat()}&endDate={end.isoformat()}"
        f"&api_key={settings.nasa_api_key}"
    )
    async with new_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def fetch_sep(start: date, end: date) -> list[dict]:
    """Solar Energetic Particle events — the primary driver of increased EVA
    radiation risk from space weather."""
    url = (
        f"{settings.donki_base_url}/SEP"
        f"?startDate={start.isoformat()}&endDate={end.isoformat()}"
        f"&api_key={settings.nasa_api_key}"
    )
    async with new_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
