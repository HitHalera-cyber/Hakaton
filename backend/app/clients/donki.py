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


class DonkiRateLimited(Exception):
    """Raised specifically for NASA's 429, with guidance tailored to
    whether it was the shared DEMO_KEY or a personal key: DEMO_KEY's low
    hourly quota is shared across every anonymous api.nasa.gov user at
    once, not just this deployment, so it can be exhausted by traffic that
    has nothing to do with this site — a personal key (free, instant,
    email-only signup) fixes it completely."""


async def _get_or_raise(client, url: str):
    resp = await client.get(url)
    if resp.status_code == 429:
        if settings.nasa_api_key == "DEMO_KEY":
            raise DonkiRateLimited(
                "превышен лимит общего DEMO_KEY (его делят между собой все анонимные "
                "пользователи api.nasa.gov, а не только этот сайт) — получите бесплатный "
                "личный ключ на api.nasa.gov (мгновенно, нужен только email) и укажите "
                "его в переменной EVA_NASA_API_KEY"
            )
        raise DonkiRateLimited("превышен лимит запросов для настроенного личного ключа NASA API")
    resp.raise_for_status()
    return resp


async def fetch_notifications(start: date, end: date, msg_type: str = "all") -> list[dict]:
    url = (
        f"{settings.donki_base_url}/notifications"
        f"?startDate={start.isoformat()}&endDate={end.isoformat()}"
        f"&type={msg_type}&api_key={settings.nasa_api_key}"
    )
    async with new_client() as client:
        resp = await _get_or_raise(client, url)
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
        resp = await _get_or_raise(client, url)
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
        resp = await _get_or_raise(client, url)
        return resp.json()
