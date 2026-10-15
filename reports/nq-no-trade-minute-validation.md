# NQ no-trade minute: clock-time RV research validation

Date: 2026-10-14 (America/New_York). **Research result: the single provider-observed minute can be represented as a clock-time price sample with a zero return under the stated evidence assumption.** This is an isolated experiment, not a certification or production-estimator change. The 2022-02-16 session remains Tier C and excluded from strict and A/B exploratory HAR samples. No paid Databento request was made for this validation.

## Evidence-only classification and provenance

The exact interval is **NQH2** (canonical `NQH22`, instrument 3541), `[2022-02-16 04:47:00, 04:48:00) UTC`, or 2022-02-15 23:47–23:48 EST. Its evidence-only classification is `PROVIDER_OBSERVED_NO_TRADE`. This means no trade appeared in the returned Databento stream; it does **not** assert exchange-wide completeness, change the historical session's Tier C classification, or authorize the same classification for any other empty minute. The underlying [completed investigation](nq-databento-gap-investigation.md) and its Git-ignored local [manifest](../data/raw/databento/NQ/gap-investigation-20261014T194238Z/manifest.json) remain the source of record.

| Retained request | Exact inclusive start / exclusive end UTC | Returned records | Response SHA-256 |
|---|---|---:|---|
| `GLBX.MDP3`, `trades`, `stype_in=raw_symbol`, `symbols=["NQH2"]` | 2022-02-16 04:47–04:48 | 0 | `b351972c9a66d514b97d6b944d90c783cdc770268078e18850a1b3d3059e805b` |
| `GLBX.MDP3`, `status`, same symbol selection | 2022-02-15 23:00–2022-02-16 04:48 | 3 | `d26aadc23c4ce02c5ed49574a1aa62f80fee2980581d6c3be0556e3de2c250c0` |

Both response hashes were rechecked locally against the saved `.dbn.zst` files. The trade JSONL export is empty, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; the status JSONL export SHA-256 is `c0e5d8dafe688dfae8bdcc717ec6873e765fd94faae4b900e47acbd4cc5139d0`. The status records report action 7, `is_trading=Y`, `is_quoting=Y` at session open and again in the UTC-midnight carried-state snapshot; no returned halt or pause precedes 04:48. The request metadata reports `partial=[]`, `not_found=[]`, and `limit=null` for both responses. The full-history `ohlcv-1m` acquisition's `ohlcv-1m.dbn.zst` SHA-256 is `75fda97820e0e822ca27e0ca53836ce504df6205bf4a37d92b05d8ccf9eb13c4`; its retained NQH2 bars have no 04:47 record. The earlier account-specific **estimate** was $0.000114440918 combined; the SDK did not report a settled charge or actual billable bytes.

The classification is intentionally narrower than “verified exchange no trade.” A common upstream loss could affect both Databento trades and its derived OHLCV. Status flags are best efforts, and the dataset's `available` condition is not minute-level completeness. The evidence therefore supports an experimental provider-stream treatment only.

## Experimental method

[`backtester/nq_clock_experiment.py`](../backtester/nq_clock_experiment.py) accepts an explicit expected-minute grid. Each minute must contain one published observed trade bar or one bounded `GapEvidence` record with a complete zero-trade response, active trading status, matching contract and minute, and preserved response hashes. The sampler refuses missing evidence, a gap at a segment start, skipped minutes within a segment, overlapping minutes, or a contract change without an explicit reset. A new session or maintenance segment starts from its own first observed bar open. The carry-forward point has only a timestamp, contract, segment, price, and source label; **it is not a trade or OHLCV bar**. The original bars remain unchanged.

For a segment's first minute, the reference is its first observed bar open. Subsequent 1-minute returns use consecutive minute-end sampled prices. Complete, nonoverlapping 5-minute clock blocks use the prior block's endpoint as the next reference. Both estimators sum squared raw log returns without annualization. Incomplete terminal blocks are rejected. This rule preserves the post-gap observed price move: the 04:47 return is zero, while the 04:48 return starts from the actual 04:46 close. It does not convert an unresolved missing interval into a zero return.

## Local arithmetic around the actual gap

The retained NQH2 source has nine published bars from 04:40 through 04:49 UTC, with only 04:47 absent. Their opens, closes, and volumes were read from `results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet`. The observed 04:46 bar closes at **14558.25**, volume **26**; the observed 04:48 bar closes at **14557.25**, volume **10**. The experimental 04:47 price sample is **14558.25**, so its log return is exactly zero and the 04:48 return is `log(14557.25/14558.25)`. Across the ten-minute window, published volume remains **107** over **nine** trade bars. The sampler emits **ten price samples**, including one carried point, and creates **zero** new bars, trades, or volume.

An independent reference loop in [`tests/test_nq_clock_experiment.py`](../tests/test_nq_clock_experiment.py) computes the squared log returns directly, without calling the experiment's RV calculation or the production estimator:

| Output | Clock-time support | Unannualized log-return RV | Status |
|---|---:|---:|---|
| **EXPERIMENTAL_EVIDENCED_CLOCK_RV**, 1-minute | 10 returns / 10 minutes | `8.405908356060673e-08` | Research measurement under provider-stream assumption |
| **EXPERIMENTAL_EVIDENCED_CLOCK_RV**, 5-minute | 2 returns / 10 minutes | `1.4449912269940095e-08` | Same support; first 5-minute block contributes zero |
| **EXISTING_GAP_REJECTING_ESTIMATOR**, 1-minute and 5-minute | 9 published bars / 10 expected minutes | `None` / `None` | `RealizedVolatility` reports incomplete prefix after the absent bar |

The two labels describe different admissibility rules, not a forecast performance comparison. The 1-minute and 5-minute numbers are also different sampling estimands; they are not expected to match. No full-session 2022-02-16 RV or HAR row is inferred from this ten-minute demonstration.

## Boundary and failure checks

The tests reject an unresolved minute, an evidence record reporting any trade, an inactive or incomplete status/response, mismatched contract evidence, and a no-trade minute without a previous observed price. They reject a contract change or time jump inside a segment. Explicit segment changes reset the price reference across a contract change, session boundary, or maintenance break; the tests verify that a large contract price difference does not enter RV. A terminal partial 5-minute block fails rather than changing support silently. The local targeted run passed **105 tests** across the experiment, NQ mathematical validation, HAR, and volatility suites (`.venv/bin/python -m pytest -q tests/test_nq_clock_experiment.py tests/test_nq_math_validation.py tests/test_nq_har.py tests/test_volatility.py`).

## HAR implications and gate

If independently evidenced no-trade minutes were ever admitted to an exploratory clock-time RV series, HAR's 1-, 5-, and 22-session features would have to use that same versioned RV definition and the same complete, matched minute support as their targets. A carried price adds a zero minute return but no trade activity; subsequent observed returns still matter. Evidence scope, source hashes, segment boundaries, contract selection, and publication/availability assumptions would need a frozen session manifest. Unknown gaps would break the session and the consecutive HAR window. This test supplies evidence for **one minute only**, not every sparse 2022 session or a historical sequence.

The [prespecified exploratory study design](nq-har-exploratory-study-design.md) requires **120 consecutive eligible A/B sessions** with complete matched-support RV. Its current longest A/B run is **44 sessions**; this Tier C date is outside that pool. The 120-session exploratory gate remains **NO-GO**, and strict historical HAR remains NO-GO. No production estimator, certification rule, A/B/C/D tier, historical ledger, or forecasting fit was changed.
