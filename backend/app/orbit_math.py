"""Low-level orbital/astronomical math: TEME -> geodetic conversion and a
simplified sun position / eclipse test.

These are standard, well-documented approximations appropriate for a
research prototype (not for operational flight dynamics):
- TEME->ECEF uses GMST rotation only (no polar motion / nutation correction,
  error is sub-km scale, negligible next to SGP4's own few-km accuracy).
- Geodetic conversion uses the closed-form Bowring approximation for WGS84.
- Sun position uses the low-precision solar ephemeris from the Astronomical
  Almanac (accurate to ~0.01 deg), and eclipse/illumination uses a
  cylindrical (not conical) shadow model, which is standard for coarse
  day/night tagging of a ground track.
Both approximations are noted in the API output's `limitations` text
wherever they feed a Signal, per the honesty requirements in the task (O2).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

WGS84_A = 6378.137  # km, semi-major axis
WGS84_F = 1 / 298.257223563
WGS84_E2 = WGS84_F * (2 - WGS84_F)


def julian_date(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + (dt.minute + dt.second / 60) / 60) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    return jd


def gmst_rad(dt: datetime) -> float:
    """Greenwich Mean Sidereal Time in radians (IAU 1982 model)."""
    jd = julian_date(dt)
    t = (jd - 2451545.0) / 36525.0
    gmst_sec = (
        67310.54841
        + (876600 * 3600 + 8640184.812866) * t
        + 0.093104 * t * t
        - 6.2e-6 * t * t * t
    )
    gmst_deg = (gmst_sec % 86400.0) / 240.0  # seconds of time -> degrees (86400s = 360deg *240)
    return math.radians(gmst_deg % 360.0)


def teme_to_ecef(x: float, y: float, z: float, dt: datetime) -> tuple[float, float, float]:
    theta = gmst_rad(dt)
    ct, st = math.cos(theta), math.sin(theta)
    xe = ct * x + st * y
    ye = -st * x + ct * y
    return xe, ye, z


def ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Returns (lat_deg, lon_deg, alt_km) using Bowring's method."""
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    if p < 1e-9:
        lat = math.pi / 2 if z > 0 else -math.pi / 2
        alt = abs(z) - WGS84_A * math.sqrt(1 - WGS84_E2)
        return math.degrees(lat), math.degrees(lon), alt

    theta = math.atan2(z * WGS84_A, p * WGS84_A * (1 - WGS84_F))
    ep2 = WGS84_E2 / (1 - WGS84_E2)
    lat = math.atan2(
        z + ep2 * WGS84_A * (1 - WGS84_F) * math.sin(theta) ** 3,
        p - WGS84_E2 * WGS84_A * math.cos(theta) ** 3,
    )
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(lat) ** 2)
    alt = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), alt


def sun_vector_eci_km(dt: datetime) -> tuple[float, float, float]:
    """Low-precision sun position (Astronomical Almanac algorithm), returned
    in an Earth-centered inertial frame close enough to TEME for shadow
    testing at this precision level."""
    jd = julian_date(dt)
    n = jd - 2451545.0
    L = math.radians((280.460 + 0.9856474 * n) % 360.0)
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    au_km = 149_597_870.7
    r = 1.00014 - 0.01671 * math.cos(g) - 0.00014 * math.cos(2 * g)
    x = r * math.cos(lam) * au_km
    y = r * math.sin(lam) * math.cos(eps) * au_km
    z = r * math.sin(lam) * math.sin(eps) * au_km
    return x, y, z


def is_sunlit(sat_teme_km: tuple[float, float, float], dt: datetime) -> bool:
    """Cylindrical shadow model: satellite is in shadow if it is on the
    night side of Earth's terminator plane and within Earth's radius of the
    Earth-Sun axis."""
    sx, sy, sz = sun_vector_eci_km(dt)
    s_norm = math.sqrt(sx * sx + sy * sy + sz * sz)
    su = (sx / s_norm, sy / s_norm, sz / s_norm)
    px, py, pz = sat_teme_km
    dot = px * su[0] + py * su[1] + pz * su[2]
    if dot > 0:
        return True  # on the sun-facing side
    perp = math.sqrt(px * px + py * py + pz * pz - dot * dot)
    return perp > WGS84_A  # outside Earth's cylindrical shadow radius
