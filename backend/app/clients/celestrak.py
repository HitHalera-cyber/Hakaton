"""CelesTrak client: current GP (TLE) elements for the ISS, and the SOCRATES
conjunction report used by the MMOD/conjunction factor.

CelesTrak requires no API key. GP_HISTORY (authenticated Space-Track archive)
is handled separately in spacetrack.py since it is explicitly optional per
the task statement.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from ..config import settings
from ..http import new_client


@dataclass
class TleRecord:
    name: str
    line1: str
    line2: str
    source_url: str


async def fetch_current_tle(norad_id: int | None = None) -> dict:
    norad_id = norad_id or settings.iss_norad_id
    url = f"{settings.celestrak_gp_url}?CATNR={norad_id}&FORMAT=TLE"
    async with new_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text.strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        raise ValueError(f"unexpected CelesTrak TLE response ({len(lines)} lines)")
    return {"name": lines[0].strip(), "line1": lines[1], "line2": lines[2], "source_url": url}


async def fetch_socrates_csv() -> str:
    """Fetches the CelesTrak SOCRATES 'limited to 7 days' conjunction report
    as raw CSV text (cached upstream by SourceCache); parsing is done by the
    conjunction factor module so the cache stores the rawest usable form."""
    async with new_client() as client:
        resp = await client.get(settings.celestrak_socrates_url)
        resp.raise_for_status()
        return resp.text


def parse_socrates_for_norad(csv_text: str, norad_id: int) -> list[dict]:
    """Returns conjunction events where either object matches norad_id.
    SOCRATES columns vary slightly between CelesTrak's published variants;
    we match case-insensitively on a set of known header spellings and skip
    unparseable rows rather than raising, since this is a best-effort public
    report (T1: удаление дублей/устойчивость к формату)."""
    reader = csv.DictReader(io.StringIO(csv_text))
    events: list[dict] = []
    seen = set()
    for row in reader:
        norm = {k.strip().upper(): (v or "").strip() for k, v in row.items() if k}
        norad1 = norm.get("NORAD_CAT_ID_1") or norm.get("SAT1_OBJECT_ID") or norm.get("NORAD1")
        norad2 = norm.get("NORAD_CAT_ID_2") or norm.get("SAT2_OBJECT_ID") or norm.get("NORAD2")
        if str(norad_id) not in {norad1, norad2}:
            continue
        tca = norm.get("TCA") or norm.get("TIME_OF_CLOSEST_APPROACH")
        miss_km = norm.get("MIN_RNG") or norm.get("MISS_DISTANCE_KM") or norm.get("RANGE")
        max_prob = norm.get("MAX_PROB") or norm.get("MAXIMUM_PROBABILITY") or norm.get("PROBABILITY")
        # Pick the *other* object's name, not the ISS's own.
        other_name = norm.get("SAT2_NAME") if norad1 == str(norad_id) else norm.get("SAT1_NAME")
        other_name = other_name or "неизвестный объект"
        dedup_key = (tca, miss_km, other_name)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        events.append(
            {
                "tca": tca,
                "miss_distance_km": miss_km,
                "max_probability": max_prob,
                "other_object": other_name,
            }
        )
    return events
