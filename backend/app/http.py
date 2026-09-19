"""Shared HTTP client factory. Centralised so timeouts/headers are consistent
across all data-source clients."""
from __future__ import annotations

import httpx

from .config import settings

_USER_AGENT = "KosmoHackathon-EVA-RiskService/1.0 (+research prototype)"


def new_client() -> httpx.AsyncClient:
    """One client factory for every data-source client.

    `settings.http_proxy` (env `EVA_HTTP_PROXY`) lets a deployment route all
    outbound requests through an HTTP/HTTPS/SOCKS proxy — useful when a
    specific government domain (api.nasa.gov, noaa.gov) is rate-limited or
    unreachable from the deployment's network/region, without requiring a
    system-wide VPN. httpx also honours the standard HTTP_PROXY/HTTPS_PROXY
    environment variables on its own (trust_env defaults to True), so this
    setting is only needed when an explicit, single proxy must be forced
    regardless of the process environment.
    """
    return httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
        proxy=settings.http_proxy or None,
    )
