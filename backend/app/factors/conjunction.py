"""Conjunction / MMOD factor: uses CelesTrak SOCRATES to flag close
approaches of tracked objects to the ISS as a proxy for elevated debris risk
around a candidate EVA window. If SOCRATES itself is unreachable — observed
in practice to share CelesTrak's own domain-level blocking with the GP
orbit source on some hosts — falls back to Space-Track's public CDM class
("cdm_public") when credentials are configured, the same optional account
already used as a GP fallback (see clients/spacetrack.py for why its field
names are discovered live rather than hardcoded).

Per the task's own domain guidance: a conjunction warning concerns the
*station* and tracked objects; it does not itself give the probability of a
small untracked fragment striking a crew member. We surface it as exactly
that — a proxy indicator with an explicit scope limitation — never as a
direct EVA-safety verdict.

Historical mode: neither SOCRATES nor cdm_public has a practical,
license-compatible historical archive queryable the same way, so historical
requests for this factor are honestly reported as data-insufficient rather
than fabricated. This is a deliberate, documented choice — see README
limitations.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..cache import SourceUnavailable, registry
from ..clients import celestrak, spacetrack
from ..config import settings
from ..models import ConfidenceLevel, FactorAssessment, FactorKind, Provenance, Signal

SOCRATES_CACHE = "celestrak_socrates"
SPACETRACK_CDM_CACHE = "spacetrack_cdm"
registry.register(SOCRATES_CACHE, settings.celestrak_socrates_url, ttl_seconds=6 * 3600)
registry.register(SPACETRACK_CDM_CACHE, settings.spacetrack_query_url, settings.current_data_ttl_seconds)


def _apply_overrides(disabled: list[str], frozen: list[str]) -> None:
    for name in (SOCRATES_CACHE, SPACETRACK_CDM_CACHE):
        cache = registry.get(name)
        (cache.disable if name in disabled else cache.enable)()
        (cache.freeze if name in frozen else cache.unfreeze)()


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
    source_name = "CelesTrak SOCRATES"
    source_url = settings.celestrak_socrates_url
    is_cdm_fallback = False

    events: list[dict] = []
    try:
        csv_text, _status, _fresh = await cache.get(celestrak.fetch_socrates_csv)
        events = celestrak.parse_socrates_for_norad(csv_text, settings.iss_norad_id)
    except SourceUnavailable as exc:
        data_sufficient = False
        notes_parts.append(f"CelesTrak SOCRATES недоступен: {exc.reason}.")

        if settings.spacetrack_identity and settings.spacetrack_password:
            cdm_cache = registry.get(SPACETRACK_CDM_CACHE)
            try:
                payload, _status, _fresh = await cdm_cache.get(
                    lambda: spacetrack.fetch_cdm_conjunctions(settings.iss_norad_id)
                )
                events = spacetrack.parse_cdm_events(payload, settings.iss_norad_id)
                data_sufficient = True
                is_cdm_fallback = True
                source_name = "Space-Track cdm_public (резервный источник)"
                source_url = payload.get("source_url", settings.spacetrack_query_url)
                notes_parts.append(
                    "Использован резервный источник Space-Track cdm_public: официальные CDM для "
                    "станции; названия полей схемы определены динамически по live-ответу сервера "
                    "(см. clients/spacetrack.py), поэтому уверенность в этих сигналах понижена."
                )
            except Exception as cdm_exc:  # noqa: BLE001 - reported, never swallowed
                notes_parts.append(f"Резервный источник Space-Track cdm_public тоже недоступен: {cdm_exc}.")
        else:
            notes_parts.append(
                "Резервный источник Space-Track cdm_public не настроен (не заданы EVA_SPACETRACK_IDENTITY / "
                "EVA_SPACETRACK_PASSWORD)."
            )

    signals = _events_to_signals(events, window_start, window_end, source_name, source_url, is_cdm_fallback)

    if data_sufficient and not signals:
        notes_parts.append(
            "В охватываемом периоде значимых сближений по каталогизированным объектам не выявлено. "
            "Это не означает нулевой риск от некаталогизированных микрометеороидов/мусора — по ним "
            "доступны только статистические, а не индивидуальные оценки."
        )

    overall_confidence = ConfidenceLevel.insufficient_data if not data_sufficient else (
        ConfidenceLevel.low if is_cdm_fallback else (ConfidenceLevel.medium if signals else ConfidenceLevel.high)
    )

    return FactorAssessment(
        factor=FactorKind.conjunction_mmod,
        title="Сближения и MMOD (микрометеороиды/орбитальный мусор)",
        mechanism_description=(
            "Использует публичный отчёт CelesTrak SOCRATES о расчётных сближениях каталогизированных "
            "объектов со станцией как прокси-показатель обстановки по мусору (при недоступности "
            "CelesTrak — резервно Space-Track cdm_public, если настроены учётные данные); "
            "статистический фон MMOD не даёт индивидуального прогноза по частицам."
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


def _parse_tca(tca_raw: str | None) -> datetime | None:
    if not tca_raw:
        return None
    # CelesTrak's real SOCRATES export uses "YYYY Mon DD HH:MM:SS.fff";
    # Space-Track's cdm_public TCA is ISO8601 ("YYYY-MM-DDTHH:MM:SS.ffffff"
    # per the CCSDS-derived CDM spec). Other formats are tolerated
    # defensively in case either export variant changes.
    for fmt in (
        "%Y %b %d %H:%M:%S.%f",
        "%Y %b %d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(tca_raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _events_to_signals(
    events: list[dict],
    window_start: datetime,
    window_end: datetime,
    source_name: str,
    source_url: str,
    is_cdm_fallback: bool,
) -> list[Signal]:
    """Shared between assess_current (CelesTrak SOCRATES, with an optional
    Space-Track cdm_public fallback) and assess_historical (Space-Track
    cdm_public archive only) — both produce the same event shape (tca,
    miss_distance_km, max_probability, other_object) and need identical
    severity/confidence handling."""
    signals: list[Signal] = []
    for ev in events:
        tca = _parse_tca(ev.get("tca"))
        if tca and not (window_start <= tca <= window_end):
            continue
        severity = _severity_from_event(ev.get("miss_distance_km"), ev.get("max_probability"))
        signals.append(
            Signal(
                factor=FactorKind.conjunction_mmod,
                label=f"Сближение с объектом «{ev.get('other_object')}»",
                description=(
                    f"Расчётное сближение отслеживаемого объекта со станцией ({source_name}). "
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
                source_name=source_name,
                source_url=source_url,
                published_at=None,
                rule_applied=(
                    "severity = вероятность/1e-4 при наличии; иначе ступенчато по минимальной "
                    "дальности (<1км=0.9, <5км=0.6, <20км=0.3, иначе 0.1)"
                ),
                limitations=(
                    "Прокси-показатель обстановки вокруг станции, не индивидуальная оценка риска "
                    "для скафандра или конкретного члена экипажа."
                    + (
                        " Резервный источник: названия полей cdm_public определены динамически "
                        "во время запроса, а не проверены заранее живым вызовом разработчика."
                        if is_cdm_fallback
                        else ""
                    )
                ),
                confidence=(
                    ConfidenceLevel.low
                    if is_cdm_fallback
                    else (ConfidenceLevel.medium if tca else ConfidenceLevel.low)
                ),
                confidence_rationale=(
                    "Резервный источник Space-Track cdm_public, схема определена динамически — "
                    "используется, но с пониженной уверенностью."
                    if is_cdm_fallback
                    else (
                        "Публичный расчёт CelesTrak на основе каталогизированных элементов; "
                        "не учитывает некаталогизированные мелкие фрагменты (MMOD)."
                    )
                ),
            )
        )
    return signals


async def assess_historical(cutoff: datetime, window_start: datetime, window_end: datetime) -> FactorAssessment:
    """CelesTrak SOCRATES itself has no archive (only ever a rolling
    ~7-day-ahead forecast), but Space-Track's cdm_public class keeps its
    full history — so a genuine "forecast from the past" replay (T4) is
    possible for conjunctions too, when credentials are configured, with
    the same strict publication-time cutoff DONKI already applies (see
    clients/spacetrack.py::fetch_cdm_conjunctions_for_window)."""
    if not (settings.spacetrack_identity and settings.spacetrack_password):
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
                "исторической даты фактор сближений не рассчитывается. Задайте "
                "EVA_SPACETRACK_IDENTITY/EVA_SPACETRACK_PASSWORD, чтобы включить историческую "
                "выборку по официальному архиву Space-Track cdm_public. До тех пор используйте "
                "только оценку космической погоды как проверяемую линию анализа для этого периода."
            ),
        )

    cache_name = f"spacetrack_cdm_hist_{cutoff.date()}"
    cache = registry.get_or_register(cache_name, settings.spacetrack_query_url, ttl_seconds=3600 * 24 * 30)

    events: list[dict] = []
    data_sufficient = True
    notes_parts: list[str] = [
        f"Прогноз из прошлого: использован официальный архив Space-Track cdm_public, отфильтрованный "
        f"по времени публикации CDM (`CREATION_DATE`-подобное поле) не позже {cutoff.isoformat()}."
    ]
    try:
        payload, _status, _fresh = await cache.get(
            lambda: spacetrack.fetch_cdm_conjunctions_for_window(settings.iss_norad_id, cutoff)
        )
        events = spacetrack.parse_cdm_events(payload, settings.iss_norad_id)
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        data_sufficient = False
        notes_parts = [f"Space-Track cdm_public (исторический архив) недоступен: {exc}."]

    signals = _events_to_signals(
        events,
        window_start,
        window_end,
        source_name="Space-Track cdm_public (исторический архив)",
        source_url=settings.spacetrack_query_url,
        is_cdm_fallback=True,
    )

    if data_sufficient and not signals:
        notes_parts.append(
            "В охватываемом периоде значимых сближений по данным архива не выявлено. Это не означает "
            "нулевой риск от некаталогизированных микрометеороидов/мусора."
        )

    overall_confidence = ConfidenceLevel.insufficient_data if not data_sufficient else ConfidenceLevel.low

    return FactorAssessment(
        factor=FactorKind.conjunction_mmod,
        title="Сближения и MMOD (прогноз из прошлого)",
        mechanism_description=(
            "Строгий прогноз из прошлого по официальному архиву Space-Track cdm_public: используются "
            f"только CDM, опубликованные к моменту отсечения {cutoff.isoformat()}. Названия полей схемы "
            "определены динамически по live-ответу сервера (см. clients/spacetrack.py), поэтому "
            "уверенность в сигналах понижена."
        ),
        data_sufficient=data_sufficient,
        signals=signals,
        overall_confidence=overall_confidence,
        notes=" ".join(notes_parts),
    )
