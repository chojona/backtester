"""Synthetic-only HAR-RV estimation and chronological evaluation for NQ research.

This module has no historical data loader. Pass complete synthetic DailyVariation
sessions; historical fitting remains gated outside this mathematical foundation.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite, sqrt
from typing import Sequence

import numpy as np

from backtester.nq_research import build_har_rows, require_strict_sessions


FEATURES = ("rv_1", "rv_5", "rv_22")


@dataclass(frozen=True)
class OLSFit:
    intercept: float
    coefficients: tuple[float, float, float]
    rank: int
    condition_number: float

    def predict(self, row: dict) -> float:
        return self.intercept + fsum(b * float(row[name]) for b, name in zip(self.coefficients, FEATURES))


@dataclass(frozen=True)
class Forecast:
    target_date: object
    actual: float
    har: float
    persistence: float
    historical_mean: float
    training_count: int


def synthetic_har_rows(sessions, *, certification_version: str) -> tuple[dict, ...]:
    """Build rows, rejecting any missing observed session or segment transition.

    The caller is responsible for providing synthetic sessions. The Tier A labels
    in synthetic fixtures exercise the input gate; they are not certifications.
    """
    sessions = require_strict_sessions(sessions, certification_version=certification_version)
    if any(b.session_ordinal != a.session_ordinal + 1 or
           b.research_segment_id != a.research_segment_id
           for a, b in zip(sessions, sessions[1:])):
        raise ValueError("Missing session or research segment transition")
    return tuple(build_har_rows(sessions, certification_version=certification_version))


def _validate_rows(rows: Sequence[dict]) -> tuple[dict, ...]:
    rows = tuple(rows)
    previous = None
    for row in rows:
        values = (row["rv_1"], row["rv_5"], row["rv_22"], row["target_rv"])
        if any(not isfinite(float(v)) or float(v) < 0 for v in values):
            raise ValueError("HAR rows require finite nonnegative realized variance")
        if row["feature_date"] >= row["target_date"] or row["as_of"] >= row["target_available_at"]:
            raise ValueError("HAR feature/target look-ahead")
        if previous is not None and (row["feature_date"] <= previous["feature_date"] or
                                     row["target_date"] <= previous["target_date"] or
                                     previous["target_available_at"] > row["as_of"] or
                                     row["research_segment_id"] != previous["research_segment_id"]):
            raise ValueError("HAR rows are not chronological and causally available")
        previous = row
    return rows


def fit_ols(rows: Sequence[dict], *, max_condition: float = 1e10) -> OLSFit:
    """SVD least squares on standardized features; reject unstable rank/design."""
    rows = _validate_rows(rows)
    if len(rows) < 5:
        raise ValueError("At least five training rows are required")
    x = np.array([[float(r[k]) for k in FEATURES] for r in rows], dtype=float)
    y = np.array([float(r["target_rv"]) for r in rows], dtype=float)
    center = x.mean(axis=0)
    scale = x.std(axis=0)
    if np.any(scale <= 0) or not np.all(np.isfinite(scale)):
        raise ValueError("Constant or invalid HAR feature")
    design = np.column_stack((np.ones(len(rows)), (x - center) / scale))
    singular = np.linalg.svd(design, compute_uv=False)
    condition = float(singular[0] / singular[-1]) if singular[-1] else float("inf")
    if not isfinite(condition) or condition > max_condition:
        raise ValueError("Ill-conditioned HAR design")
    beta, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank != 4:
        raise ValueError("Rank-deficient HAR design")
    slopes = beta[1:] / scale
    intercept = beta[0] - np.dot(slopes, center)
    result = OLSFit(float(intercept), tuple(float(v) for v in slopes), int(rank), condition)
    if not all(isfinite(v) for v in (result.intercept, *result.coefficients)):
        raise ValueError("Nonfinite HAR fit")
    return result


def chronological_split(rows: Sequence[dict], *, train: int, validation: int):
    rows = _validate_rows(rows)
    if train < 5 or validation < 1 or train + validation >= len(rows):
        raise ValueError("Need nonempty chronological training, validation and test blocks")
    return rows[:train], rows[train:train + validation], rows[train + validation:]


def _forecast(model: OLSFit, history: Sequence[dict], row: dict) -> Forecast:
    if history[-1]["target_available_at"] > row["as_of"]:
        raise ValueError("Training target is unavailable at forecast time")
    return Forecast(row["target_date"], float(row["target_rv"]), model.predict(row),
                    float(row["rv_1"]), fsum(float(r["target_rv"]) for r in history) / len(history),
                    len(history))


def evaluate_fixed(rows: Sequence[dict], *, train: int, validation: int):
    """Fit on training once; evaluate validation and test without refitting."""
    tr, va, te = chronological_split(rows, train=train, validation=validation)
    model = fit_ols(tr)
    return {"fit": model,
            "validation": tuple(_forecast(model, tr, row) for row in va),
            "test": tuple(_forecast(model, tr, row) for row in te)}


def evaluate_walk_forward(rows: Sequence[dict], *, train: int, validation: int,
                          window: str = "expanding", rolling_size: int | None = None):
    """Refit before each validation/test target using only then-available labels."""
    tr, va, te = chronological_split(rows, train=train, validation=validation)
    if window not in ("expanding", "rolling"):
        raise ValueError("Window must be expanding or rolling")
    if window == "rolling" and (rolling_size is None or rolling_size < 5 or rolling_size > train):
        raise ValueError("Rolling size must be between five and initial training size")
    result = {"validation": [], "test": []}
    all_rows = tr + va + te
    for index in range(train, len(all_rows)):
        row = all_rows[index]
        available = [r for r in all_rows[:index] if r["target_available_at"] <= row["as_of"]]
        history = available if window == "expanding" else available[-rolling_size:]
        if len(history) < 5:
            raise ValueError("Too few available training targets")
        result["validation" if index < train + validation else "test"].append(
            _forecast(fit_ols(history), history, row))
    return {key: tuple(value) for key, value in result.items()}


def metrics(forecasts: Sequence[Forecast], *, benchmark: Sequence[float] | None = None
            ) -> dict[str, dict[str, float]]:
    """Score forecasts against one benchmark sequence (the local mean by default).

    Pass the same explicit benchmark to each evaluation for comparable OOS R².
    The default preserves evaluation-specific historical-mean metrics.
    """
    forecasts = tuple(forecasts)
    if not forecasts:
        raise ValueError("No forecasts")
    benchmark = tuple(f.historical_mean for f in forecasts) if benchmark is None else tuple(benchmark)
    if len(benchmark) != len(forecasts) or any(not isfinite(float(v)) for v in benchmark):
        raise ValueError("Benchmark must be finite and match the forecast count")
    baseline_sse = fsum((f.actual - float(b)) ** 2 for f, b in zip(forecasts, benchmark))
    if not isfinite(baseline_sse) or baseline_sse <= 0:
        raise ValueError("Benchmark OOS R² denominator must be finite and positive")
    output = {}
    for name in ("har", "persistence", "historical_mean"):
        errors = [f.actual - getattr(f, name) for f in forecasts]
        sse = fsum(e * e for e in errors)
        output[name] = {"n": len(errors), "mae": fsum(abs(e) for e in errors) / len(errors),
                        "rmse": sqrt(sse / len(errors)), "oos_r2": 1 - sse / baseline_sse}
    return output


def comparison_metrics(evaluations: dict[str, Sequence[Forecast]], *, benchmark_from: str = "fixed"
                       ) -> dict[str, object]:
    """Return common-benchmark scores alongside each evaluation's local scores.

    Every evaluation must forecast the same ordered target dates and actuals.
    The named evaluation supplies one frozen historical-mean benchmark sequence.
    """
    forecasts = {name: tuple(values) for name, values in evaluations.items()}
    if benchmark_from not in forecasts:
        raise ValueError("Benchmark evaluation is missing")
    reference = forecasts[benchmark_from]
    if not reference:
        raise ValueError("No forecasts")
    identity = tuple((f.target_date, f.actual) for f in reference)
    if any(tuple((f.target_date, f.actual) for f in values) != identity
           for values in forecasts.values()):
        raise ValueError("Evaluations must have identical ordered targets and actuals")
    benchmark = tuple(f.historical_mean for f in reference)
    return {"benchmark_from": benchmark_from, "benchmark": benchmark,
            "common": {name: metrics(values, benchmark=benchmark) for name, values in forecasts.items()},
            "evaluation_specific": {name: metrics(values) for name, values in forecasts.items()}}
