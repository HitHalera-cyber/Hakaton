"""Shared pydantic schemas.

The vocabulary here mirrors the postanovka zadachi terms directly so that the
API surface, the analysis engine and the frontend all speak the same
language: factor (mechanism of external influence), signal (one concrete
observed/forecast/calculated data point about a factor), window (candidate
EVA interval), and provenance (origin/observation/forecast/calculation kind
required to distinguish sources visually per criterion O4/O2).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Mode(str, Enum):
    current = "current"
    historical = "historical"


class Provenance(str, Enum):
    """How a value came to exist. Required to be visually distinguishable
    (criterion O2/O4: "Наблюдение, внешний прогноз и расчёт команды должны
    различаться визуально или текстом")."""

    observation = "observation"          # a directly measured/reported value
    external_forecast = "external_forecast"  # a forecast issued by the source org (e.g. NOAA)
    team_calculation = "team_calculation"    # derived/combined by this service's own rules


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    insufficient_data = "insufficient_data"


class FactorKind(str, Enum):
    space_weather = "space_weather"
    conjunction_mmod = "conjunction_mmod"


class SourceStatus(BaseModel):
    name: str
    url: str
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    is_stale: bool = False
    is_frozen: bool = False
    is_disabled: bool = False
    last_error: str | None = None
    ttl_seconds: int


class Signal(BaseModel):
    """One explainable data point feeding a factor's assessment.

    Every field required by criterion O4 ("Объяснение предупреждения") is
    represented directly, not synthesized post-hoc from free text.
    """

    factor: FactorKind
    label: str
    description: str
    severity: float = Field(ge=0.0, le=1.0, description="0=no concern, 1=maximum severity")
    provenance: Provenance
    observed_or_expected_start: datetime | None = None
    observed_or_expected_end: datetime | None = None
    is_time_uncertain: bool = False
    value: float | None = None
    unit: str | None = None
    source_name: str
    source_url: str
    published_at: datetime | None = None
    rule_applied: str
    limitations: str
    confidence: ConfidenceLevel
    confidence_rationale: str


class FactorAssessment(BaseModel):
    factor: FactorKind
    title: str
    mechanism_description: str
    data_sufficient: bool
    signals: list[Signal]
    overall_confidence: ConfidenceLevel
    notes: str


class TrackPoint(BaseModel):
    t: datetime
    lat: float
    lon: float
    alt_km: float
    is_daylight: bool | None = None


class OrbitInfo(BaseModel):
    source_name: str
    source_url: str
    norad_id: int
    epoch: datetime
    fetched_at: datetime
    age_hours: float
    is_reconstruction: bool
    reconstruction_note: str | None = None
    track: list[TrackPoint]


class WindowFactorContribution(BaseModel):
    factor: FactorKind
    overlap_minutes: float
    max_severity: float
    time_weighted_severity: float
    driving_signals: list[str]


class WindowAssessment(BaseModel):
    start: datetime
    end: datetime
    duration_hours: float
    combined_score: float | None
    factor_contributions: list[WindowFactorContribution]
    data_completeness: ConfidenceLevel
    daylight_fraction: float = Field(ge=0.0, le=1.0)
    orbit_note: str
    is_recommended: bool = False
    is_tied_with_recommended: bool = False


class Recommendation(BaseModel):
    has_recommendation: bool
    recommended_window_index: int | None
    reason: str
    caveats: list[str]


class HistoricalCutoffInfo(BaseModel):
    is_historical: bool
    requested_instant: datetime | None = None
    cutoff_applied_at: datetime | None = None
    replay_mode: Literal["forecast_from_past", "situation_review", "not_applicable"]
    note: str


class AnalyzeRequest(BaseModel):
    mode: Mode
    reference_time: datetime = Field(description="Start of EVA window (UTC) for 'now' anchor of search")
    duration_hours: float = Field(ge=1.0, le=8.0)
    search_period_hours: float = Field(ge=0.0, le=24.0, default=0.0)
    step_minutes: float = Field(default=30.0, ge=5.0, le=120.0)
    disabled_sources: list[str] = Field(default_factory=list)
    frozen_sources: list[str] = Field(default_factory=list)
    force_refresh: bool = Field(
        default=False,
        description="Bypass the TTL cache and re-fetch every source now, even if a fresh cached copy exists.",
    )


class AnalyzeResponse(BaseModel):
    request: AnalyzeRequest
    generated_at: datetime
    algorithm_version: str
    historical_info: HistoricalCutoffInfo
    orbit: OrbitInfo
    factors: list[FactorAssessment]
    windows: list[WindowAssessment]
    recommendation: Recommendation
    sources: list[SourceStatus]
    result_id: str


class CompareDatesRequest(BaseModel):
    """Compares two independent EVA scenarios anchored on different
    reference dates/times (e.g. 10 May vs 21 May) — distinct from
    AnalyzeRequest.search_period_hours, which only compares different start
    times clustered around ONE reference date. Duration/search/step/mode
    and source overrides are shared by both scenarios so the two runs are
    directly comparable (same weighting, same analysis settings)."""

    mode: Mode
    date_a: datetime = Field(description="Reference start of EVA window (UTC) for scenario A")
    date_b: datetime = Field(description="Reference start of EVA window (UTC) for scenario B")
    duration_hours: float = Field(ge=1.0, le=8.0)
    search_period_hours: float = Field(ge=0.0, le=24.0, default=0.0)
    step_minutes: float = Field(default=30.0, ge=5.0, le=120.0)
    disabled_sources: list[str] = Field(default_factory=list)
    frozen_sources: list[str] = Field(default_factory=list)
    force_refresh: bool = Field(default=False, description="Bypass the TTL cache for both scenarios.")


class CompareDatesResponse(BaseModel):
    result_a: AnalyzeResponse
    result_b: AnalyzeResponse
    overall_recommendation: Recommendation
    winning_date: Literal["a", "b"] | None
    winning_window_index: int | None = Field(
        description="Index into winning_date's own result.windows identifying the overall-best window"
    )


class ExperimentResult(BaseModel):
    """Output of the simple-vs-team-method comparison (criterion T5)."""

    method: str
    description: str
    event_period: tuple[datetime, datetime]
    control_period: tuple[datetime, datetime]
    metrics: dict[str, Any]
