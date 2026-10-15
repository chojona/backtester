# NQ research preflight audit

Date: 2026-10-14 (America/New_York). Scope: retained local NQ history, offline core and optional Databento adapter. **Decision: NO-GO for HAR research using strict certified data.** This audit did not fit a model, request paid data, alter retained market data, or change certification rules.

## Status by subsystem

| Subsystem | Status | Evidence and limit |
|---|---|---|
| Architecture and offline tests | PASS | Reviewed provider, data validation, calendars, rolls, features, volatility, execution, risk, reporting, certification and tests. Original suite: 261 passed, one live test deselected. Final suite with additional local audit checks: 297 passed, one deselected. A passing suite is only evidence for its stated cases. |
| Raw history provenance and overlap | PASS | Independent retained-data verifier checked 67 raw chunk hashes, 7,301,216 raw bars, 516,400 exact overlap duplicates, zero conflicting duplicates, 6,784,816 consolidated rows and 66 roll boundaries. This verifies retained bytes and internal reconciliation, not exchange completeness. |
| Tiered historical certification | PASS | Rebuilt Phase 3 outputs with explicit exclusions: A=11, B=1,336, C=2,858, D=2 across 4,207 observed dates; 15,180 strict bars. Independent verifier passed the 4,207-date register and output hashes. Tier B is provisional exploratory data only; C/D are excluded. |
| Historical exchange calendar and missing data | BLOCKED | Individual holiday and early-close exceptions are incomplete. There are 56 unobserved weekday candidates, including five possible 2014 provider gaps. OHLCV silence cannot independently distinguish no trade, closure and provider loss. Pre-2012 trade-date mapping remains unresolved. |
| Core return, RV, semivariance, BPV and bar mathematics | PASS | Hand calculations, 500 seeded property cases and synthetic streaming checks passed. A retained Tier A session independently matched streaming RV, 5m/15m RV, signed semivariances and segment-aware BPV within floating-point error. |
| Historical estimator consistency | FAIL | `scripts/accept_nq_history.py` computes BPV across Overnight/RTH/Post-RTH boundaries, while `backtester/volatility.py` and `docs/VOLATILITY.md` explicitly exclude those pairs. The historical BPV table is therefore not interchangeable with streaming BPV. No historical outputs were rewritten. |
| VWAP, ATR and supported chart aggregation | PASS | Hand VWAP and ATR cases passed. Complete 5m OHLCV preserves open/high/low/close/summed volume; a missing minute censors the block. Tests also cover 1m/15m display bars and 60m/240m/1D session bars. Actual trade-level VWAP and execution-quality bars remain unverified from OHLCV. |
| Modeled futures execution and risk | PASS | NQ two-contract round trip independently reconciled tick slippage, multiplier, fees, gross and net P&L. Existing tests cover all six instrument tick values, gap stops, partial fills, OCO ambiguity, roll reopen, margin and entry limits. Costs and margin defaults are illustrative. |
| Real fill fidelity | BLOCKED | OHLCV cannot establish queue position or intrabar path; no independent broker or order-book reconciliation was available. |
| Adversarial integrity and leakage | PASS for checked cases | Missing intervals, duplicate and descending records, off-grid timestamps, bad prices, DST, session boundaries, UNKNOWN coverage, degraded metadata, as-of time, causal rolls and prefix-only strategy contexts have explicit rejection/censoring tests. Unknown future external data available to arbitrary Python strategies is outside the trusted research API. |
| Reproducibility and reporting | PASS for offline deterministic outputs | Two fixed-input `feature-audit` runs had byte-identical summary, features, events, orders, fills, rolls and integrity outputs. Metadata records input/code/timezone hashes and config; run IDs and creation times intentionally differ. This smoke run generated no trades. |
| HAR prerequisites | BLOCKED | Strict Tier A has two continuity segments of length 10 and 1; neither supplies a 22-session lag window or the prior recommendation of 778 accepted observations. Synthetic checks exercise ordering, 1/5/22 lag arithmetic, next-session target availability, missing-session rejection and no target leakage. No HAR model was fit. |
| Databento live integration | BLOCKED | Adapter and offline mocks inspected; installed SDK is 0.87.0. `DATABENTO_API_KEY` was absent from the process environment, so metadata-only live checks could not run. No historical market-data request was made. |

## Historical acceptance reconciliation

The legacy certification rerun returned `ACCEPT=11`, `REJECT=2`, `UNRESOLVED=4,194`. The Phase 3 cross-tab is exact: 11 `ACCEPT→A`, two `REJECT→D`, 1,336 `UNRESOLVED→B`, and 2,858 `UNRESOLVED→C`. Thus Phase 3 promoted no legacy unresolved date to strict certification. Its B label means provisional exploration under regular-regime evidence, not an exchange-certified session.

The 11 A dates comprise 2026-09-14 through 2026-09-25 (ten trading dates) and 2026-10-06 (one separate date after a retained provider revision). The D dates are 2010-06-07 (no prior-session roll buffer) and Sunday 2018-08-05 (preopen artifact). The 34 provider-degraded or metadata-incomplete dates remain C. Other C reasons include 635 pre-2012 mapping cases, 489 guarded exception cases, 159 sparse/off-schedule cases and 1,527 incomplete causal contract-evidence cases. Full reason counts are in `results/databento-nq-full-history/phase3-v3.0.0/certification-report.json`.

The independent verifier checked strict allowlist isolation and 15,180 strict rows; exploratory output has 1,852,590 rows over A+B dates. The reported 183 exploratory continuity segments must not be compressed into one uninterrupted history. No authoritative expected-session count exists for the full span.

## Independent numerical comparisons

The synthetic example uses returns `(+0.01, -0.02, +0.03)`: RV=`0.0014`, positive semivariance=`0.0010`, negative semivariance=`0.0004`, BPV=`(π/2)×0.0008`. For `100→100e^0.01`, log return=`0.01`. Two bars with typical prices `(104+98+102)/3` at volume 2 and `(108+100+106)/3` at volume 3 yield VWAP=`((304/3)×2+(314/3)×3)/5`. ATR for ranges 3 and 5 with period 2 is 4. A complete synthetic five-minute sequence `O=100, H=105, L=100, C=105, V=15` aggregates exactly; deleting a constituent minute yields no 5m bar.

For strict 2026-09-14 (1,380 NQU26 minute bars, 2026-09-13 22:00 through 2026-09-14 20:59 UTC), independent calculations from retained raw prices gave:

| Measure | Independent arithmetic | Streaming result | Interpretation |
|---|---:|---:|---|
| RV 1m | 9.572864330318981e-05 | 9.572864330318740e-05 | Agrees within 2.5e-18 |
| RV 5m | 1.0489860535242281e-04 | 1.0489860535242011e-04 | Agrees within 2.8e-18 |
| RV 15m | 8.913036080801017e-05 | 8.913036080800337e-05 | Agrees within 7e-18 |
| RS+ | 5.4819084138899635e-05 | 5.481908413889850e-05 | Agrees within 1.2e-18 |
| RS− | 4.090955916429018e-05 | 4.090955916428890e-05 | Agrees within 1.3e-18 |
| Segment-aware BPV | 8.227665424526533e-05 | 8.227665424526290e-05 | Agrees within 2.5e-18 |
| Legacy all-adjacent BPV | 8.272469477170503e-05 | 8.227665424526290e-05 | Different convention; delta 4.480405264421263e-07 |

The BPV delta equals two cross-segment adjacent products (1.974542883192305e-07 at Overnight→RTH and 2.505862381204660e-07 at RTH→Post-RTH). The core implementation follows its documented convention. The retained `volatility-by-session.csv` was generated by the older all-adjacent formula and must carry an explicit estimator version before it is used with streaming values.
The reproducible comparison is `scripts/audit_strict_nq_numeric.py`; its machine-readable output is `results/nq-strict-numeric-comparison.json` and includes the strict Parquet SHA-256.

## Invariants tested and remaining gaps

The offline tests and this audit cover: aware UTC bar-open timestamps, positive durations, finite and possible OHLC values, nonnegative volume, per-contract duplication/order, grid/session validity, off-tick flags, explicit missing active intervals, contract identity, roll paired opens and prior-session volume, no return across gaps/rolls, null complete-session volatility after unknown coverage, as-of availability, no future denominator in profiles, order tick validation, stop gap pricing, partial exits, fees/slippage/point multipliers, and deterministic report artifacts.

They do not independently prove historical exchange-hour exceptions, minute-level provider completeness, true order-book fills, traded VWAP, realistic margin schedules, model-ready long continuity, or broker reconciliation. Feature ATR currently rolls observed traded bars; whether a gap should reset its warmup needs an explicit research convention before using ATR as a predictor. The CLI's `feature-audit` reproducibility run did not exercise trade output with real NQ history.

## Findings and required changes before HAR

1. **P1 — insufficient strict history:** only 11 Tier A sessions and a maximum continuous run of ten, versus a 22-session feature lag and a previously proposed 778-session study floor. Sources: `phase3-v3.0.0/certification-report.json`, `certification-by-session.csv`, `docs/acceptance/databento-2026-10-07.md`. Do not build lag rows by bridging excluded sessions.
2. **P1 — calendar/provider acceptance incomplete:** Tier B cannot be treated as Tier A; 2,858 C and two D dates remain excluded. Sources: `calendars/nq-history-v3.json`, `scripts/certify_nq_history_phase3.py`, `results/databento-nq-full-history/phase3-v3.0.0/certification-by-session.csv`. Obtain dated CME exception evidence and resolve provider/roll ambiguity before promotion.
3. **P1 — BPV definition mismatch:** `scripts/accept_nq_history.py:262` includes all adjacent pairs, while `backtester/volatility.py:277-281` and `docs/VOLATILITY.md:36-39` split at calendar segments. Version and harmonize derived history in a separate reviewed change; preserve the original table and raw bars for auditability.
4. **P2 — unverified live provider path:** `backtester/providers/databento.py:135-223` is mocked offline, but this environment had no exported key. Metadata-only availability/condition checks and a bounded real normalization review remain outstanding.
5. **P2 — modeled fills only:** `backtester/execution.py:133-222` and `backtester/intraday.py` model fills from OHLCV and explicitly cannot reconstruct queue priority or exact intrabar sequencing. Treat execution performance as simulated until matched against higher-fidelity data.

No certification threshold was relaxed and no original historical market file was modified. No confirmed core correctness defect was fixed: the initially suspected streaming BPV boundary behavior was verified against the explicit estimator definition. New audit regression and seeded property tests were added in `tests/test_research_preflight_audit.py`.

## Commands and reproduction

Run from the repository root with `.venv-py312/bin/python`:

```sh
.venv-py312/bin/python -m pytest -q
.venv-py312/bin/python -m pytest -q tests/test_research_preflight_audit.py
.venv-py312/bin/python -m scripts.certify_nq_history
.venv-py312/bin/python -m scripts.certify_nq_history_phase3
.venv-py312/bin/python -m scripts.verify_nq_history_4207
.venv-py312/bin/python -m scripts.validate_nq_math --output results/nq-math-validation.json
.venv-py312/bin/python -m scripts.audit_strict_nq_numeric
```

Observed results: original 261/261 offline passed and one live deselected; audit test file 9/9 passed; independent math harness 21/21 passed when invoked; final complete suite 297/297 passed and one live deselected. The certification commands reproduced the counts above; independent verification returned `PASS_WITH_EXPLICIT_EXCLUSIONS`. The Phase 3 report records SHA-256 of registry, source evidence, consolidated Parquet, prior acceptance report, decision CSVs and derived Parquets. Raw chunk file hashes and overlap reconciliation are checked by the independent verifier. Original licensed input is under ignored `data/raw/databento/NQ/full-history/`; generated reports are under ignored `results/`.

Two identical synthetic `feature-audit` CLI invocations used `data/synthetic_NQ_1m.csv` (SHA-256 `b96ed2552b639b3af20b24a1cb14851fd7959d698710fbfc75e06642438003cc`) and `config/research.example.json` (SHA-256 `299d0948d1bacc4eac323d231b5cd24bbf6b7de3076e7a756c695063604727ee`). Their `summary.json` SHA-256 was `a45a763a62694df6d056c5cfc966cff59e779d9c10091c7e48a027293441afc1`; `features.json` was `248c6cb4f660aa3b075f1478c72a2d11944b321284368791639bff1fd91e90b5`. Other compared deterministic files also matched byte for byte. Use a fresh output directory and compare these artifact types, not run metadata timestamps.

## Bounded live Databento test proposed, not executed

When credentials are available, first query only `GLBX.MDP3` dataset range and conditions for one previously accepted UTC date; record response time, condition revision and request parameters without exposing the key. Before any historical `get_range`, present an exact narrow request and whole-request cost/size estimate for explicit authorization. The proposed billable test is one known 2026-09-14 NQ outright `ohlcv-1m` plus point-in-time `definition` range, bounded to one session with the paired contracts needed for roll review. Cap the scope and compare raw file hashes, DBN completeness metadata, normalized counts, timestamps, prices and selected-contract RV to retained evidence. Do not extend the request or acquire paid history without separate authorization.

**GO condition:** build a materially longer contiguous Tier A register with reviewed exchange exceptions, unambiguous provider/roll evidence, a frozen estimator specification, versioned daily targets on matched 1m/5m/15m support, and enough uninterrupted observations for 22-session lags plus the declared training and out-of-sample design. Until then, HAR research is **NO-GO**.
