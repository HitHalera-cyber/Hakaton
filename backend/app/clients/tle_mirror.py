"""Fallback GP/TLE source: a community-maintained GitHub mirror of
CelesTrak's own element sets (github.com/caelo-works/tle-mirror), refreshed
every ~8 hours by a scheduled GitHub Action and served over
raw.githubusercontent.com.

This is deliberately NOT an independent measurement — it just re-publishes
CelesTrak's own data, so it doesn't count as a second corroborating source
in the data-provenance sense (per the task's own "два сайта, перепечатывающих
одно измерение, не считаются независимым подтверждением"). It exists purely
as a reachability bridge: GitHub's raw-content CDN is orders of magnitude
harder to end up blocked/rate-limited on than a small volunteer-run site
like celestrak.org, which is exactly the failure mode this project has hit
in practice on at least one deployment. Staleness (up to ~8h) is honestly
surfaced via the normal OrbitInfo.age_hours field — never hidden.
"""
from __future__ import annotations

from ..config import settings
from ..http import new_client


async def fetch_current_tle(norad_id: int) -> dict:
    async with new_client() as client:
        resp = await client.get(settings.tle_mirror_url)
        resp.raise_for_status()
        text = resp.text

    target = f"1 {norad_id:05d}"
    lines = [ln for ln in text.splitlines() if ln.strip()]
    for i, line in enumerate(lines):
        if line.startswith(target) and i + 1 < len(lines):
            name = lines[i - 1].strip() if i > 0 and not lines[i - 1].startswith(("1 ", "2 ")) else f"NORAD {norad_id}"
            return {
                "name": name,
                "line1": line.rstrip(),
                "line2": lines[i + 1].rstrip(),
                "source_url": settings.tle_mirror_url,
            }
    raise ValueError(f"NORAD {norad_id} not found in TLE mirror file")
