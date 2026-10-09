"""NASA's DEMO_KEY has a low hourly quota shared across every anonymous
api.nasa.gov user at once — easy to exhaust with traffic that has nothing
to do with this deployment. A plain raise_for_status() on a 429 gives an
opaque error; these tests check that DonkiRateLimited fires instead, with
guidance tailored to whether it's the shared DEMO_KEY or a personal key."""
from datetime import date

import httpx
import pytest

from app.clients import donki
from app.config import settings


async def test_notifications_429_with_demo_key_mentions_getting_a_personal_key(monkeypatch):
    monkeypatch.setattr(settings, "nasa_api_key", "DEMO_KEY")

    def handler(request):
        return httpx.Response(429)

    def fake_new_client():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(donki, "new_client", fake_new_client)

    with pytest.raises(donki.DonkiRateLimited) as excinfo:
        await donki.fetch_notifications(date(2024, 5, 1), date(2024, 5, 2))
    assert "DEMO_KEY" in str(excinfo.value)
    assert "EVA_NASA_API_KEY" in str(excinfo.value)


async def test_notifications_429_with_personal_key_gives_generic_rate_limit_message(monkeypatch):
    monkeypatch.setattr(settings, "nasa_api_key", "my-personal-key")

    def handler(request):
        return httpx.Response(429)

    def fake_new_client():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(donki, "new_client", fake_new_client)

    with pytest.raises(donki.DonkiRateLimited) as excinfo:
        await donki.fetch_notifications(date(2024, 5, 1), date(2024, 5, 2))
    assert "DEMO_KEY" not in str(excinfo.value)
