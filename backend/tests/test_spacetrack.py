"""Space-Track's login endpoint is unusual: a rejected login still comes
back as HTTP 200, with a JSON body like {"Login": "Failed"} instead of an
error status. Without checking the body explicitly, a bad identity/password
would silently pass raise_for_status() and only surface a few requests
later as a confusing, unrelated-looking 401/403. These tests exercise
_login() directly against a mocked transport (no real network) to make
sure a bad login is caught at the point it actually happens."""
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
