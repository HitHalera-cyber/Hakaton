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
        # A separate, short connect-timeout matters a lot for a genuinely
        # unreachable/blocked host (e.g. celestrak.org from some cloud
        # hosts — see README): with a single flat timeout, each of the 3
        # retry attempts in cache.py would hang for the full read-timeout
        # duration before failing, so one blocked source alone could stall
        # a request past what Render's proxy or the browser's own fetch()
        # will wait for, surfacing as an opaque "Failed to fetch" instead
        # of the server's own JSON error. A slow-but-working response
        # still gets the full http_timeout_seconds to complete.
        timeout=httpx.Timeout(
            connect=settings.http_connect_timeout_seconds,
            read=settings.http_timeout_seconds,
            write=settings.http_timeout_seconds,
            pool=settings.http_timeout_seconds,
        ),
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
        proxy=settings.http_proxy or None,
    )
