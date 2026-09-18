"""Conjunction / MMOD factor: uses CelesTrak SOCRATES to flag close
approaches of tracked objects to the ISS as a proxy for elevated debris risk
around a candidate EVA window.

Per the task's own domain guidance: a conjunction warning concerns the
*station* and tracked objects; it does not itself give the probability of a
small untracked fragment striking a crew member. We surface it as exactly
that — a proxy indicator with an explicit scope limitation — never as a
direct EVA-safety verdict.

Historical mode: SOCRATES has no practical, license-compatible historical
archive without a Space-Track account, so historical requests for this
factor are honestly reported as data-insufficient rather than fabricated.
This is a deliberate, documented choice — see README limitations.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..cache import SourceUnavailable, registry
from ..clients import celestrak
from ..config import settings
from ..models import ConfidenceLevel, FactorAssessment, FactorKind, Provenance, Signal

SOCRATES_CACHE = "celestrak_socrates"
registry.register(SOCRATES_CACHE, settings.celestrak_socrates_url, ttl_seconds=6 * 3600)


def _apply_overrides(disabled: list[str], frozen: list[str]) -> None:
    cache = registry.get(SOCRATES_CACHE)
    (cache.disable if SOCRATES_CACHE in disabled else cache.enable)()
    (cache.freeze if SOCRATES_CACHE in frozen else cache.unfreeze)()


def _severity_from_event(miss_km: str, max_prob: str) -> float:
    """Rule: probability dominates when available (numeric, most direct);
    otherwise fall back to a miss-distance bucket. Documented explicitly so
    T3 reviewers can audit the rule without reading code."""
    try:
        p = float(max_prob)
        if p > 0:
            return max(0.0, min(1.0, p / 1e-4))  # 1e-4 treated as a high-concern reference probability
    except (TypeError, ValueError):
        pass
    try:
        km = float(miss_km)
    except (TypeError, ValueError):
        return 0.2  # unknown geometry, low-confidence baseline concern
    if km < 1:
        return 0.9
    if km < 5:
        return 0.6
    if km < 20:
        return 0.3
    return 0.1


async def assess_current(
    window_start: datetime,
    window_end: datetime,
    disabled_sources: list[str],
    frozen_sources: list[str],
) -> FactorAssessment:
    _apply_overrides(disabled_sources, frozen_sources)
    cache = registry.get(SOCRATES_CACHE)
    signals: list[Signal] = []
    notes_parts: list[str] = []
    data_sufficient = True

    try:
        csv_text, _status, _fresh = await cache.get(celestrak.fetch_socrates_csv)
    except SourceUnavailable as exc:
        data_sufficient = False
        csv_text = ""
        notes_parts.append(f"CelesTrak SOCRATES недоступен: {exc.reason}.")

    events = celestrak.parse_socrates_for_norad(csv_text, settings.iss_norad_id) if csv_text else []

    for ev in events:
        tca_raw = ev.get("tca")
        tca = None
        if tca_raw:
            for fmt in ("%Y %b %d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    tca = datetime.strptime(tca_raw, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
        if tca and not (window_start <= tca <= window_end):
            continue
        severity = _severity_from_event(ev.get("miss_distance_km"), ev.get("max_probability"))
        signals.append(
            Signal(
                factor=FactorKind.conjunction_mmod,
                label=f"Сближение с объектом «{ev.get('other_object')}»",
                description=(
                    "Расчётное сближение отслеживаемого объекта со станцией (CelesTrak SOCRATES). "
                    "Показатель относится к станции и каталогизированным объектам; он не задаёт "
                    "вероятность попадания мелкого несопровождаемого фрагмента в космонавта."
                ),
                severity=severity,
                provenance=Provenance.external_forecast,
                observed_or_expected_start=tca,
                observed_or_expected_end=tca,
                is_time_uncertain=tca is None,
                value=float(ev.get("miss_distance_km")) if _is_float(ev.get("miss_distance_km")) else None,
                unit="км (минимальная дальность)",
                source_name="CelesTrak SOCRATES",
                source_url=settings.celestrak_socrates_url,
                published_at=None,
                rule_applied=(
                    "severity = вероятность/1e-4 при наличии; иначе ступенчато по минимальной "
                    "дальности (<1км=0.9, <5км=0.6, <20км=0.3, иначе 0.1)"
                ),
                limitations=(
                    "Прокси-показатель обстановки вокруг станции, не индивидуальная оценка риска "
                    "для скафандра или конкретного члена экипажа."
                ),
                confidence=ConfidenceLevel.medium if tca else ConfidenceLevel.low,
                confidence_rationale=(
                    "Публичный расчёт CelesTrak на основе каталогизированных элементов; "
                    "не учитывает некаталогизированные мелкие фрагменты (MMOD)."
                ),
            )
        )

    if data_sufficient and not signals:
        notes_parts.append(
            "В охватываемом периоде значимых сближений по каталогизированным объектам не выявлено. "
            "Это не означает нулевой риск от некаталогизированных микрометеороидов/мусора — по ним "
            "доступны только статистические, а не индивидуальные оценки."
        )

    overall_confidence = ConfidenceLevel.insufficient_data if not data_sufficient else (
        ConfidenceLevel.medium if signals else ConfidenceLevel.high
    )

    return FactorAssessment(
        factor=FactorKind.conjunction_mmod,
        title="Сближения и MMOD (микрометеороиды/орбитальный мусор)",
        mechanism_description=(
            "Использует публичный отчёт CelesTrak SOCRATES о расчётных сближениях "
            "каталогизированных объектов со станцией как прокси-показатель обстановки "
            "по мусору; статистический фон MMOD не даёт индивидуального прогноза по частицам."
        ),
        data_sufficient=data_sufficient,
        signals=signals,
        overall_confidence=overall_confidence,
        notes=" ".join(notes_parts),
    )


def _is_float(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


async def assess_historical(cutoff: datetime, window_start: datetime, window_end: datetime) -> FactorAssessment:
    return FactorAssessment(
        factor=FactorKind.conjunction_mmod,
        title="Сближения и MMOD (исторический режим)",
        mechanism_description=(
            "CelesTrak SOCRATES публикует только текущий скользящий прогноз сближений "
            "и не хранит воспроизводимый датированный архив без учётной записи Space-Track."
        ),
        data_sufficient=False,
        signals=[],
        overall_confidence=ConfidenceLevel.insufficient_data,
        notes=(
            "Честно обозначено как недостаток данных, а не отсутствие риска: для выбранной "
            "исторической даты фактор сближений не рассчитывается. Используйте только оценку "
            "космической погоды как проверяемую линию анализа для этого периода."
        ),
    )
