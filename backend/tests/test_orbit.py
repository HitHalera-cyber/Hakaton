"""Criterion T2: orbit computed from suitable data, epoch/source surfaced,
current vs historical never silently mixed."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import orbit
from app.cache import SourceUnavailable
from app.clients import celestrak, spacetrack, tle_mirror
from app.config import settings
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


async def _failing_fetch(norad_id=None):
    raise ConnectionError("simulated CelesTrak block")


async def test_current_mode_all_sources_failing_raises_with_all_reasons():
    """No fallback configured / all fail -> the caller must see an
    actionable error naming every attempted source, never a silent/false
    success."""
    with patch.object(celestrak, "fetch_current_tle", _failing_fetch), \
         patch.object(tle_mirror, "fetch_current_tle", _failing_fetch):
        with pytest.raises(SourceUnavailable) as excinfo:
            await orbit.get_orbit(True, datetime(2026, 1, 1, tzinfo=timezone.utc),
                                   datetime(2026, 1, 1, tzinfo=timezone.utc), step_minutes=1.0)
    assert "CelesTrak" in str(excinfo.value) or "celestrak" in str(excinfo.value).lower()


async def test_current_mode_falls_back_to_github_mirror_when_celestrak_fails():
    async def fake_mirror(norad_id):
        return SAMPLE_TLE

    with patch.object(celestrak, "fetch_current_tle", _failing_fetch), \
         patch.object(tle_mirror, "fetch_current_tle", fake_mirror):
        info = await orbit.get_orbit(True, datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                                      datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc), step_minutes=1.0)
    assert "GitHub" in info.source_name
    assert info.is_reconstruction is False


async def test_current_mode_falls_back_to_spacetrack_when_celestrak_and_mirror_fail():
    async def fake_spacetrack_current(norad_id):
        return SAMPLE_TLE

    with patch.object(settings, "spacetrack_identity", "test-user"), \
         patch.object(settings, "spacetrack_password", "test-pass"), \
         patch.object(celestrak, "fetch_current_tle", _failing_fetch), \
         patch.object(tle_mirror, "fetch_current_tle", _failing_fetch), \
         patch.object(spacetrack, "fetch_current_tle", fake_spacetrack_current):
        info = await orbit.get_orbit(True, datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                                      datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc), step_minutes=1.0)
    assert "Space-Track" in info.source_name
    assert info.is_reconstruction is False  # a real current fix, not a reconstruction


async def test_current_mode_all_three_sources_failing_reports_all_reasons():
    async def failing_spacetrack_current(norad_id):
        raise ConnectionError("simulated Space-Track outage too")

    with patch.object(settings, "spacetrack_identity", "test-user"), \
         patch.object(settings, "spacetrack_password", "test-pass"), \
         patch.object(celestrak, "fetch_current_tle", _failing_fetch), \
         patch.object(tle_mirror, "fetch_current_tle", _failing_fetch), \
         patch.object(spacetrack, "fetch_current_tle", failing_spacetrack_current):
        with pytest.raises(SourceUnavailable) as excinfo:
            await orbit.get_orbit(True, datetime(2026, 1, 1, tzinfo=timezone.utc),
                                   datetime(2026, 1, 1, tzinfo=timezone.utc), step_minutes=1.0)
    # every attempted source's failure reason must be visible, not just the first one
    msg = str(excinfo.value)
    assert "CelesTrak" in msg and "GitHub" in msg and "Space-Track" in msg
