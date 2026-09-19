import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLE_TLE = {
    "name": "ISS (ZARYA)",
    "line1": "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9007",
    "line2": "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49309620 24775",
    "source_url": "https://celestrak.org/test",
}


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    """Every test gets a fresh on-disk cache dir so tests never see each
    other's cached responses or fight over TTL state."""
    from app.config import settings

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(settings, "cache_dir", cache_dir)
    for cache in list(__import__("app.cache", fromlist=["registry"]).registry._sources.values()):
        cache._path = cache_dir / f"{cache._state.name}.json"
    yield
    shutil.rmtree(cache_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def no_retry_backoff(monkeypatch):
    """SourceCache retries transient failures with a short real-time
    backoff in production; tests exercise the failure path a lot, so drop
    the backoff to zero here rather than paying real wall-clock delays."""
    import app.cache as cache_module

    monkeypatch.setattr(cache_module, "_RETRY_BACKOFF_SECONDS", (0, 0))
