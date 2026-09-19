"""Runtime configuration. All external endpoints, keys and tunables live here,
never hardcoded in the client/business logic modules."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EVA_", extra="ignore")

    # --- Data sources ---
    celestrak_gp_url: str = "https://celestrak.org/NORAD/elements/gp.php"
    celestrak_socrates_url: str = "https://celestrak.org/SOCRATES/socrates-limited-7.csv"
    # Fallback only — re-publishes CelesTrak's own data via GitHub's raw
    # CDN, refreshed roughly every 8h. See clients/tle_mirror.py.
    tle_mirror_url: str = "https://raw.githubusercontent.com/caelo-works/tle-mirror/main/tle/stations.tle"
    swpc_scales_url: str = "https://services.swpc.noaa.gov/products/noaa-scales.json"
    swpc_kp_url: str = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    swpc_alerts_url: str = "https://services.swpc.noaa.gov/products/alerts.json"
    donki_base_url: str = "https://api.nasa.gov/DONKI"
    nasa_api_key: str = "DEMO_KEY"

    # Optional: Space-Track (needed only for authenticated historical GP_HISTORY orbit elements).
    spacetrack_login_url: str = "https://www.space-track.org/ajaxauth/login"
    spacetrack_query_url: str = "https://www.space-track.org/basicspacedata/query"
    # "modeldef" is its own request type under the same "basicspacedata"
    # controller, not a predicate appended after "query" — a distinct base
    # URL avoids ever reconstructing it wrong. See clients/spacetrack.py.
    spacetrack_modeldef_url: str = "https://www.space-track.org/basicspacedata/modeldef"
    spacetrack_identity: str | None = None
    spacetrack_password: str | None = None

    iss_norad_id: int = 25544

    # --- Cache ---
    cache_dir: Path = Path(__file__).resolve().parents[2] / "data" / "cache"
    current_data_ttl_seconds: int = 300  # how often "current" sources are considered fresh
    http_timeout_seconds: float = 20.0
    # Kept short and separate from http_timeout_seconds on purpose: a host
    # that is unreachable/blocked (not just slow) should fail fast, not
    # eat the full read-timeout on every attempt — see http.py.
    http_connect_timeout_seconds: float = 6.0
    # Optional explicit proxy (e.g. "http://user:pass@host:port" or
    # "socks5://host:port") for deployments where a source (typically
    # api.nasa.gov) is rate-limited or unreachable from the local network.
    http_proxy: str | None = None

    # --- Task limits per postanovka zadachi ---
    min_duration_hours: float = 1.0
    max_duration_hours: float = 8.0
    max_search_period_hours: float = 24.0
    forecast_horizon_hours: float = 6.0

    # --- Historical mode bounds ---
    historical_start: str = "2024-05-01T00:00:00+00:00"
    historical_end: str = "2024-06-30T23:59:59+00:00"

    algorithm_version: str = "1.0.0"


settings = Settings()
settings.cache_dir.mkdir(parents=True, exist_ok=True)
