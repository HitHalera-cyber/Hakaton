"""Criterion T6: source failure must never silently look like 'all clear',
and freeze/disable must behave predictably."""
import pytest

from app.cache import SourceCache, SourceUnavailable


async def test_fetch_success_then_serves_cache_within_ttl():
    calls = {"n": 0}

    async def fetch():
        calls["n"] += 1
        return {"value": 42}

    cache = SourceCache("t1", "http://example.test", ttl_seconds=3600)
    payload, status, fresh = await cache.get(fetch)
    assert payload == {"value": 42}
    assert fresh is True
    assert status.is_stale is False

    payload2, status2, fresh2 = await cache.get(fetch)
    assert fresh2 is False
    assert calls["n"] == 1  # second call served from cache, no refetch


async def test_fetch_failure_with_no_cache_raises():
    async def failing_fetch():
        raise RuntimeError("network down")

    cache = SourceCache("t2", "http://example.test", ttl_seconds=3600)
    with pytest.raises(SourceUnavailable):
        await cache.get(failing_fetch)


async def test_fetch_failure_falls_back_to_stale_cache_with_error_recorded():
    state = {"fail": False}

    async def fetch():
        if state["fail"]:
            raise RuntimeError("temporary outage")
        return {"value": 1}

    cache = SourceCache("t3", "http://example.test", ttl_seconds=0)  # always stale
    payload, status, _ = await cache.get(fetch)
    assert payload == {"value": 1}

    state["fail"] = True
    payload2, status2, fresh2 = await cache.get(fetch)
    assert payload2 == {"value": 1}  # stale cache still served
    assert fresh2 is False
    assert status2.last_error is not None


async def test_frozen_source_never_refetches():
    calls = {"n": 0}

    async def fetch():
        calls["n"] += 1
        return {"value": calls["n"]}

    cache = SourceCache("t4", "http://example.test", ttl_seconds=0)
    await cache.get(fetch)
    cache.freeze()
    payload, status, fresh = await cache.get(fetch)
    assert calls["n"] == 1  # frozen: no second network call even though TTL=0
    assert status.is_frozen is True
    assert status.is_stale is False


async def test_disabled_source_with_no_cache_raises_and_never_calls_network():
    calls = {"n": 0}

    async def fetch():
        calls["n"] += 1
        return {"value": 1}

    cache = SourceCache("t5", "http://example.test", ttl_seconds=3600)
    cache.disable()
    with pytest.raises(SourceUnavailable):
        await cache.get(fetch)
    assert calls["n"] == 0
