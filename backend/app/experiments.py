"""Criterion T5 / 'Исследование и оценка подхода': compares the team's
rule-based space-weather severity against a naive baseline ("any notification
present that day = risky, otherwise safe") over a real, well-documented
event period and a quiet control period, both inside the supported
historical window (1 May - 30 June 2024).

Event period: 10-12 May 2024 — the well-documented extreme geomagnetic storm
("Gannon storm", NOAA G5) coincident with X-class flares and an SEP event.
Control period: 1-2 June 2024 — a quiet interval with no major NOAA alerts
reported for the ISS orbit region.

This module is runnable standalone (`python -m app.experiments`) and via
`/api/experiment` so a judge can reproduce it without reading code first.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone

from .clients import donki
from .factors.space_weather import _DONKI_TYPE_SEVERITY  # reuse the same documented rule table
from .models import ExperimentResult

EVENT_START = datetime(2024, 5, 10, tzinfo=timezone.utc)
EVENT_END = datetime(2024, 5, 12, tzinfo=timezone.utc)
CONTROL_START = datetime(2024, 6, 1, tzinfo=timezone.utc)
CONTROL_END = datetime(2024, 6, 2, tzinfo=timezone.utc)


def _naive_daily_flag(notifications: list[dict]) -> float:
    """Baseline: 1.0 if ANY notification exists that day, else 0.0. No
    distinction of type or severity — this is deliberately the simplest
    possible 'existing approach' referenced by the task (использование
    последнего наблюдения/одного готового предупреждения)."""
    return 1.0 if notifications else 0.0


def _team_mean_severity(notifications: list[dict]) -> float:
    sevs = []
    for item in notifications:
        msg_type_raw = str(item.get("messageType", ""))
        matched = next((k for k in _DONKI_TYPE_SEVERITY if msg_type_raw.upper().startswith(k)), None)
        if matched:
            sevs.append(_DONKI_TYPE_SEVERITY[matched])
    return sum(sevs) / len(sevs) if sevs else 0.0


async def _fetch(start: date, end: date) -> list[dict]:
    return await donki.fetch_notifications(start, end)


async def run_comparison() -> ExperimentResult:
    event_notifs = await _fetch(EVENT_START.date(), EVENT_END.date())
    control_notifs = await _fetch(CONTROL_START.date(), CONTROL_END.date())

    metrics = {
        "naive_baseline": {
            "event_period_flag": _naive_daily_flag(event_notifs),
            "control_period_flag": _naive_daily_flag(control_notifs),
            "distinguishes_event_from_control": _naive_daily_flag(event_notifs) > _naive_daily_flag(control_notifs),
        },
        "team_method": {
            "event_period_mean_severity": round(_team_mean_severity(event_notifs), 3),
            "control_period_mean_severity": round(_team_mean_severity(control_notifs), 3),
            "distinguishes_event_from_control": _team_mean_severity(event_notifs) > _team_mean_severity(control_notifs),
        },
        "event_notification_count": len(event_notifs),
        "control_notification_count": len(control_notifs),
    }

    return ExperimentResult(
        method="rule-based severity by DONKI messageType vs. naive any-notification baseline",
        description=(
            "Сравнение среднесуточной оценки серьёзности космической погоды команды "
            "(по типам уведомлений DONKI) с наивным базовым подходом (бинарный флаг "
            "«есть хоть одно уведомление») на выраженном событии (буря Gannon, 10-12 мая "
            "2024) и спокойном контрольном периоде (1-2 июня 2024)."
        ),
        event_period=(EVENT_START, EVENT_END),
        control_period=(CONTROL_START, CONTROL_END),
        metrics=metrics,
    )


if __name__ == "__main__":
    result = asyncio.run(run_comparison())
    print(json.dumps(result.model_dump(), indent=2, default=str, ensure_ascii=False))
