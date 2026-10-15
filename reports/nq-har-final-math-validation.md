# NQ HAR-RV — final mathematical validation

Date: 2026-10-14 (America/New_York). Scope: synthetic data only. Reviewed `backtester/nq_har.py`, `tests/test_nq_har.py`, and the row construction contract in `backtester/nq_research.py`.

## Verdict

**Numerical correctness: validated on synthetic fixtures.** The lag arithmetic, forecast timing, OLS fit, fixed and walk-forward forecast calculations, window selection, and scoring agree with independent calculations. Raw OLS forecasts can be negative; the implementation does not clip them. Constant, rank-deficient, or ill-conditioned designs are rejected.

**Predictive validity for historical NQ: untested.** Synthetic scores say nothing about market forecasting performance. No historical NQ data were loaded, no market model was fitted, and no trading signal or certification rule was changed. The existing historical **NO-GO** remains in force.

## Availability audit

For every generated row with target session index `j >= 22`, the feature origin is session `j−1`. The regressors are `RV[j−1]`, the mean of `RV[j−5:j]`, and the mean of `RV[j−22:j]`; the label is `RV[j]`. `as_of` equals the availability timestamp of session `j−1`, while `target_available_at` equals that of session `j` and must be later. The test checks these identities for **all 98** rows of the 120-session fixture, not just the first row. The 22-session warm-up produces exactly 98 target rows.

The synthetic session input gate requires ordered, complete, consecutive Tier A fixture sessions in one research segment, with finite nonnegative RV and strictly increasing availability timestamps. The row validator requires increasing feature and target dates, `feature_date < target_date`, `as_of < target_available_at`, and the preceding target to be available by the next origin. Consequently, the row contract represents one fully observed target becoming available at or before the following origin. It does not support arbitrary delayed-label gaps; such rows are rejected before fitting.

With `train=50`, `validation=20`, and 28 test rows, fixed evaluation fits once on indices `0..49` and uses that fit and training historical mean at every later origin. Expanding evaluation uses eligible prior indices `0..i−1` at origin `i`. Rolling evaluation with size 30 uses exactly `i−30..i−1`. In each case, eligibility is checked using `target_available_at <= current as_of`; no current or future target enters a fit. The independent test recomputes eligible indices and complete forecasts with a separate QR solver for every validation and test origin. Changing future features or targets leaves all earlier predictions unchanged. A synthetic regime shift affects forecasts only from the first changed origin onward, and its label enters later refits only after availability.

## Common benchmark comparison

For fair cross-evaluation OOS R², `comparison_metrics` requires identical ordered target dates and actuals. It freezes the **fixed evaluation's sequential historical-mean forecast** as one benchmark sequence for all methods and evaluations. For errors `e_i = actual_i − forecast_i`, MAE is `mean(|e_i|)`, RMSE is `sqrt(mean(e_i²))`, and common OOS R² is `1 − sum(e_i²) / sum((actual_i − benchmark_i)²)`. The synthetic test denominator is finite and positive. All rows below use the same 28 test targets. Values are in synthetic RV units.

| Evaluation | Forecast | MAE | RMSE | Common OOS R² |
|---|---|---:|---:|---:|
| Fixed | HAR | 0.03261 | 0.03553 | 0.98537 |
| Fixed | Persistence | 0.08361 | 0.09295 | 0.89987 |
| Fixed | Historical mean | 0.23344 | 0.29374 | 0.00000 |
| Expanding | HAR | 0.03749 | 0.04090 | 0.98061 |
| Expanding | Persistence | 0.08361 | 0.09295 | 0.89987 |
| Expanding | Historical mean | 0.22950 | 0.28946 | 0.02893 |
| Rolling 30 | HAR | 0.03644 | 0.03851 | 0.98281 |
| Rolling 30 | Persistence | 0.08361 | 0.09295 | 0.89987 |
| Rolling 30 | Historical mean | 0.24331 | 0.30450 | −0.07460 |

The original evaluation-specific metrics are retained separately under `evaluation_specific`; their MAE and RMSE are the same as above, while each evaluation's own historical-mean sequence defines its R² denominator:

| Evaluation | HAR local OOS R² | Persistence local OOS R² | Historical mean local OOS R² |
|---|---:|---:|---:|
| Fixed | 0.98537 | 0.89987 | 0.00000 |
| Expanding | 0.98003 | 0.89689 | 0.00000 |
| Rolling 30 | 0.98400 | 0.90683 | 0.00000 |

The common and local R² values answer different questions. In particular, a local historical mean has R² zero by definition, while an expanding or rolling mean can score above or below zero against the common fixed benchmark. The test independently calculates every MAE, RMSE, and common R² and rejects mismatched targets or benchmark lengths.

## Numerical stress and limitations

Tests cover zero and `1e-12` RV, a `1e6` RV spike, a later synthetic regime change, an intentionally negative raw forecast, highly correlated 1/5/22 regressors, near-singular and exactly singular designs, a constant regressor, and future feature and target mutations. Moderately correlated regressors agree with the independent QR reference within numerical tolerance; unstable designs are rejected at the configured condition threshold. The independent reference checks **full walk-forward forecasts**, including persistence, historical mean, and training counts, rather than coefficients alone.

Condition screening protects this linear-algebra implementation from unstable designs; it does not establish that HAR is well specified or that RV forecasts will be calibrated on NQ. Negative raw predictions are mathematically possible, so any later application requiring nonnegative variance forecasts must make and validate an explicit policy. No such policy was added here.

Verification: `.venv/bin/python -m pytest -q tests/test_nq_har.py` → **17 passed**; `.venv/bin/python -m pytest -q` → **318 passed, 1 deselected**. `git diff --check` passed.
