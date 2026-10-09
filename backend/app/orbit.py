"""ISS orbit propagation: fetches current GP/TLE elements (with optional
historical fallback via Space-Track), propagates with SGP4, and produces a
ground track annotated with illumination.

Criterion T2 requirements this module exists to satisfy: position computed
from suitable data with epoch/coordinate-system/time accounted for; current
and historical orbits are never mixed; the source, epoch and data age are
always surfaced to the caller.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sgp4.api import Satrec, jday

from .cache import SourceUnavailable, registry
from .clients import celestrak, spacetrack, tle_mirror
from .config import settings
from .models import OrbitInfo, TrackPoint
from .orbit_math import ecef_to_geodetic, is_sunlit, teme_to_ecef

CELESTRAK_GP_CACHE = "celestrak_gp"
TLE_MIRROR_CACHE = "tle_mirror"
SPACETRACK_GP_CACHE = "spacetrack_gp_current"

registry.register(CELESTRAK_GP_CACHE, settings.celestrak_gp_url, settings.current_data_ttl_seconds)
registry.register(TLE_MIRROR_CACHE, settings.tle_mirror_url, settings.current_data_ttl_seconds)
registry.register(SPACETRACK_GP_CACHE, settings.spacetrack_query_url, settings.current_data_ttl_seconds)


def _epoch_from_satrec(sat: Satrec) -> datetime:
    jd = sat.jdsatepoch + sat.jdsatepochF
    # Convert Julian date back to a UTC datetime.
    from .orbit_math import julian_date as _jd  # local import to avoid cycle at module load

    # Invert via a small search-free formula (standard JD->calendar conversion).
    jd_ = jd + 0.5
    z = int(jd_)
    f = jd_ - z
    if z < 2299161:
        a = z
    else:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = b - d - int(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    day_int = int(day)
    frac = day - day_int
    hours = frac * 24
    h = int(hours)
    minutes = (hours - h) * 60
    m = int(minutes)
    s = (minutes - m) * 60
    return datetime(year, month, day_int, h, m, int(s), tzinfo=timezone.utc)


async def _load_current_gp(force_refresh: bool = False) -> dict:
    cache = registry.get(CELESTRAK_GP_CACHE)
    payload, _status, _fresh = await cache.get(
        lambda: celestrak.fetch_current_tle(settings.iss_norad_id), force_refresh=force_refresh
    )
    return payload


async def _load_current_gp_via_mirror(force_refresh: bool = False) -> dict:
    cache = registry.get(TLE_MIRROR_CACHE)
    payload, _status, _fresh = await cache.get(
        lambda: tle_mirror.fetch_current_tle(settings.iss_norad_id), force_refresh=force_refresh
    )
    return payload


async def _load_current_gp_via_spacetrack(force_refresh: bool = False) -> dict:
    cache = registry.get(SPACETRACK_GP_CACHE)
    payload, _status, _fresh = await cache.get(
        lambda: spacetrack.fetch_current_tle(settings.iss_norad_id), force_refresh=force_refresh
    )
    return payload


async def _load_current_gp_with_fallback(force_refresh: bool = False) -> tuple[dict, str]:
    """Ordered fallback chain, shared by both the current-mode path and the
    historical-mode reconstruction path (the latter used to call CelesTrak
    directly and skip the fallback chain entirely — a real bug: a blocked
    CelesTrak broke the "reconstruction" fallback too, not just the primary
    current-mode flow).

    CelesTrak needs no account and has the best freshness, so it's always
    tried first and preferred whenever it works. The GitHub mirror needs no
    account either and is tried next automatically — it only re-publishes
    CelesTrak's own data (not an independent measurement) but runs on
    infrastructure (GitHub's raw-content CDN) that is far less likely to
    share celestrak.org's own blocking/rate-limiting (observed in practice
    on at least one deployment). Space-Track is tried last, and only if the
    user actually configured credentials for it.
    """
    attempts = [
        ("CelesTrak GP (current)", _load_current_gp),
        ("Зеркало TLE на GitHub (резервный источник)", _load_current_gp_via_mirror),
    ]
    if settings.spacetrack_identity and settings.spacetrack_password:
        attempts.append(("Space-Track GP (резервный источник)", _load_current_gp_via_spacetrack))

    errors: list[str] = []
    for label, loader in attempts:
        try:
            gp = await loader(force_refresh=force_refresh)
            return gp, label
        except Exception as exc:  # noqa: BLE001 - aggregated below, never swallowed
            errors.append(f"{label} — {exc}")

    # Every configured source failed: surface ALL of their errors, not just
    # the first one, so a deployment with e.g. Space-Track also
    # misconfigured doesn't get misdiagnosed as "just" a CelesTrak problem.
    raise SourceUnavailable("celestrak_gp", "; ".join(errors))


async def get_orbit(
    mode_current: bool,
    start: datetime,
    end: datetime,
    step_minutes: float,
    force_refresh: bool = False,
) -> OrbitInfo:
    is_reconstruction = False
    reconstruction_note = None

    if mode_current:
        gp, source_name = await _load_current_gp_with_fallback(force_refresh=force_refresh)
        source_url = gp["source_url"]
    else:
        try:
            gp = await spacetrack.fetch_historical_tle(settings.iss_norad_id, start)
            source_name, source_url = "Space-Track GP_HISTORY", gp["source_url"]
        except Exception:
            # Not configured or unavailable: fall back to the freshest
            # current elements we have (through the SAME fallback chain as
            # current mode — this used to call CelesTrak directly and skip
            # the chain, so a blocked CelesTrak broke the reconstruction
            # path too) and mark this explicitly as a reconstruction,
            # never as a verified historical position (criterion:
            # "современная орбита не подменяет историческую").
            gp, fallback_source = await _load_current_gp_with_fallback(force_refresh=False)
            source_name = f"{fallback_source} (использована как реконструкция)"
            source_url = gp["source_url"]
            is_reconstruction = True
            reconstruction_note = (
                "Историческая орбита недоступна без учётных данных Space-Track "
                "(GP_HISTORY). Траектория реконструирована по ближайшим доступным "
                "элементам и не является проверяемым историческим прогнозом "
                "положения станции — используйте её только как ориентировочную "
                "геометрию, отдельно от расчётов, зависящих от точной орбиты."
            )

    sat = Satrec.twoline2rv(gp["line1"], gp["line2"])
    epoch = _epoch_from_satrec(sat)
    fetched_at = datetime.now(timezone.utc)

    track: list[TrackPoint] = []
    t = start
    step = timedelta(minutes=step_minutes)
    while t <= end:
        jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
        err, r, _v = sat.sgp4(jd, fr)
        if err == 0:
            xe, ye, ze = teme_to_ecef(r[0], r[1], r[2], t)
            lat, lon, alt = ecef_to_geodetic(xe, ye, ze)
            sunlit = is_sunlit(r, t)
            track.append(TrackPoint(t=t, lat=lat, lon=lon, alt_km=alt, is_daylight=sunlit))
        t += step

    age_hours = (fetched_at - epoch).total_seconds() / 3600.0

    return OrbitInfo(
        source_name=source_name,
        source_url=source_url,
        norad_id=settings.iss_norad_id,
        epoch=epoch,
        fetched_at=fetched_at,
        age_hours=age_hours,
        is_reconstruction=is_reconstruction,
        reconstruction_note=reconstruction_note,
        track=track,
    )


async def get_position_at(dt: datetime, mode_current: bool = True) -> TrackPoint:
    info = await get_orbit(mode_current, dt, dt, step_minutes=1.0)
    if not info.track:
        raise SourceUnavailable("celestrak_gp", "SGP4 propagation failed at requested instant")
    return info.track[0]
