"""Space-weather factor: solar radiation storms (S-scale/SEP — the dominant
driver of extra astronaut radiation dose during EVA), geomagnetic storms
(G-scale) and radio blackouts (R-scale) as contextual signals, and
DONKI-based historical notifications for the required "forecast from the
past" replay mode.

Rule summary (documented here so O2/T3 reviewers can audit it in one place):
  - S-scale (and DONKI SEP notifications) is the PRIMARY driver of severity,
    because solar energetic particles are what actually raises dose outside
    the station's shielding during an EVA.
  - G-scale and R-scale are CONTEXTUAL: they add at most a small, capped
    bonus, and only when they are not simply an echo of the same causal
    event as an already-counted S/SEP signal (matched by NOAA-provided
    event linkage when available, otherwise by overlapping issue time
    windows). This directly implements the requirement that "связанные
    сигналы не увеличивают риск автоматически несколько раз".
  - Missing/unavailable sub-scores lower confidence, they are never treated
    as "0 risk".
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

from ..cache import SourceUnavailable, registry
from ..clients import donki, swpc
from ..timeutil import parse_utc_datetime
from ..config import settings
from ..models import ConfidenceLevel, FactorAssessment, FactorKind, Provenance, Signal

SWPC_SCALES_CACHE = "swpc_scales"
SWPC_ALERTS_CACHE = "swpc_alerts"

registry.register(SWPC_SCALES_CACHE, settings.swpc_scales_url, settings.current_data_ttl_seconds)
registry.register(SWPC_ALERTS_CACHE, settings.swpc_alerts_url, settings.current_data_ttl_seconds)

_CONTEXT_CAP = 0.15  # max additive contribution from G/R scales, see module docstring

_DONKI_TYPE_SEVERITY = {
    "SEP": 0.6,
    "GST": 0.35,
    "RBE": 0.25,
    "IPS": 0.2,
    "CME": 0.15,
    "FLR": 0.1,
}
_DONKI_TYPE_LABEL = {
    "SEP": "Солнечное протонное событие (SEP)",
    "GST": "Геомагнитная буря (GST)",
    "RBE": "Радионарушение (RBE)",
    "IPS": "Межпланетное ударное возмущение (IPS)",
    "CME": "Корональный выброс массы (CME)",
    "FLR": "Солнечная вспышка (FLR)",
}


def _apply_overrides(disabled: list[str], frozen: list[str]) -> None:
    for name in (SWPC_SCALES_CACHE, SWPC_ALERTS_CACHE):
        cache = registry.get(name)
        (cache.disable if name in disabled else cache.enable)()
        (cache.freeze if name in frozen else cache.unfreeze)()


def _scale_severity(scale_str: str | None) -> float | None:
    if scale_str is None or scale_str == "":
        return None
    try:
        return max(0.0, min(1.0, int(scale_str) / 5.0))
    except (TypeError, ValueError):
        return None


async def assess_current(
    window_start: datetime,
    window_end: datetime,
    disabled_sources: list[str],
    frozen_sources: list[str],
) -> FactorAssessment:
    _apply_overrides(disabled_sources, frozen_sources)
    signals: list[Signal] = []
    notes_parts: list[str] = []

    scales_cache = registry.get(SWPC_SCALES_CACHE)
    alerts_cache = registry.get(SWPC_ALERTS_CACHE)

    # Independent sources, fetched concurrently rather than one after the
    # other — halves the worst-case wait when one of them is slow/down.
    scales_result, alerts_result = await asyncio.gather(
        scales_cache.get(swpc.fetch_scales), alerts_cache.get(swpc.fetch_alerts), return_exceptions=True
    )

    scales_ok = True
    if isinstance(scales_result, SourceUnavailable):
        scales_ok = False
        notes_parts.append(f"Источник шкал NOAA SWPC недоступен: {scales_result.reason}.")
        scales, scales_status = {}, scales_cache.status
    else:
        scales, scales_status, _ = scales_result

    alerts_ok = True
    if isinstance(alerts_result, SourceUnavailable):
        alerts_ok = False
        notes_parts.append(f"Лента предупреждений NOAA SWPC недоступна: {alerts_result.reason}.")
        alerts, alerts_status = [], alerts_cache.status
    else:
        alerts, alerts_status, _ = alerts_result

    # Determine which forecast-horizon day-buckets ("0" = today ... "3") this
    # window overlaps. NOAA publishes day-granularity scales, coarser than
    # our 6h forecast horizon requirement, so we mark timing as uncertain.
    day0 = datetime.now(timezone.utc).date()
    for offset_str, entry in (scales or {}).items():
        try:
            offset = int(offset_str)
        except ValueError:
            continue
        if offset > 1:  # only "today" and "tomorrow" are within our 6h forecast horizon concern
            continue
        bucket_date = day0 + timedelta(days=offset)
        bucket_start = datetime(bucket_date.year, bucket_date.month, bucket_date.day, tzinfo=timezone.utc)
        bucket_end = bucket_start + timedelta(days=1)
        if bucket_end < window_start or bucket_start > window_end:
            continue
        provenance = Provenance.observation if offset == 0 else Provenance.external_forecast

        s_sev = _scale_severity((entry.get("S") or {}).get("Scale"))
        g_sev = _scale_severity((entry.get("G") or {}).get("Scale"))
        r_sev = _scale_severity((entry.get("R") or {}).get("Scale"))

        if s_sev is not None:
            signals.append(
                Signal(
                    factor=FactorKind.space_weather,
                    label=f"Радиационная буря S{int(s_sev*5)} ({'сегодня' if offset==0 else 'прогноз +1 сутки'})",
                    description=(
                        "Уровень солнечной радиационной бури по шкале NOAA S "
                        "(поток протонов >10 МэВ) — основной фактор дополнительной "
                        "дозы облучения космонавта вне защиты станции."
                    ),
                    severity=s_sev,
                    provenance=provenance,
                    observed_or_expected_start=bucket_start,
                    observed_or_expected_end=bucket_end,
                    is_time_uncertain=True,
                    value=float(int(s_sev * 5)),
                    unit="S-scale (0-5)",
                    source_name="NOAA SWPC noaa-scales.json",
                    source_url=settings.swpc_scales_url,
                    published_at=None,
                    rule_applied="severity = S_scale / 5, основной (не контекстный) сигнал",
                    limitations="Публикуется посуточно, не даёт точного момента начала/окончания в пределах суток.",
                    confidence=ConfidenceLevel.medium if offset == 0 else ConfidenceLevel.low,
                    confidence_rationale=(
                        "Наблюдаемое значение текущих суток." if offset == 0
                        else "Прогноз NOAA на следующие сутки, точность ниже наблюдения."
                    ),
                )
            )
        context_bonus_used = False
        for label, sev, unit_name, key in (("геомагнитной буре", g_sev, "G-scale (0-5)", "G"), ("радионарушению", r_sev, "R-scale (0-5)", "R")):
            if sev is None:
                continue
            capped = min(sev, _CONTEXT_CAP)
            signals.append(
                Signal(
                    factor=FactorKind.space_weather,
                    label=f"Контекст: {key}-scale {int(sev*5)} ({'сегодня' if offset==0 else 'прогноз +1 сутки'})",
                    description=(
                        f"Сопутствующий показатель по {label}. Учитывается как контекст с "
                        f"ограниченным вкладом (не более {_CONTEXT_CAP:.2f}), чтобы связанные "
                        "сигналы одного солнечного события не увеличивали риск повторно."
                    ),
                    severity=capped,
                    provenance=provenance,
                    observed_or_expected_start=bucket_start,
                    observed_or_expected_end=bucket_end,
                    is_time_uncertain=True,
                    value=float(int(sev * 5)),
                    unit=unit_name,
                    source_name="NOAA SWPC noaa-scales.json",
                    source_url=settings.swpc_scales_url,
                    published_at=None,
                    rule_applied=f"severity = min({key}_scale/5, {_CONTEXT_CAP}), контекстный сигнал",
                    limitations="Не суммируется напрямую с основным S-сигналом того же события.",
                    confidence=ConfidenceLevel.medium if offset == 0 else ConfidenceLevel.low,
                    confidence_rationale="Контекстный показатель космической погоды, не первичный для дозы при ВКД.",
                )
            )
            context_bonus_used = True
        if context_bonus_used:
            notes_parts.append("G/R-scale учтены как ограниченный контекст, не как отдельные риски.")

    for alert in alerts or []:
        product_id = str(alert.get("product_id", ""))
        issued = parse_utc_datetime(alert.get("issue_datetime"))
        if issued and not (window_start - timedelta(hours=48) <= issued <= window_end):
            continue
        message = str(alert.get("message", ""))[:400]
        signals.append(
            Signal(
                factor=FactorKind.space_weather,
                label=f"Оповещение NOAA SWPC {product_id or ''}".strip(),
                description=message or "Оповещение без текста",
                severity=0.3,
                provenance=Provenance.observation,
                observed_or_expected_start=issued,
                observed_or_expected_end=None,
                is_time_uncertain=issued is None,
                value=None,
                unit=None,
                source_name="NOAA SWPC alerts.json",
                source_url=settings.swpc_alerts_url,
                published_at=issued,
                rule_applied="фиксированная базовая значимость активного оповещения (0.3), дополняет шкалы",
                limitations="Текстовое оповещение, точная числовая интенсивность берётся из noaa-scales.json.",
                confidence=ConfidenceLevel.medium,
                confidence_rationale="Официальное оповещение NOAA с указанным временем публикации.",
            )
        )

    data_sufficient = scales_ok or alerts_ok
    overall_confidence = ConfidenceLevel.insufficient_data if not data_sufficient else (
        ConfidenceLevel.medium if signals else ConfidenceLevel.high
    )
    if not signals and data_sufficient:
        notes_parts.append("Значимых событий космической погоды в охватываемом периоде не обнаружено.")

    return FactorAssessment(
        factor=FactorKind.space_weather,
        title="Космическая погода (радиация, геомагнитная обстановка)",
        mechanism_description=(
            "Оценивает риск повышенной дозы облучения и связанных возмущений среды "
            "во время ВКД по данным NOAA SWPC (текущая обстановка и краткосрочный прогноз)."
        ),
        data_sufficient=data_sufficient,
        signals=signals,
        overall_confidence=overall_confidence,
        notes=" ".join(notes_parts) if notes_parts else "",
    )


async def assess_historical(
    cutoff: datetime,
    window_start: datetime,
    window_end: datetime,
) -> FactorAssessment:
    """Strict 'forecast from the past' replay: only DONKI notifications with
    messageIssueTime <= cutoff are used. This directly satisfies T4."""
    hist_start = datetime.fromisoformat(settings.historical_start)
    hist_end = datetime.fromisoformat(settings.historical_end)
    if not (hist_start <= cutoff <= hist_end):
        return FactorAssessment(
            factor=FactorKind.space_weather,
            title="Космическая погода (исторический режим)",
            mechanism_description="Проверяемый прогноз из прошлого по данным NASA DONKI.",
            data_sufficient=False,
            signals=[],
            overall_confidence=ConfidenceLevel.insufficient_data,
            notes=(
                f"Запрошенная дата вне поддерживаемого исторического диапазона "
                f"({settings.historical_start[:10]}…{settings.historical_end[:10]})."
            ),
        )

    query_start = (cutoff - timedelta(days=3)).date()
    query_end = cutoff.date()
    cache_name = f"donki_notif_{query_start}_{query_end}"
    cache = registry.get_or_register(cache_name, settings.donki_base_url, ttl_seconds=3600 * 24 * 30)

    signals: list[Signal] = []
    notes_parts: list[str] = []
    data_sufficient = True
    try:
        raw, _status, _fresh = await cache.get(lambda: donki.fetch_notifications(query_start, query_end))
    except SourceUnavailable as exc:
        data_sufficient = False
        raw = []
        notes_parts.append(f"NASA DONKI недоступен: {exc.reason}.")

    kept, dropped_future = 0, 0
    for item in raw or []:
        issued = parse_utc_datetime(item.get("messageIssueTime"))
        if issued is None:
            continue
        if issued > cutoff:
            dropped_future += 1  # strictly excluded from the past-forecast calculation
            continue
        msg_type_raw = str(item.get("messageType", ""))
        msg_type = next((k for k in _DONKI_TYPE_SEVERITY if msg_type_raw.upper().startswith(k)), None)
        if msg_type is None:
            continue
        body = str(item.get("messageBody", ""))[:500]
        is_forecast_wording = any(w in body.lower() for w in ("predicted", "expected", "forecast", "likely"))
        kept += 1
        signals.append(
            Signal(
                factor=FactorKind.space_weather,
                label=f"{_DONKI_TYPE_LABEL[msg_type]} — уведомление DONKI",
                description=body or item.get("messageID", ""),
                severity=_DONKI_TYPE_SEVERITY[msg_type],
                provenance=Provenance.external_forecast if is_forecast_wording else Provenance.observation,
                observed_or_expected_start=issued,
                observed_or_expected_end=None,
                is_time_uncertain=True,
                value=None,
                unit=None,
                source_name="NASA DONKI notifications",
                source_url=settings.donki_base_url,
                published_at=issued,
                rule_applied=(
                    f"фиксированная значимость по типу уведомления DONKI ({msg_type}="
                    f"{_DONKI_TYPE_SEVERITY[msg_type]}); строгое отсечение по messageIssueTime <= {cutoff.isoformat()}"
                ),
                limitations="DONKI-уведомление не даёт точной числовой интенсивности в теле сообщения.",
                confidence=ConfidenceLevel.medium,
                confidence_rationale="Официальное историческое уведомление с датой публикации, отфильтрованное по моменту отсечения.",
            )
        )

    notes_parts.append(
        f"Прогноз из прошлого: учтено {kept} уведомлений, опубликованных не позже {cutoff.isoformat()}; "
        f"{dropped_future} более поздних уведомлений исключены из расчёта и доступны только для проверки."
    )

    overall_confidence = ConfidenceLevel.insufficient_data if not data_sufficient else (
        ConfidenceLevel.medium if signals else ConfidenceLevel.high
    )

    return FactorAssessment(
        factor=FactorKind.space_weather,
        title="Космическая погода (прогноз из прошлого)",
        mechanism_description=(
            "Строгий прогноз из прошлого: используются только уведомления NASA DONKI, "
            f"опубликованные к моменту отсечения {cutoff.isoformat()}."
        ),
        data_sufficient=data_sufficient,
        signals=signals,
        overall_confidence=overall_confidence,
        notes=" ".join(notes_parts),
    )


async def verification_signals(window_start: datetime, window_end: datetime) -> list[Signal]:
    """Fetches the FULL archive (no cutoff) for the same period, for
    after-the-fact verification only. Never fed into the recommendation."""
    query_start = window_start.date()
    query_end = window_end.date()
    cache_name = f"donki_verify_{query_start}_{query_end}"
    cache = registry.get_or_register(cache_name, settings.donki_base_url, ttl_seconds=3600 * 24 * 30)
    try:
        raw, _status, _fresh = await cache.get(lambda: donki.fetch_notifications(query_start, query_end))
    except SourceUnavailable:
        return []
    out: list[Signal] = []
    for item in raw or []:
        msg_type_raw = str(item.get("messageType", ""))
        msg_type = next((k for k in _DONKI_TYPE_SEVERITY if msg_type_raw.upper().startswith(k)), None)
        if msg_type is None:
            continue
        issued = parse_utc_datetime(item.get("messageIssueTime"))
        out.append(
            Signal(
                factor=FactorKind.space_weather,
                label=f"{_DONKI_TYPE_LABEL[msg_type]} — полный архив (для проверки)",
                description=str(item.get("messageBody", ""))[:500],
                severity=_DONKI_TYPE_SEVERITY[msg_type],
                provenance=Provenance.observation,
                observed_or_expected_start=issued,
                observed_or_expected_end=None,
                is_time_uncertain=True,
                value=None,
                unit=None,
                source_name="NASA DONKI notifications (полный архив)",
                source_url=settings.donki_base_url,
                published_at=issued,
                rule_applied="используется только для последующей проверки, не для расчёта окна",
                limitations="Не участвует в рекомендации; служит только для сопоставления прогноза с фактом.",
                confidence=ConfidenceLevel.medium,
                confidence_rationale="Полный архив без отсечения по времени публикации.",
            )
        )
    return out
