"""Analysis engine: turns factor signals + orbit data into a per-window
comparison and a recommendation.

Scoring rule (documented for O3/T3 auditability):
  combined_score(window) = weighted average of each factor's
  time-weighted severity over the window, weights {space_weather: 0.6,
  conjunction_mmod: 0.4}, renormalised over whichever factors actually have
  sufficient data for that window. A factor with NO data for a window is
  excluded from the score (not treated as 0 = safe). If no scored factor has
  data at all, combined_score is None and the window is reported as
  requiring further verification rather than being silently marked safe.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from . import orbit
from .cache import registry
from .factors import conjunction, space_weather
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CompareDatesRequest,
    CompareDatesResponse,
    ConfidenceLevel,
    FactorAssessment,
    FactorKind,
    HistoricalCutoffInfo,
    Recommendation,
    Signal,
    WindowAssessment,
    WindowFactorContribution,
)
from .config import settings

_WEIGHTS = {FactorKind.space_weather: 0.6, FactorKind.conjunction_mmod: 0.4}
_TIE_EPSILON = 0.02
_DEFAULT_SIGNAL_SPAN = timedelta(minutes=30)

_CONFIDENCE_RANK = {
    ConfidenceLevel.high: 0,
    ConfidenceLevel.medium: 1,
    ConfidenceLevel.low: 2,
    ConfidenceLevel.insufficient_data: 3,
}


def _candidate_windows(req: AnalyzeRequest) -> list[tuple[datetime, datetime]]:
    duration = timedelta(hours=req.duration_hours)
    step = timedelta(minutes=req.step_minutes)
    search = timedelta(hours=req.search_period_hours)
    starts = []
    t = req.reference_time
    end_of_search = req.reference_time + search
    while t <= end_of_search:
        starts.append(t)
        if step.total_seconds() <= 0:
            break
        t += step
    if len(starts) < 2:
        # Need at least two same-duration windows to compare (functional
        # requirement #3). If the requested search period is too small to
        # produce a second candidate, add one adjacent window explicitly.
        starts.append(req.reference_time + duration)
    return [(s, s + duration) for s in starts]


def _overlap_minutes(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> float:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return max(0.0, (end - start).total_seconds() / 60.0)


def _score_factor_for_window(
    signals: list[Signal], window_start: datetime, window_end: datetime
) -> WindowFactorContribution | None:
    duration_min = (window_end - window_start).total_seconds() / 60.0
    total_weighted = 0.0
    total_overlap = 0.0
    max_sev = 0.0
    driving: list[tuple[float, str]] = []
    for sig in signals:
        s_start = sig.observed_or_expected_start
        s_end = sig.observed_or_expected_end or (
            (s_start + _DEFAULT_SIGNAL_SPAN) if s_start else None
        )
        if s_start is None or s_end is None:
            continue
        overlap = _overlap_minutes(s_start, s_end, window_start, window_end)
        if overlap <= 0:
            continue
        total_weighted += sig.severity * overlap
        total_overlap += overlap
        max_sev = max(max_sev, sig.severity)
        driving.append((sig.severity, sig.label))
    if total_overlap <= 0:
        return None
    time_weighted = min(1.0, total_weighted / duration_min) if duration_min > 0 else 0.0
    driving.sort(reverse=True)
    factor = signals[0].factor
    return WindowFactorContribution(
        factor=factor,
        overlap_minutes=total_overlap,
        max_severity=max_sev,
        time_weighted_severity=time_weighted,
        driving_signals=[label for _, label in driving[:3]],
    )


def _window_daylight_fraction(track_points, window_start: datetime, window_end: datetime) -> float:
    pts = [p for p in track_points if window_start <= p.t <= window_end]
    if not pts:
        return 0.5  # unknown -> neutral, never silently "all daylight"
    lit = sum(1 for p in pts if p.is_daylight)
    return lit / len(pts)


async def run_analysis(req: AnalyzeRequest) -> AnalyzeResponse:
    is_historical = req.mode.value == "historical"
    windows_raw = _candidate_windows(req)
    span_start = min(w[0] for w in windows_raw)
    span_end = max(w[1] for w in windows_raw)

    historical_info = HistoricalCutoffInfo(
        is_historical=is_historical,
        requested_instant=req.reference_time if is_historical else None,
        cutoff_applied_at=req.reference_time if is_historical else None,
        replay_mode="forecast_from_past" if is_historical else "not_applicable",
        note=(
            "Прогноз из прошлого: используются только данные, опубликованные не позже "
            f"{req.reference_time.isoformat()}. Более поздние сведения используются только "
            "для проверки результата и не входят в расчёт."
            if is_historical
            else "Режим текущей обстановки: используются самые свежие доступные данные."
        ),
    )

    # Orbit + both factor assessments hit independent external sources
    # (CelesTrak, NOAA, DONKI) and don't depend on each other's results, so
    # they run concurrently rather than one-after-another — with a slow or
    # unreachable source, a sequential await chain could stack up well past
    # what a browser's own fetch() or a hosting platform's request proxy
    # will wait for, surfacing as an opaque network error instead of this
    # service's own (much more informative) JSON error.
    orbit_task = orbit.get_orbit(
        mode_current=not is_historical,
        start=span_start,
        end=span_end,
        step_minutes=min(req.step_minutes, 10.0),
        force_refresh=req.force_refresh,
    )
    if is_historical:
        sw_task = space_weather.assess_historical(
            req.reference_time, span_start, span_end, force_refresh=req.force_refresh
        )
        conj_task = conjunction.assess_historical(
            req.reference_time, span_start, span_end, force_refresh=req.force_refresh
        )
    else:
        sw_task = space_weather.assess_current(
            span_start, span_end, req.disabled_sources, req.frozen_sources, force_refresh=req.force_refresh
        )
        conj_task = conjunction.assess_current(
            span_start, span_end, req.disabled_sources, req.frozen_sources, force_refresh=req.force_refresh
        )

    orbit_info, sw_assessment, conj_assessment = await asyncio.gather(orbit_task, sw_task, conj_task)

    factors: list[FactorAssessment] = [sw_assessment, conj_assessment]
    by_factor_signals = {sw_assessment.factor: sw_assessment.signals, conj_assessment.factor: conj_assessment.signals}
    data_sufficient_by_factor = {sw_assessment.factor: sw_assessment.data_sufficient, conj_assessment.factor: conj_assessment.data_sufficient}

    windows: list[WindowAssessment] = []
    for w_start, w_end in windows_raw:
        contributions: list[WindowFactorContribution] = []
        weighted_sum = 0.0
        weight_total = 0.0
        worst_confidence = ConfidenceLevel.high
        any_factor_had_data = False

        for factor_kind, weight in _WEIGHTS.items():
            if not data_sufficient_by_factor[factor_kind]:
                worst_confidence = max(worst_confidence, ConfidenceLevel.insufficient_data, key=lambda c: _CONFIDENCE_RANK[c])
                continue
            contrib = _score_factor_for_window(by_factor_signals[factor_kind], w_start, w_end)
            if contrib is None:
                contrib = WindowFactorContribution(
                    factor=factor_kind, overlap_minutes=0.0, max_severity=0.0,
                    time_weighted_severity=0.0, driving_signals=[],
                )
            else:
                any_factor_had_data = True
            contributions.append(contrib)
            weighted_sum += contrib.time_weighted_severity * weight
            weight_total += weight

        combined_score = (weighted_sum / weight_total) if weight_total > 0 else None
        if not any_factor_had_data and combined_score is not None:
            # scored factors technically had "sufficient data sources" but no
            # signals overlapped this window at all -> genuinely low risk,
            # keep the (near-zero) score, do not force insufficient.
            pass

        daylight_fraction = _window_daylight_fraction(orbit_info.track, w_start, w_end)
        orbit_note = (
            f"Доля светлого времени в окне: {daylight_fraction*100:.0f}%. "
            f"Траектория рассчитана по данным источника «{orbit_info.source_name}» "
            f"(эпоха {orbit_info.epoch.isoformat()}, давность {orbit_info.age_hours:.1f} ч)."
        )
        if orbit_info.is_reconstruction:
            orbit_note += " " + (orbit_info.reconstruction_note or "")

        windows.append(
            WindowAssessment(
                start=w_start,
                end=w_end,
                duration_hours=req.duration_hours,
                combined_score=combined_score,
                factor_contributions=contributions,
                data_completeness=worst_confidence,
                daylight_fraction=daylight_fraction,
                orbit_note=orbit_note,
            )
        )

    recommendation = _recommend(windows)
    for idx, w in enumerate(windows):
        w.is_recommended = idx == recommendation.recommended_window_index
    if recommendation.recommended_window_index is not None:
        best_score = windows[recommendation.recommended_window_index].combined_score
        if best_score is not None:
            for w in windows:
                if w.combined_score is not None and not w.is_recommended:
                    w.is_tied_with_recommended = abs(w.combined_score - best_score) <= _TIE_EPSILON

    disabled = req.disabled_sources
    frozen = req.frozen_sources
    registry.apply_overrides(disabled, frozen)

    return AnalyzeResponse(
        request=req,
        generated_at=datetime.now(timezone.utc),
        algorithm_version=settings.algorithm_version,
        historical_info=historical_info,
        orbit=orbit_info,
        factors=factors,
        windows=windows,
        recommendation=recommendation,
        sources=registry.all_statuses(),
        result_id=str(uuid.uuid4()),
    )


async def compare_dates(req: CompareDatesRequest) -> CompareDatesResponse:
    """Two independent scenarios (e.g. 10 May vs 21 May), each run through
    the full analysis pipeline exactly as /api/analyze does, then compared
    against each other with the SAME window-comparison logic (_recommend)
    already used to compare windows within one date — here applied across
    the two dates' merged window lists instead of one date's own windows.
    This is deliberately not a separate scoring rule: reusing _recommend
    keeps the tie/insufficient-data messaging identical and already tested.
    """
    req_a = AnalyzeRequest(
        mode=req.mode, reference_time=req.date_a, duration_hours=req.duration_hours,
        search_period_hours=req.search_period_hours, step_minutes=req.step_minutes,
        disabled_sources=req.disabled_sources, frozen_sources=req.frozen_sources,
        force_refresh=req.force_refresh,
    )
    req_b = AnalyzeRequest(
        mode=req.mode, reference_time=req.date_b, duration_hours=req.duration_hours,
        search_period_hours=req.search_period_hours, step_minutes=req.step_minutes,
        disabled_sources=req.disabled_sources, frozen_sources=req.frozen_sources,
        force_refresh=req.force_refresh,
    )
    result_a, result_b = await asyncio.gather(run_analysis(req_a), run_analysis(req_b))

    # _recommend only reads its argument (severity/completeness/timing),
    # never mutates it — safe to feed it both dates' own already-built
    # WindowAssessment objects directly without touching each date's own
    # within-date is_recommended/is_tied flags computed by run_analysis.
    merged_windows = result_a.windows + result_b.windows
    overall = _recommend(merged_windows)

    winning_date: str | None = None
    winning_window_index: int | None = None
    if overall.recommended_window_index is not None:
        idx = overall.recommended_window_index
        if idx < len(result_a.windows):
            winning_date, winning_window_index = "a", idx
        else:
            winning_date, winning_window_index = "b", idx - len(result_a.windows)

    return CompareDatesResponse(
        result_a=result_a,
        result_b=result_b,
        overall_recommendation=overall,
        winning_date=winning_date,
        winning_window_index=winning_window_index,
    )


def _recommend(windows: list[WindowAssessment]) -> Recommendation:
    scored = [(i, w) for i, w in enumerate(windows) if w.combined_score is not None]
    if not scored:
        return Recommendation(
            has_recommendation=False,
            recommended_window_index=None,
            reason=(
                "Недостаточно данных ни по одному сравниваемому окну — ключевые источники "
                "недоступны или не покрывают рассматриваемый период. Рекомендация не выдаётся."
            ),
            caveats=["Повторите запрос после восстановления источников данных."],
        )

    best_idx, best_window = min(scored, key=lambda pair: pair[1].combined_score)
    tied = [
        i for i, w in scored
        if i != best_idx and abs(w.combined_score - best_window.combined_score) <= _TIE_EPSILON
    ]
    caveats = []
    if tied:
        caveats.append(
            "Есть равнозначные по риску альтернативные окна (в пределах погрешности сравнения): "
            + ", ".join(f"#{i+1}" for i in tied)
            + ". Выбор между ними лучше уточнить дополнительными данными."
        )
    insufficient = [i for i, w in enumerate(windows) if w.data_completeness == ConfidenceLevel.insufficient_data]
    if insufficient:
        caveats.append(
            "По окнам "
            + ", ".join(f"#{i+1}" for i in insufficient)
            + " часть факторов не имеет данных — сравнение по ним частично неполное."
        )

    driving = []
    for c in best_window.factor_contributions:
        if c.driving_signals:
            driving.append(f"{c.factor.value}: " + "; ".join(c.driving_signals))
    reason = (
        f"Окно {best_window.start.isoformat()} — {best_window.end.isoformat()} имеет наименьшую "
        f"совокупную оценку риска ({best_window.combined_score:.2f}) среди сравненных окон."
    )
    if driving:
        reason += " Определяющие факторы: " + " | ".join(driving) + "."
    else:
        reason += " Значимых факторов риска в этом окне не выявлено."

    return Recommendation(
        has_recommendation=True,
        recommended_window_index=best_idx,
        reason=reason,
        caveats=caveats,
    )
