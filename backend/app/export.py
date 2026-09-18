"""Persists computed results to disk (for reproducibility, criterion T8) and
builds the user-facing export bundle (JSON + CSV in one zip, criterion:
functional requirement #5 / "Пользователь сохраняет расчёт и выгружает его
в читаемом и машиночитаемом виде").
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

from .config import settings
from .models import AnalyzeResponse

RESULTS_DIR = settings.cache_dir.parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def save_result(resp: AnalyzeResponse) -> Path:
    path = RESULTS_DIR / f"{resp.result_id}.json"
    path.write_text(resp.model_dump_json(indent=2))
    return path


def load_result(result_id: str) -> AnalyzeResponse | None:
    path = RESULTS_DIR / f"{result_id}.json"
    if not path.exists():
        return None
    return AnalyzeResponse.model_validate_json(path.read_text())


def _windows_csv(resp: AnalyzeResponse) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "window_index", "start", "end", "duration_hours", "combined_score",
            "data_completeness", "is_recommended", "is_tied_with_recommended",
            "daylight_fraction", "factor", "overlap_minutes", "max_severity",
            "time_weighted_severity", "driving_signals",
        ]
    )
    for idx, w in enumerate(resp.windows):
        if not w.factor_contributions:
            writer.writerow([idx, w.start, w.end, w.duration_hours, w.combined_score,
                              w.data_completeness.value, w.is_recommended, w.is_tied_with_recommended,
                              f"{w.daylight_fraction:.3f}", "", "", "", "", ""])
            continue
        for c in w.factor_contributions:
            writer.writerow([
                idx, w.start, w.end, w.duration_hours, w.combined_score,
                w.data_completeness.value, w.is_recommended, w.is_tied_with_recommended,
                f"{w.daylight_fraction:.3f}", c.factor.value, c.overlap_minutes, c.max_severity,
                f"{c.time_weighted_severity:.3f}", "; ".join(c.driving_signals),
            ])
    return buf.getvalue()


def _signals_csv(resp: AnalyzeResponse) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "factor", "label", "severity", "provenance", "start", "end", "is_time_uncertain",
            "value", "unit", "source_name", "source_url", "published_at", "rule_applied",
            "confidence", "confidence_rationale", "limitations",
        ]
    )
    for fa in resp.factors:
        for s in fa.signals:
            writer.writerow([
                s.factor.value, s.label, s.severity, s.provenance.value,
                s.observed_or_expected_start, s.observed_or_expected_end, s.is_time_uncertain,
                s.value, s.unit, s.source_name, s.source_url, s.published_at,
                s.rule_applied, s.confidence.value, s.confidence_rationale, s.limitations,
            ])
    return buf.getvalue()


def build_export_zip(resp: AnalyzeResponse) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.json", resp.model_dump_json(indent=2))
        zf.writestr("windows.csv", _windows_csv(resp))
        zf.writestr("signals.csv", _signals_csv(resp))
        zf.writestr(
            "README.txt",
            "Отчёт по прогнозированию внешних рисков и планированию ВКД на МКС.\n"
            f"result_id: {resp.result_id}\n"
            f"algorithm_version: {resp.algorithm_version}\n"
            f"сгенерировано: {resp.generated_at.isoformat()}\n\n"
            "report.json — полный расчёт (параметры запроса, орбита, факторы, окна, рекомендация).\n"
            "windows.csv — сравнение окон по вкладу каждого фактора.\n"
            "signals.csv — все объясняющие сигналы с источником, временем публикации и правилом расчёта.\n",
        )
    return buf.getvalue()
