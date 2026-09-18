"""Criterion T2: orbit computed from suitable data, epoch/source surfaced,
current vs historical never silently mixed."""
from datetime import datetime, timezone
from unittest.mock import patch

from app import orbit
from app.clients import celestrak
from .conftest import SAMPLE_TLE


async def _fake_fetch(norad_id=None):
    return SAMPLE_TLE


async def test_propagation_matches_epoch_and_plausible_altitude():
    with patch.object(celestrak, "fetch_current_tle", _fake_fetch):
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        info = await orbit.get_orbit(True, start, start, step_minutes=1.0)

    assert info.epoch == start  # TLE epoch 24001.5 == 2024-01-01 12:00 UTC
    assert len(info.track) == 1
    p = info.track[0]
    # ISS orbits at ~400-430km altitude; a wildly wrong frame conversion
    # would show up as an altitude far outside this band.
    assert 380 < p.alt_km < 450
    assert -90 <= p.lat <= 90
    assert -180 <= p.lon <= 180
    assert p.is_daylight in (True, False)


async def test_orbit_source_and_reconstruction_flag_are_surfaced():
    with patch.object(celestrak, "fetch_current_tle", _fake_fetch):
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        info = await orbit.get_orbit(True, start, start, step_minutes=1.0)
    assert info.source_name
    assert info.source_url
    assert info.is_reconstruction is False  # current mode is never a reconstruction


async def test_historical_mode_without_spacetrack_credentials_is_marked_reconstruction():
    with patch.object(celestrak, "fetch_current_tle", _fake_fetch):
        start = datetime(2024, 5, 10, 6, 0, 0, tzinfo=timezone.utc)
        info = await orbit.get_orbit(False, start, start, step_minutes=1.0)
    # No Space-Track credentials configured in test env -> must fall back
    # honestly, never silently pretend today's orbit is the historical one.
    assert info.is_reconstruction is True
    assert info.reconstruction_note
