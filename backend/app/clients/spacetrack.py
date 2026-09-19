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

import re
from datetime import datetime

import httpx

from ..config import settings
from ..http import new_client


class SpaceTrackNotConfigured(Exception):
    pass


class SpaceTrackLoginError(Exception):
    """Raised when Space-Track rejects the configured credentials. Space-
    Track's login endpoint is unusual: a failed login still comes back as
    HTTP 200, with a JSON body like {"Login": "Failed"} instead of an error
    status — httpx's raise_for_status() alone would NOT catch that, and
    every later request in the same session would then fail with an
    unrelated-looking 401/403 instead of a clear "wrong credentials"
    message. We check the login response body explicitly so a bad
    identity/password shows up as exactly that, not a confusing downstream
    failure."""


class SpaceTrackSchemaError(Exception):
    """Raised when the live cdm_public schema doesn't expose a field this
    client needs (a TCA and a satellite-id column). Never raised from a
    guessed field name — see fetch_cdm_conjunctions."""


def _row_to_gp(row: dict) -> dict:
    return {
        "name": row.get("OBJECT_NAME", "unknown"),
        "line1": row["TLE_LINE1"],
        "line2": row["TLE_LINE2"],
        "epoch": row.get("EPOCH"),
        "creation_date": row.get("CREATION_DATE"),
        "source_url": settings.spacetrack_query_url,
    }


async def _login(client: httpx.AsyncClient) -> None:
    if not settings.spacetrack_identity or not settings.spacetrack_password:
        raise SpaceTrackNotConfigured("Space-Track credentials not configured")

    resp = await client.post(
        settings.spacetrack_login_url,
        data={"identity": settings.spacetrack_identity, "password": settings.spacetrack_password},
    )
    resp.raise_for_status()
    # A failed login is still HTTP 200; only the body says so (see
    # SpaceTrackLoginError docstring). A successful login returns an empty
    # body, so anything that parses as {"Login": "Failed", ...} is the one
    # shape we must treat as a hard failure here.
    try:
        body = resp.json()
    except ValueError:
        return  # empty/non-JSON body: the normal successful-login response
    if isinstance(body, dict) and str(body.get("Login", "")).lower() == "failed":
        raise SpaceTrackLoginError(
            f"Space-Track login rejected for identity '{settings.spacetrack_identity}' "
            "(wrong password, or the account needs to accept the site's Acceptable Use "
            "Policy by logging in via the space-track.org website first)"
        )


async def _login_and_query(query_path: str) -> list[dict]:
    async with new_client() as client:
        await _login(client)
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


def _find_field(fields: set[str], *patterns: str) -> str | None:
    for pat in patterns:
        rx = re.compile(pat)
        for f in fields:
            if rx.fullmatch(f):
                return f
    return None


async def fetch_cdm_conjunctions(norad_id: int, limit: int = 50) -> dict:
    """Fallback conjunction-data source for when CelesTrak SOCRATES is
    unreachable — observed in practice to share CelesTrak's own domain-level
    blocking on some hosts (see conjunction.py), with no CDN mirror
    equivalent to the GP fallback's GitHub TLE mirror. Space-Track's own
    public Conjunction Data Message class ("cdm_public") is the natural
    substitute, but its exact column spellings are deliberately NOT
    hardcoded from memory: independent lookups for the real field names
    (SAT_1_ID vs SAT1_ID, MISS_DISTANCE vs MIN_RNG, ...) turned up
    inconsistent answers even across seemingly authoritative sources, and
    space-track.org itself is unreachable from this project's own dev
    environment to verify live against. Instead, immediately before the
    real query, we call Space-Track's "modeldef" endpoint — a schema
    introspection request every class supports — to read the *actual* live
    field names, and use only those (never a guessed name) to build the
    query and later parse the response in parse_cdm_events. If the live
    schema doesn't expose what's needed, this raises SpaceTrackSchemaError
    rather than silently returning nothing or fabricating a field.
    """
    async with new_client() as client:
        await _login(client)

        modeldef_resp = await client.get(f"{settings.spacetrack_modeldef_url}/class/cdm_public/format/json")
        modeldef_resp.raise_for_status()
        modeldef = modeldef_resp.json()
        rows = modeldef.get("data", modeldef) if isinstance(modeldef, dict) else modeldef
        fields = {str(row.get("Field", "")).upper() for row in rows if isinstance(row, dict) and row.get("Field")}

        tca_field = _find_field(fields, r"TCA")
        sat1_id_field = _find_field(fields, r"SAT_?1_?ID", r"SAT1_OBJECT_ID")
        if not tca_field or not sat1_id_field:
            raise SpaceTrackSchemaError(
                f"cdm_public schema exposes no recognizable TCA/satellite-id field (saw: {sorted(fields)})"
            )

        query_url = (
            f"{settings.spacetrack_query_url}/class/cdm_public/{sat1_id_field}/{norad_id}"
            f"/orderby/{tca_field}%20desc/limit/{limit}/format/json"
        )
        resp = await client.get(query_url)
        resp.raise_for_status()
        # fields as a sorted list, not a set: this payload goes through the
        # disk-backed cache's JSON serialization.
        return {"rows": resp.json(), "fields": sorted(fields), "source_url": query_url}


def parse_cdm_events(payload: dict, norad_id: int) -> list[dict]:
    """Parses fetch_cdm_conjunctions' payload into the same event shape
    conjunction.py already builds from CelesTrak SOCRATES: tca,
    miss_distance_km, max_probability, other_object. Field values are read
    using the field names discovered live in fetch_cdm_conjunctions
    (payload["fields"]), never a hardcoded spelling — if a needed field
    can't be found in the live schema, that value is left None rather than
    guessed, so severity falls back to the same conservative "unknown
    geometry" rule already used for a malformed SOCRATES row.

    Only entries naming our own satellite are kept. Space-Track's CDMs for
    the ISS are generated as ISS-as-primary-asset assessments in practice,
    so SAT_1 is checked first; SAT_2 is also checked as a defensive
    fallback in case that convention doesn't hold for a given record.
    """
    fields = set(payload.get("fields") or [])
    rows = payload.get("rows", [])

    tca_field = _find_field(fields, r"TCA")
    miss_field = _find_field(fields, r"MISS_DISTANCE", r"MIN_RNG", r".*MISS.*DIST.*")
    prob_field = _find_field(fields, r"PC", r"COLLISION_PROBABILITY", r".*PROBAB.*")
    sat1_id_field = _find_field(fields, r"SAT_?1_?ID", r"SAT1_OBJECT_ID")
    sat2_id_field = _find_field(fields, r"SAT_?2_?ID", r"SAT2_OBJECT_ID")
    sat1_name_field = _find_field(fields, r"SAT_?1_?NAME", r"SAT1_OBJECT_NAME")
    sat2_name_field = _find_field(fields, r"SAT_?2_?NAME", r"SAT2_OBJECT_NAME")

    events: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        id1 = str(row.get(sat1_id_field, "")) if sat1_id_field else ""
        id2 = str(row.get(sat2_id_field, "")) if sat2_id_field else ""
        if str(norad_id) not in {id1, id2}:
            continue
        other_name = None
        if id1 == str(norad_id) and sat2_name_field:
            other_name = row.get(sat2_name_field)
        elif sat1_name_field:
            other_name = row.get(sat1_name_field)

        miss_km = None
        if miss_field is not None:
            try:
                # Space-Track's documented CDM MISS_DISTANCE is in meters
                # (per the CCSDS-derived CDM spec Space-Track publishes);
                # convert to km to match the km-bucketed severity rule.
                miss_km = float(row[miss_field]) / 1000.0
            except (TypeError, ValueError, KeyError):
                miss_km = None

        events.append(
            {
                "tca": row.get(tca_field) if tca_field else None,
                "miss_distance_km": miss_km,
                "max_probability": row.get(prob_field) if prob_field else None,
                "other_object": other_name or "неизвестный объект (Space-Track cdm_public)",
            }
        )
    return events
