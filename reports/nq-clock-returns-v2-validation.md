# NQ clock returns v2 validation — 2026-10-14

## Result and scope

`nq-clock-returns-v2.0.0` reproduces the frozen return-reference rule in [`docs/VOLATILITY.md`](../docs/VOLATILITY.md). It computes a destination research-segment return from the preceding minute's close when price continuity is intact, even if the Overnight/RTH/Post-RTH label changes. The cross-label BPV pair is omitted; the destination return pairs with the next eligible return. RV5 starts a new five-minute block at each research-segment opening without resetting the return reference. A new active interval (session open, scheduled halt, or contract change) resets to its first observed bar open. An explicit UNKNOWN minute invalidates canonical full-window measures and makes the next observed bar restart at its own open.

The corrected 120-session values are **experimental, provider-observed clock arithmetic**. The five no-trade minutes are carried only after the ten preserved DBN/JSONL responses pass hash, request-bound, zero-trade, and trading-status checks. This does not establish exchange-wide completeness, promote a certification tier, create an accepted historical daily target, or fit HAR. The 98 HAR rows below are potential feature/target arithmetic under the candidate calendar; actually eligible certified/HAR-fit rows remain **zero**.

## Versioned implementation and outputs

- [`backtester/nq_clock_returns_v2.py`](../backtester/nq_clock_returns_v2.py) gives each minute an `active_id` for price continuity and a separate `research_segment` for BPV eligibility and RV5 blocks. Evidenced no-trade minutes have a zero return and carried price; unverified absence is rejected by the builder.
- [`scripts/validate_nq_clock_returns_v2.py`](../scripts/validate_nq_clock_returns_v2.py) rebuilds the selected 120-date grid from retained raw bars and the preserved W1 candidate. It verifies the original evidence before calculation and compares an independent direct raw-price reference on every date. It also checks the five frozen-reference values from the [boundary audit](nq-return-boundary-specification-audit.md).
- [`results/nq-clock-returns-v2.0.0/daily-series.json`](../results/nq-clock-returns-v2.0.0/daily-series.json) contains all 120 daily RV1, RV5, positive/negative semivariance, BPV, sample counts, and v2-minus-v1 deltas. The five investigated dates include all RV5 block returns.
- [`results/nq-clock-returns-v2.0.0/potential-har-rows.json`](../results/nq-clock-returns-v2.0.0/potential-har-rows.json) contains the 98 corrected potential rows, with 1-, 5-, and 22-session RV5 features, target RV5, date provenance, and 50/20/28 split labels. No model coefficients or predictions were produced.
- [`results/nq-clock-returns-v2.0.0/manifest.json`](../results/nq-clock-returns-v2.0.0/manifest.json) records source/output hashes, changed-row counts, the five independent reference values, and exactly which five no-trade minutes were used.

The prior [`results/nq-w1-five-gap-clock-validation.json`](../results/nq-w1-five-gap-clock-validation.json), production volatility code, raw Parquet, existing certification, and accepted historical tables retain their prior content. No paid retrieval occurred.

## Evidence and sample accounting

The validator reopened all **ten** saved DBNs and matched their SHA-256 hashes and JSONL exports to the investigation manifest. Each trade response has zero returned trades; each corresponding status response reports trading and quoting active over the checked interval. The candidate hash is `b3a702768c7444f4c6cd5e692e57b1fc0b0e47919ff9445991adb465f6a07c2e`; evidence-manifest hash is `ec6df2be79e33a63562e55566fef43b4c85b114a6942ece14d99f3150955d1e8`; source-Parquet hash is `16a626bf24c90a73a176e4a21138f58c40e3a5c35ae70a57643c3f1878f94c44`. The Phase 3 ledger hash is `8f539c28a437f5e13266f15ad048cb11f87ccd51d13cdcaa3dac59eb8c23d40c`.

The rebuilt grid has **169,020** clock minutes: **169,015** retained source bars plus exactly **five** evidenced no-trade samples. It produces **33,804** complete five-minute blocks. No UNKNOWN minute is silently converted to zero. Ordinary sessions retain 1,380 clock returns, 276 five-minute blocks, and 1,377 eligible BPV pairs (two research-cut pairs excluded). The five verified UTC minutes are June 5 23:27, July 27 03:56, August 16 04:43, August 18 04:42, and October 12 22:48 in 2022.

## Independent five-date reproduction

The independent reference loops over raw selected-contract closes and candidate active intervals without calling the v2 clock API or reading v1 return arrays. It restarts only at active interval opens, carries only the five verified no-trade prices, partitions BPV by research label, and sums complete segment-anchored five-minute returns. Its five values below agree with the v2 implementation within `2e−15` and with the truncated [audit values](nq-return-boundary-specification-audit.md) within `5e−13` absolute squared-log-return units.

| Trade date | RV1 | RV5 | RS+ | RS− | BPV |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-06-06 | 0.000283004126192 | 0.000245807530114 | 0.000147365747282 | 0.000135638378910 | 0.000284655372334 |
| 2022-07-27 | 0.000261577898609 | 0.000336715308672 | 0.000170349132546 | 0.000091228766063 | 0.000249036523493 |
| 2022-08-16 | 0.000107185211682 | 0.000111139850500 | 0.000051209207064 | 0.000055976004618 | 0.000105954201691 |
| 2022-08-18 | 0.000130934710263 | 0.000134137847952 | 0.000063726049361 | 0.000067208660902 | 0.000133528497791 |
| 2022-10-13 | 0.002197493363833 | 0.002007580383880 | 0.000596987248747 | 0.001600506115087 | 0.001185547615150 |

Every one of the 120 daily v2 measurements matched the independent raw-price calculation within `2e−15` for RV1, RV5, both semivariances, and BPV. RV1 equals positive plus negative semivariance within `1e−15` on each date. Compared with the prior experiment, **119** dates change RV1, **120** change RV5, **108** change RS+, **82** change RS−, and **118** change BPV at an absolute `1e−18` change threshold. These counts reflect boundary-bar price differences in the retained source, not changes to no-trade evidence or the selected contracts.

The corrected RV5 series changes the values in all **98** potential HAR rows: `RV_1`, `RV_5`, `RV_22`, and target RV each change in 98/98 rows at the same threshold. Target dates, 22-date feature windows, chronological ordering, and split labels match the preserved candidate plan. No HAR fit or forecasting evaluation was run.

## Hash comparison and verification

| Artifact | SHA-256 |
| --- | --- |
| Prior experimental JSON, unchanged | `f73169dd9cdf806cfc0f4d0edc854191e18adc9806b9577c3b3c6edc368586ef` |
| New daily series | `8d4659f02d8ef76ab058ac464eb127ff3a91a5a9973506567edb438d63c62276` |
| New potential HAR rows | `850873a253812815107885e41169acce404bbf60e0f492ca98aa141dfd8cc0e1` |
| New manifest | `e6bd464b10dd057a68a5153a018825ba169b1a6bf8c510564ac288644e43b48b` |

The prior JSON hash was checked before and after writing the new directory. A second complete v2 run produced the same three new-file hashes. The old and new files have different schemas; the numeric comparison is the per-date/per-field delta stored in the daily series and the changed-row counts above.

Regression fixtures in [`tests/test_nq_clock_returns_v2.py`](../tests/test_nq_clock_returns_v2.py) use unequal preceding close and boundary open at **both** research cuts. They independently check all requested RV1, RV5, signed-semivariance, and BPV formulas, including the first eligible pair after each cut; they also test halt/session/contract resets, evidence-backed zero return, UNKNOWN restart, and rejection of unverified or mismatched evidence. The focused clock/math/BPV suites passed **35 tests**. The repository suite passed **332 tests, 1 deselected**. The v2 builder was run twice and verified the raw evidence and output hashes both times.

Reproduce locally with the existing project environment:

```sh
.venv/bin/python -m scripts.validate_nq_clock_returns_v2
.venv/bin/python -m pytest -q tests/test_nq_clock_returns_v2.py
```

The repository ignores `results/*` by default; the versioned results remain available in this workspace at the paths above.
