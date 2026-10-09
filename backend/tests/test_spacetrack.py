"""Space-Track's login endpoint is unusual: a rejected login still comes
back as HTTP 200, with a JSON body like {"Login": "Failed"} instead of an
error status. Without checking the body explicitly, a bad identity/password
would silently pass raise_for_status() and only surface a few requests
later as a confusing, unrelated-looking 401/403. These tests exercise
_login() directly against a mocked transport (no real network) to make
sure a bad login is caught at the point it actually happens."""
from datetime import datetime, timezone

import httpx
import pytest

from app.clients import spacetrack
from app.config import settings


async def test_login_raises_clear_error_on_login_failed_body(monkeypatch):
    monkeypatch.setattr(settings, "spacetrack_identity", "bad-user")
    monkeypatch.setattr(settings, "spacetrack_password", "bad-pass")

    def handler(request):
        return httpx.Response(200, json={"Login": "Failed"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(spacetrack.SpaceTrackLoginError):
            await spacetrack._login(client)


async def test_login_succeeds_on_normal_empty_body(monkeypatch):
    monkeypatch.setattr(settings, "spacetrack_identity", "good-user")
    monkeypatch.setattr(settings, "spacetrack_password", "good-pass")

    def handler(request):
        return httpx.Response(200, content=b"")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await spacetrack._login(client)  # must not raise


async def test_login_without_credentials_raises_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "spacetrack_identity", None)
    monkeypatch.setattr(settings, "spacetrack_password", None)

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
        with pytest.raises(spacetrack.SpaceTrackNotConfigured):
            await spacetrack._login(client)


async def test_fetch_cdm_conjunctions_requests_modeldef_at_the_dedicated_url(monkeypatch):
    """Regression test: modeldef is its own request type under
    basicspacedata ("/basicspacedata/modeldef/..."), not a predicate tacked
    onto the query request type ("/basicspacedata/query/modeldef/...") —
    the latter is exactly the mistake that produced a live 400 Bad Request."""
    monkeypatch.setattr(settings, "spacetrack_identity", "user")
    monkeypatch.setattr(settings, "spacetrack_password", "pass")

    seen_urls = []

    def handler(request):
        seen_urls.append(str(request.url))
        if request.url.path.endswith("/ajaxauth/login"):
            return httpx.Response(200, content=b"")
        if request.url.path.startswith("/basicspacedata/modeldef/"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"Field": "TCA"},
                        {"Field": "MISS_DISTANCE"},
                        {"Field": "PC"},
                        {"Field": "SAT_1_ID"},
                        {"Field": "SAT_2_ID"},
                        {"Field": "SAT_1_NAME"},
                        {"Field": "SAT_2_NAME"},
                    ]
                },
            )
        return httpx.Response(200, json=[])

    def fake_new_client():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(spacetrack, "new_client", fake_new_client)

    payload = await spacetrack.fetch_cdm_conjunctions(25544)

    assert "https://www.space-track.org/basicspacedata/modeldef/class/cdm_public/format/json" in seen_urls
    assert not any("/basicspacedata/query/modeldef" in u for u in seen_urls)
    assert payload["rows"] == []


async def test_fetch_cdm_conjunctions_for_window_filters_by_creation_date_before_cutoff(monkeypatch):
    """The historical query must filter on a creation/publication-time
    field with the cutoff, not just TCA — otherwise a "forecast from the
    past" could use CDMs published after the cutoff, which is exactly the
    kind of leak the strict T4 replay rule exists to prevent."""
    monkeypatch.setattr(settings, "spacetrack_identity", "user")
    monkeypatch.setattr(settings, "spacetrack_password", "pass")

    seen_urls = []

    def handler(request):
        seen_urls.append(str(request.url))
        if request.url.path.endswith("/ajaxauth/login"):
            return httpx.Response(200, content=b"")
        if request.url.path.startswith("/basicspacedata/modeldef/"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"Field": "TCA"},
                        {"Field": "CREATION_DATE"},
                        {"Field": "SAT_1_ID"},
                    ]
                },
            )
        return httpx.Response(200, json=[])

    def fake_new_client():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(spacetrack, "new_client", fake_new_client)

    cutoff = datetime(2024, 5, 10, 6, 0, tzinfo=timezone.utc)
    await spacetrack.fetch_cdm_conjunctions_for_window(25544, cutoff)

    query_urls = [u for u in seen_urls if "/basicspacedata/query/class/cdm_public/" in u]
    assert len(query_urls) == 1
    assert "CREATION_DATE/%3C2024-05-10T06:00:00" in query_urls[0]
    assert "SAT_1_ID/25544" in query_urls[0]


async def test_fetch_cdm_conjunctions_for_window_without_creation_field_raises_schema_error(monkeypatch):
    monkeypatch.setattr(settings, "spacetrack_identity", "user")
    monkeypatch.setattr(settings, "spacetrack_password", "pass")

    def handler(request):
        if request.url.path.endswith("/ajaxauth/login"):
            return httpx.Response(200, content=b"")
        if request.url.path.startswith("/basicspacedata/modeldef/"):
            return httpx.Response(200, json={"data": [{"Field": "TCA"}, {"Field": "SAT_1_ID"}]})
        return httpx.Response(200, json=[])

    def fake_new_client():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(spacetrack, "new_client", fake_new_client)

    cutoff = datetime(2024, 5, 10, 6, 0, tzinfo=timezone.utc)
    with pytest.raises(spacetrack.SpaceTrackSchemaError):
        await spacetrack.fetch_cdm_conjunctions_for_window(25544, cutoff)
