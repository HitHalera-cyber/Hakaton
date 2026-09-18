"""Shared HTTP client factory. Centralised so timeouts/headers are consistent
across all data-source clients."""
from __future__ import annotations

import httpx

from .config import settings

_USER_AGENT = "KosmoHackathon-EVA-RiskService/1.0 (+research prototype)"


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    )
