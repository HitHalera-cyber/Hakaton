"""HTTP API surface. Kept thin on purpose: request validation + orchestration
only, all decision logic lives in analysis.py/factors/orbit.py (criterion
T7: "разделение получения данных, расчётов и интерфейса")."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from . import experiments, export
from .analysis import compare_dates, run_analysis
from .cache import registry
from .config import settings
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CompareDatesRequest,
    CompareDatesResponse,
    ExperimentResult,
    Mode,
    SourceStatus,
)

logger = logging.getLogger("eva.api")
router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "algorithm_version": settings.algorithm_version}


@router.get("/config")
async def config() -> dict:
    """Exposes the task's fixed operating bounds to the frontend so the UI
    can validate client-side without duplicating magic numbers."""
    return {
        "min_duration_hours": settings.min_duration_hours,
        "max_duration_hours": settings.max_duration_hours,
        "max_search_period_hours": settings.max_search_period_hours,
        "forecast_horizon_hours": settings.forecast_horizon_hours,
        "historical_start": settings.historical_start,
        "historical_end": settings.historical_end,
        "iss_norad_id": settings.iss_norad_id,
    }


def _check_historical_range(reference_time) -> None:
    hist_start = settings.historical_start
    hist_end = settings.historical_end
    if not (hist_start <= reference_time.isoformat() <= hist_end):
        raise HTTPException(
            status_code=422,
            detail=f"Историческая дата должна быть в диапазоне {hist_start[:10]}..{hist_end[:10]}",
        )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    if req.mode == Mode.historical:
        _check_historical_range(req.reference_time)
    try:
        resp = await run_analysis(req)
    except Exception as exc:  # noqa: BLE001 - convert to a clean user-facing error, never a silent "all clear"
        logger.exception("analysis failed")
        raise HTTPException(status_code=502, detail=f"Не удалось выполнить расчёт: {exc}") from exc
    export.save_result(resp)
    return resp


@router.post("/compare-dates", response_model=CompareDatesResponse)
async def compare_dates_route(req: CompareDatesRequest) -> CompareDatesResponse:
    if req.mode == Mode.historical:
        _check_historical_range(req.date_a)
        _check_historical_range(req.date_b)
    try:
        resp = await compare_dates(req)
    except Exception as exc:  # noqa: BLE001 - convert to a clean user-facing error, never a silent "all clear"
        logger.exception("date comparison failed")
        raise HTTPException(status_code=502, detail=f"Не удалось сравнить даты: {exc}") from exc
    export.save_result(resp.result_a)
    export.save_result(resp.result_b)
    return resp


@router.get("/results/{result_id}", response_model=AnalyzeResponse)
async def get_result(result_id: str) -> AnalyzeResponse:
    resp = export.load_result(result_id)
    if resp is None:
        raise HTTPException(status_code=404, detail="Результат не найден")
    return resp


@router.get("/export/{result_id}")
async def export_result(result_id: str) -> Response:
    resp = export.load_result(result_id)
    if resp is None:
        raise HTTPException(status_code=404, detail="Результат не найден")
    payload = export.build_export_zip(resp)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="eva-report-{result_id}.zip"'},
    )


@router.get("/sources/status", response_model=list[SourceStatus])
async def sources_status() -> list[SourceStatus]:
    return registry.all_statuses()


class SourceToggleRequest(BaseModel):
    name: str
    disabled: bool | None = None
    frozen: bool | None = None


@router.post("/sources/toggle", response_model=SourceStatus)
async def toggle_source(req: SourceToggleRequest) -> SourceStatus:
    if not registry.has(req.name):
        raise HTTPException(status_code=404, detail=f"Неизвестный источник: {req.name}")
    cache = registry.get(req.name)
    if req.disabled is not None:
        (cache.disable if req.disabled else cache.enable)()
    if req.frozen is not None:
        (cache.freeze if req.frozen else cache.unfreeze)()
    return cache.status


@router.get("/experiment", response_model=ExperimentResult)
async def experiment() -> ExperimentResult:
    try:
        return await experiments.run_comparison()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Эксперимент не выполнен: {exc}") from exc
