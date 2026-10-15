# NQ synthetic HAR-RV foundation

Date: 2026-10-14 (America/New_York). Scope is NQ realized-variance forecasting mathematics on **synthetic sessions only**. Historical fitting, trading signals, and other instruments are outside this implementation. Historical HAR decision: **NO-GO**; see [2022 evidence pilot and follow-up](nq-2022-evidence-pilot.md).

## Implemented contract

[`backtester/nq_har.py`](../backtester/nq_har.py) accepts complete, ordered synthetic `DailyVariation` observations through the existing NQ feature builder. At feature session *t*, the three regressors are `RV_t`, the mean of `RV_(t−4)..RV_t`, and the mean of `RV_(t−21)..RV_t`; the label is `RV_(t+1)`. A missing session ordinal, segment change, incomplete/non-A synthetic fixture, negative or nonfinite RV, or noncausal availability time is rejected. Synthetic Tier A labels exercise the strict input validator; they make no claim about historical certification. The module contains no historical loader.

OLS uses NumPy SVD least squares on centered and scaled regressors with an intercept; it rejects constant, rank-deficient, or ill-conditioned designs. The separate reference in [`tests/test_nq_har.py`](../tests/test_nq_har.py) uses modified Gram-Schmidt QR and back substitution. On a 55-row deterministic synthetic fixture, a second independent SciPy `lstsq(..., lapack_driver="gelsy")` run returned coefficients `[0.25184601630423364, 1.364472112338067, -0.6202489435806863, 0.13666276092445573]` for intercept, 1-, 5-, and 22-session terms. The production coefficients differed by at most `3.89e-15` in absolute value. This is numerical agreement on a fixture, not a claim of predictive validity.

Chronological splits preserve train, validation, and test order. Fixed evaluation fits once on train. Expanding and rolling walk-forward evaluation refit before each validation/test forecast, using only labels whose `target_available_at <= as_of`. Validation labels may enter later walk-forward fits only after availability; test labels similarly enter subsequent fits. Persistence forecasts `RV_t`; historical mean forecasts the mean of then-available training labels. For each method, `MAE`, `RMSE`, and out-of-sample `R² = 1 − SSE_method / SSE_sequential_historical_mean` are reported. A zero denominator is rejected. Raw OLS predictions are not clipped.

## Synthetic smoke results

Fixture: 120 deterministic positive synthetic daily RV observations, 98 target rows after 22-session warm-up; 50 training, 20 validation, 28 test; rolling window size 30. Values are realized-variance units. These numbers verify that the framework computes the metrics; they are **not market performance estimates**.

| Evaluation / split | Forecast | MAE | RMSE | OOS R² |
|---|---|---:|---:|---:|
| Fixed / test | HAR | 0.03261 | 0.03553 | 0.98537 |
| Fixed / test | Persistence | 0.08361 | 0.09295 | 0.89987 |
| Fixed / test | Historical mean | 0.23344 | 0.29374 | 0.00000 |
| Expanding / test | HAR | 0.03749 | 0.04090 | 0.98003 |
| Expanding / test | Persistence | 0.08361 | 0.09295 | 0.89689 |
| Expanding / test | Historical mean | 0.22950 | 0.28946 | 0.00000 |
| Rolling 30 / test | HAR | 0.03644 | 0.03851 | 0.98400 |
| Rolling 30 / test | Persistence | 0.08361 | 0.09295 | 0.90683 |
| Rolling 30 / test | Historical mean | 0.24331 | 0.30450 | 0.00000 |

Tests cover 1/5/22 lag arithmetic, next-session target separation, independent OLS coefficients, chronology and all three splits, expanding/rolling counts, persistence/mean baselines and metric finiteness, missing-session and segment rejection, invalid/constant/ill-conditioned inputs, and a future-label mutation that leaves earlier forecasts unchanged. Command: `.venv/bin/python -m pytest -q` → **307 passed, 1 deselected**. The new module's six tests all passed. No historical NQ Parquet was loaded by the HAR tests or fitted by this module during the work.

## Historical release gate

No historical fit is authorized by this mathematical foundation. The strict dataset currently contains 11 Tier A sessions in segments of length 10 and 1, so it cannot form a 22-lag HAR row. A first proposed study requires at least 778 consecutive accepted NQ sessions, with a dated CME grid, independent minute-status evidence where expected bars are absent, complete causal roll predecessors, and versioned recertification under the existing gates. The 2022 pilot does not clear those requirements. **GO for synthetic mathematical validation; NO-GO for historical HAR fitting.**
