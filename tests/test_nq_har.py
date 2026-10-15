"""Synthetic-only HAR-RV fitting checks with independent SciPy OLS reference."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from math import sin, cos, fsum, sqrt

import numpy as np
import pytest

from backtester.nq_har import (
    chronological_split, comparison_metrics, evaluate_fixed, evaluate_walk_forward, fit_ols, metrics,
    synthetic_har_rows,
)
from backtester.nq_research import DailyVariation

VERSION = "synthetic-nq-only"


def sessions(n=120):
    start = datetime(2022, 1, 1, 22, tzinfo=timezone.utc)
    return [DailyVariation(date(2022, 1, 1) + timedelta(days=i), i,
                           start + timedelta(days=i),
                           2.0 + 0.002 * i + 0.35 * sin(i * 0.37) + 0.18 * cos(i * 0.11),
                           "A", VERSION, 1, True) for i in range(n)]


def rows():
    return synthetic_har_rows(sessions(), certification_version=VERSION)


def test_lags_and_next_session_target_are_causal():
    source = sessions()
    actual = synthetic_har_rows(source, certification_version=VERSION)
    first = actual[0]
    assert len(actual) == len(source) - 22
    assert first["rv_1"] == source[21].rv
    assert first["rv_5"] == pytest.approx(sum(s.rv for s in source[17:22]) / 5)
    assert first["rv_22"] == pytest.approx(sum(s.rv for s in source[:22]) / 22)
    assert first["target_rv"] == source[22].rv
    changed = source.copy()
    changed[22] = replace(changed[22], rv=10.0)
    altered = synthetic_har_rows(changed, certification_version=VERSION)
    assert all(altered[0][k] == first[k] for k in ("rv_1", "rv_5", "rv_22"))
    assert altered[0]["target_rv"] == 10.0
    assert altered[1]["rv_1"] == 10.0


def test_every_origin_and_availability_timestamp():
    source = sessions()
    for target_index, row in enumerate(rows(), start=22):
        feature = source[target_index - 1]
        target = source[target_index]
        assert row["feature_date"] == feature.trading_date
        assert row["as_of"] == feature.available_at
        assert row["target_date"] == target.trading_date
        assert row["target_available_at"] == target.available_at
        assert row["as_of"] < row["target_available_at"]
        assert row["rv_1"] == feature.rv
        assert row["rv_5"] == pytest.approx(fsum(s.rv for s in source[target_index - 5:target_index]) / 5)
        assert row["rv_22"] == pytest.approx(fsum(s.rv for s in source[target_index - 22:target_index]) / 22)
        if target_index > 22:
            assert source[target_index - 1].available_at == row["as_of"]


def reference_qr_ols(design, targets):
    """Independent modified Gram-Schmidt and triangular back substitution."""
    columns = [[float(row[j]) for row in design] for j in range(4)]
    orthogonal = []
    upper = [[0.0] * 4 for _ in range(4)]
    for j, raw in enumerate(columns):
        work = raw[:]
        for i, q in enumerate(orthogonal):
            upper[i][j] = fsum(a * b for a, b in zip(q, work))
            work = [a - upper[i][j] * b for a, b in zip(work, q)]
        upper[j][j] = sqrt(fsum(a * a for a in work))
        orthogonal.append([a / upper[j][j] for a in work])
    rhs = [fsum(a * b for a, b in zip(q, targets)) for q in orthogonal]
    beta = [0.0] * 4
    for j in range(3, -1, -1):
        beta[j] = (rhs[j] - fsum(upper[j][k] * beta[k] for k in range(j + 1, 4))) / upper[j][j]
    return beta


def test_ols_matches_independent_qr_reference():
    training = rows()[:55]
    fit = fit_ols(training)
    design = np.array([[1.0, r["rv_1"], r["rv_5"], r["rv_22"]] for r in training])
    targets = np.array([r["target_rv"] for r in training])
    reference = reference_qr_ols(design, targets)
    assert fit.rank == 4
    np.testing.assert_allclose((fit.intercept, *fit.coefficients), reference, rtol=1e-8, atol=1e-10)
    np.testing.assert_allclose([fit.predict(r) for r in training], design @ reference, rtol=1e-8)


def test_chronological_fixed_and_walk_forward_metrics():
    data = rows()
    train, validation, test = chronological_split(data, train=50, validation=20)
    assert len(train) == 50 and len(validation) == 20 and len(test) == len(data) - 70
    assert train[-1]["target_date"] < validation[0]["target_date"] < test[0]["target_date"]
    fixed = evaluate_fixed(data, train=50, validation=20)
    expanding = evaluate_walk_forward(data, train=50, validation=20)
    rolling = evaluate_walk_forward(data, train=50, validation=20, window="rolling", rolling_size=30)
    assert len(fixed["validation"]) == len(expanding["validation"]) == 20
    assert fixed["validation"][0].har == pytest.approx(expanding["validation"][0].har)
    assert [f.training_count for f in expanding["validation"]] == list(range(50, 70))
    assert {f.training_count for f in rolling["validation"] + rolling["test"]} == {30}
    for forecast_set in (fixed["validation"], expanding["test"], rolling["test"]):
        report = metrics(forecast_set)
        assert set(report) == {"har", "persistence", "historical_mean"}
        assert report["historical_mean"]["oos_r2"] == pytest.approx(0.0)
        assert all(np.isfinite(v) for m in report.values() for v in m.values())


def reference_walk_forward(data, train, validation, window=None):
    """Separate forecast loop, QR fit, and manually selected eligible indices."""
    result = {"validation": [], "test": []}
    for origin in range(train, len(data)):
        eligible = tuple(i for i in range(origin) if data[i]["target_available_at"] <= data[origin]["as_of"])
        chosen = eligible if window is None else eligible[-window:]
        history = [data[i] for i in chosen]
        design = [[1.0, *(r[k] for k in ("rv_1", "rv_5", "rv_22"))] for r in history]
        beta = reference_qr_ols(design, [r["target_rv"] for r in history])
        current = data[origin]
        forecast = (current["target_date"], current["target_rv"],
                    fsum(a * b for a, b in zip(beta, [1.0, current["rv_1"], current["rv_5"], current["rv_22"]])),
                    current["rv_1"], fsum(r["target_rv"] for r in history) / len(history), len(history))
        result["validation" if origin < train + validation else "test"].append(forecast)
    return result


@pytest.mark.parametrize("window", [None, 30])
def test_independent_walk_forward_forecasts_and_exact_rolling_window(window):
    data = rows()
    actual = evaluate_walk_forward(data, train=50, validation=20,
                                   window="expanding" if window is None else "rolling", rolling_size=window)
    reference = reference_walk_forward(data, 50, 20, window)
    for split in ("validation", "test"):
        assert len(actual[split]) == len(reference[split])
        for forecast, expected in zip(actual[split], reference[split]):
            assert forecast.target_date == expected[0]
            assert forecast.actual == expected[1]
            assert forecast.har == pytest.approx(expected[2], abs=1e-9)
            assert forecast.persistence == expected[3]
            assert forecast.historical_mean == pytest.approx(expected[4])
            assert forecast.training_count == expected[5]
    if window is not None:
        # The 50th origin must retain indices 20..49; each later origin shifts by one.
        for origin in range(50, len(data)):
            eligible = [i for i in range(origin) if data[i]["target_available_at"] <= data[origin]["as_of"]]
            assert eligible[-window:] == list(range(origin - window, origin))


def test_common_benchmark_scores_and_local_scores_are_both_retained():
    data = rows()
    evaluations = {
        "fixed": evaluate_fixed(data, train=50, validation=20)["test"],
        "expanding": evaluate_walk_forward(data, train=50, validation=20)["test"],
        "rolling": evaluate_walk_forward(data, train=50, validation=20, window="rolling", rolling_size=30)["test"],
    }
    report = comparison_metrics(evaluations)
    baseline = report["benchmark"]
    assert baseline == tuple(f.historical_mean for f in evaluations["fixed"])
    baseline_sse = fsum((f.actual - b) ** 2 for f, b in zip(evaluations["fixed"], baseline))
    for name, forecasts in evaluations.items():
        assert report["evaluation_specific"][name] == metrics(forecasts)
        for model in ("har", "persistence", "historical_mean"):
            errors = [f.actual - getattr(f, model) for f in forecasts]
            scored = report["common"][name][model]
            assert scored["mae"] == pytest.approx(fsum(abs(e) for e in errors) / len(errors))
            assert scored["rmse"] == pytest.approx(sqrt(fsum(e * e for e in errors) / len(errors)))
            assert scored["oos_r2"] == pytest.approx(1 - fsum(e * e for e in errors) / baseline_sse)
    assert report["common"]["expanding"]["historical_mean"]["oos_r2"] != 0
    bad = dict(evaluations)
    bad["rolling"] = tuple(replace(f, actual=f.actual + 1) for f in bad["rolling"])
    with pytest.raises(ValueError, match="identical"):
        comparison_metrics(bad)
    with pytest.raises(ValueError, match="match the forecast count"):
        metrics(evaluations["fixed"], benchmark=[1.0])


def test_missing_sessions_and_invalid_inputs_are_rejected():
    source = sessions()
    with pytest.raises(ValueError, match="Missing session"):
        synthetic_har_rows(source[:40] + source[41:], certification_version=VERSION)
    with pytest.raises(ValueError, match="segment"):
        synthetic_har_rows(source[:40] + [replace(s, research_segment_id=2) for s in source[40:]],
                           certification_version=VERSION)
    with pytest.raises(ValueError, match="Tier A"):
        synthetic_har_rows(source[:40] + [replace(source[40], quality_tier="B")] + source[41:],
                           certification_version=VERSION)
    with pytest.raises(ValueError, match="nonnegative"):
        fit_ols([dict(r, target_rv=-1.0) if i == 0 else r for i, r in enumerate(rows()[:40])])
    with pytest.raises(ValueError, match="Constant"):
        fit_ols([dict(r, rv_1=1.0) for r in rows()[:40]])
    with pytest.raises(ValueError, match="chronological"):
        fit_ols(list(reversed(rows()[:40])))


def test_future_label_cannot_change_prior_walk_forward_forecast():
    data = rows()
    original = evaluate_walk_forward(data, train=50, validation=20)
    altered = [dict(r) for r in data]
    altered[75]["target_rv"] *= 10
    rerun = evaluate_walk_forward(altered, train=50, validation=20)
    assert original["validation"] == rerun["validation"]
    assert [f.har for f in original["test"][:6]] == [f.har for f in rerun["test"][:6]]
    assert original["test"][6].har != rerun["test"][6].har
    leak = [dict(r) for r in data]
    leak[51]["target_available_at"] = leak[52]["as_of"] + timedelta(seconds=1)
    with pytest.raises(ValueError, match="causally available"):
        evaluate_walk_forward(leak, train=50, validation=20)


def test_numerical_instability_and_split_edges():
    data = rows()
    with pytest.raises(ValueError, match="Ill-conditioned"):
        fit_ols(data[:40], max_condition=1.01)
    with pytest.raises(ValueError, match="nonempty"):
        chronological_split(data, train=50, validation=len(data) - 50)
    with pytest.raises(ValueError, match="Rolling size"):
        evaluate_walk_forward(data, train=50, validation=20, window="rolling", rolling_size=3)


def test_zero_near_zero_and_large_spike_rv():
    source = sessions()
    changed = [replace(s, rv=0.0 if i % 11 == 0 else 1e-12 if i % 13 == 0 else s.rv)
               for i, s in enumerate(source)]
    changed[83] = replace(changed[83], rv=1e6)
    data = synthetic_har_rows(changed, certification_version=VERSION)
    assert any(r["target_rv"] == 0 for r in data)
    assert any(r["rv_1"] == 1e-12 for r in data)
    assert max(r["target_rv"] for r in data) == 1e6
    for evaluation in (evaluate_fixed(data, train=50, validation=20),
                       evaluate_walk_forward(data, train=50, validation=20)):
        assert all(np.isfinite(f.har) for f in evaluation["validation"] + evaluation["test"])
    assert all(np.isfinite(v) for scores in metrics(evaluation["test"]).values() for v in scores.values())
    with pytest.raises(ValueError, match="Constant"):
        fit_ols([dict(r, rv_1=0.0) for r in rows()[:40]])


def test_negative_raw_forecast_is_not_clipped():
    data = [dict(r) for r in rows()]
    for row in data[:50]:
        row["target_rv"] = 10 - row["rv_1"]
    data[50]["rv_1"] = 20.0
    forecast = evaluate_fixed(data, train=50, validation=20)["validation"][0]
    assert forecast.har == pytest.approx(-10.0, abs=1e-9)
    assert forecast.har < 0


def test_high_correlation_and_ill_conditioned_design():
    base = rows()[:50]
    correlated = [dict(r, rv_5=r["rv_1"] + 1e-3 * sin(i),
                       rv_22=r["rv_1"] + 1e-3 * cos(i)) for i, r in enumerate(base)]
    fit = fit_ols(correlated)
    assert fit.rank == 4 and fit.condition_number > 100
    design = [[1.0, r["rv_1"], r["rv_5"], r["rv_22"]] for r in correlated]
    reference = reference_qr_ols(design, [r["target_rv"] for r in correlated])
    np.testing.assert_allclose((fit.intercept, *fit.coefficients), reference, rtol=1e-6, atol=1e-6)
    near_singular = [dict(r, rv_5=r["rv_1"] + 1e-12 * sin(i),
                          rv_22=r["rv_1"] + 1e-12 * cos(i)) for i, r in enumerate(base)]
    with pytest.raises(ValueError, match="Ill-conditioned"):
        fit_ols(near_singular)
    exact = [dict(r, rv_5=r["rv_1"]) for r in base]
    with pytest.raises(ValueError, match="Ill-conditioned|Rank-deficient"):
        fit_ols(exact)


@pytest.mark.parametrize("evaluation", ["fixed", "expanding", "rolling"])
def test_future_features_and_targets_cannot_change_earlier_predictions(evaluation):
    original = rows()
    altered = [dict(r) for r in original]
    # Far-future row changes must not affect forecast origins before it.
    altered[80]["rv_1"] *= 10
    altered[80]["rv_5"] *= 10
    altered[80]["rv_22"] *= 10
    altered[80]["target_rv"] *= 10
    def run(data):
        if evaluation == "fixed":
            return evaluate_fixed(data, train=50, validation=20)
        return evaluate_walk_forward(data, train=50, validation=20, window=evaluation,
                                     rolling_size=30 if evaluation == "rolling" else None)
    before, after = run(original), run(altered)
    for split in ("validation", "test"):
        for a, b in zip(before[split], after[split]):
            if a.target_date < original[80]["target_date"]:
                assert a == b


def test_regime_change_enters_only_after_label_availability():
    original = sessions()
    changed = [replace(s, rv=s.rv + 5.0) if i >= 85 else s for i, s in enumerate(original)]
    old_rows = synthetic_har_rows(original, certification_version=VERSION)
    new_rows = synthetic_har_rows(changed, certification_version=VERSION)
    old = evaluate_walk_forward(old_rows, train=50, validation=20)
    new = evaluate_walk_forward(new_rows, train=50, validation=20)
    old_forecasts = old["validation"] + old["test"]
    new_forecasts = new["validation"] + new["test"]
    for index, (a, b) in enumerate(zip(old_forecasts, new_forecasts), start=50):
        if index < 85 - 22:
            assert a == b
    assert any(a.har != b.har for a, b in zip(old_forecasts, new_forecasts))
