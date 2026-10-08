# Independent Databento acceptance — 2026-10-07

**PASS — retained ten-session NQ acquisition and its normalization/realized-measurement pipeline.**

This verdict covers acquisition `20261007T233046211545Z`, trading dates September 14–25, 2026, and the raw constituent, volume-roll configuration supplied with it. It does not certify other dates, DST transitions, holiday schedules, all exchange messages, or forecasting performance. No trading execution or forecasting model was changed. No network acquisition or billed request was made.

## Evidence and reproducibility

The detailed evidence and prefix JSON files linked below are local, Git-ignored
research artifacts because they contain licensed provider samples. They are not
included in a fresh checkout. Reproduction requires the retained licensed inputs
and the optional Databento SDK; the checker scripts regenerate these evidence files.

- [Independent offline checker](review_databento.py) imports no production backtester logic. It independently decodes retained DBN using the installed official Databento SDK, compares all JSON records, parses CSV using Decimal, constructs exchange-local schedules, independently selects the contract, and computes measurements with math.log and math.fsum.
- [Detailed evidence](databento-2026-10-07-evidence.json): 50/50 checks passed, file hashes, all 30 contract/date coverage summaries, 10 measurement vectors and discrepancies, roll evidence, and 60 raw boundary observations.
- [Prefix checker](check_databento_prefixes.py) exercises production selection/measurement against separate raw arithmetic. [Prefix evidence](databento-2026-10-07-prefixes.json): all six cutoffs passed raw arithmetic comparison, exact record equality with truncated inputs, and exact equality after changing future prices and traded volumes in memory. These checks operate after validated ingestion; they do not claim that edited CSV would pass provenance checks.

Run from the repository root:

```sh
.venv/bin/python docs/acceptance/review_databento.py
.venv/bin/python -m docs.acceptance.check_databento_prefixes
.venv/bin/python -m pytest
```

Inputs remain in `data/raw/databento/NQ/20261007T233046211545Z`, `data/normalized/databento/NQ/20261007T233046211545Z`, and `results/databento-acceptance/20261007T233046211545Z`. Original reports and raw files were preserved. Evidence records SHA256 of each input, including config/calendar/source note. CSV SHA256: `38fbf881cb9be2c5dc81d7fb44bb466c3f6d74486ac0cd06002cb3b2e2ce0141`; raw manifest SHA256: `49b3cdb3e4da400f228e1c0229a20dce8f4057689258aaaa506a259f18a4a9e8`.

## Raw prices and timestamps — PASS

All seven manifest file hashes match. All three decoded DBN streams equal their retained JSONL record-for-record: 438 definitions, 27,377 OHLCV records and 52,878 statistics. Metadata has no limit, partial symbols or not-found symbols. The normalized sidecar's source, manifest and CSV hashes agree.

All 21,406 normalized TRADED rows match retained raw open/high/low/close exactly after division by 1e9, volume exactly, instrument ID, symbol and integer-nanosecond interval-start timestamp. All 12,575 materialized NO_TRADE rows have zero volume, flat previous known price, unpublished provenance and no fabricated source timestamp; the corresponding raw records are absent. All normalized timestamps fall in eligible sessions. The 5,971 excluded parent records reconcile the raw count to the chosen panel.

Databento specifies interval-start ts_event based on trade-message ts_recv, prices in 1e-9 units, and no record for a minute without trades. Thus a 13:30 UTC bar is available to this measurement layer at 13:31 UTC, rather than at its start. This is historical bar availability convention, not a verified live dissemination latency. [Databento OHLCV specification](https://databento.com/docs/schemas-and-data-formats/ohlcv).

Example: September 13 22:00 UTC = Sunday 18:00 EDT, trading date September 14. NQU6 / ID 42004177 becomes NQU26; raw OHLC = 28997.75 / 29111 / 28990 / 29090.75, volume 1644. The initial within-bar log return is 0.003202013460836004.

## Session calendar — PASS within the sampled dates

All ten ordinary sessions run 18:00 prior day to 17:00 ET, 22:00 to 21:00 UTC, with 1,380 eligible minutes. RTH is the explicit cash-hours research convention 09:30–16:00 ET, 13:30–20:00 UTC: 930 overnight, 390 RTH and 60 post-RTH minutes. RTH here is not a claim that Globex stops at 16:00 ET. Boundary evidence includes the minute before and at both RTH boundaries and the final session minute, every date. Weekends and daily maintenance contain no normalized observations.

CME's electronic trading notice establishes 17:00–16:00 CT and 16:00–17:00 CT maintenance after removal of the old afternoon pause. SER-8788 addresses this in section **5**, correcting the old local source note's reference to section 3. [CME notice](https://www.cmegroup.com/notices/electronic-trading/2021/06/20210621.html), [SER-8788](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2021/06/SER-8788.pdf).

The 2026 CME holiday index places Labor Day in September 6–8; none of September 14–25 falls in a listed holiday window. No sampled active-contract session needs a scheduled early close. [CME calendar](https://www.cmegroup.com/trading-hours.html). DST runs March 8–November 1, 2026, so every sampled date uses EDT (UTC−4); independently constructed ZoneInfo bounds agree. [NIST DST rules](https://www.nist.gov/pml/time-and-frequency-division/popular-links/daylight-saving-time-dst).

**Unresolved scope:** no DST transition or holiday early-close date was acquired. Their live-data handling remains unaccepted. Unscheduled exchange halts are not independently certified because no status/trade-message audit or archived exchange incident record was supplied. The local calendar is an authored schedule, not an exchange-signed archive.

## Definitions and contract rolls — PASS for the observed transition

Raw initial definitions independently confirm all three IDs/symbols, futures class, XCME, USD, 0.25 tick and 20 dollars per index point. Metadata was available before the request start. Expirations are NQU26 September 18 13:30 UTC, NQZ26 December 18 14:30 UTC, NQH27 March 19, 2027 13:30 UTC. The differing UTC expiry hours are consistent with New York DST. Contract multiplier sentinel is unknown, not 20; point value comes from unit_of_measure_qty. No selected-panel raw record occurs at or after expiry.

The initial NQU26 selection is a supplied policy choice, not an independently established most-liquid contract at acquisition start: the prior September 11 session is absent. It remains valid and fully observed for September 14. Before a longer study, acquire a prior-session buffer and freeze an initial-selection rule.

September 14 completed volume was NQU26 **312,278**, NQZ26 **341,924**, NQH27 **51**. The next session therefore switches to NQZ26 at September 14 22:00 UTC (September 15 trading date). Both old/new opens were traded at that exact minute: **29200.00 / 29488.50**, spread **288.50**. The preceding active/next comparison has all 1,380 minutes in both contracts. Independent selection agrees with the sole retained roll.

Volatility consumes raw constituent prices and resets at each exchange session/contract. At the new contract's first minute it uses log(29467.25 / 29488.50), giving RV **5.196675043878859e-7**, rather than a cross-contract close return. BPV and jump are null for that one-return prefix. The forward additive research offset is −288.50, aligning the paired research opens at 29200; those adjusted prices are not used for the recalculated volatility. Closure/weekend price gaps also are excluded by the documented within-session target definition. Include a separate gap measure later if total holding-period risk is the target; do not silently mix it into these daily labels.

## Independent volatility arithmetic — PASS

For each session, the initial return is log(first close / first open), then consecutive raw close-to-close log returns. RV is sum r²; BPV is (pi/2) sum adjacent |r_i r_(i−1)| with pairs stopped at calendar-segment boundaries; jump is max(RV−BPV,0); signed semivariances partition r²; quarticity is (1380/3) sum r⁴. BPV is the documented uncorrected estimator, not a finite-sample-adjusted version or a significance test. Quarticity uses the observed window as a unit interval.

Every daily RV, BPV, jump, both semivariances, quarticity, segment RV and 5m/15m RV agrees with the retained report under rel_tol=1e-10, abs_tol=1e-16. Maximum absolute discrepancy across those values is **6.804e-18**. Each daily 5m/15m estimate uses 276/92 complete nonoverlapping segment-anchored blocks, covering all 1,380 minutes. RV equals the semivariance sum and the three segment totals; the jump identity agrees.

| Trading date | Contract | RV 1m | BPV | Jump | RS+ | RS− | Quarticity |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-09-14 | NQU26 | 9.57286433e-05 | 8.227665425e-05 | 1.345198906e-05 | 5.481908414e-05 | 4.090955916e-05 | 6.915553629e-08 |
| 2026-09-15 | NQZ26 | 6.235870722e-05 | 6.017064266e-05 | 2.188064553e-06 | 3.059518267e-05 | 3.176352455e-05 | 7.653074448e-09 |
| 2026-09-16 | NQZ26 | 0.0001062266875 | 0.000102442404 | 3.784283478e-06 | 5.51168639e-05 | 5.110982362e-05 | 4.47314148e-08 |
| 2026-09-17 | NQZ26 | 5.912350752e-05 | 5.481931529e-05 | 4.304192232e-06 | 3.321052516e-05 | 2.591298236e-05 | 9.279882931e-09 |
| 2026-09-18 | NQZ26 | 4.844318541e-05 | 4.399703119e-05 | 4.44615422e-06 | 2.43064431e-05 | 2.413674231e-05 | 9.366780824e-09 |
| 2026-09-21 | NQZ26 | 4.408893821e-05 | 4.109396824e-05 | 2.994969967e-06 | 2.859654194e-05 | 1.549239626e-05 | 4.593555608e-09 |
| 2026-09-22 | NQZ26 | 5.577579319e-05 | 5.283085797e-05 | 2.944935215e-06 | 3.112728972e-05 | 2.464850347e-05 | 9.787452931e-09 |
| 2026-09-23 | NQZ26 | 6.079327806e-05 | 5.752236826e-05 | 3.270909804e-06 | 2.74182954e-05 | 3.337498266e-05 | 1.455507212e-08 |
| 2026-09-24 | NQZ26 | 0.0001101878838 | 0.0001081839299 | 2.003953873e-06 | 6.037201774e-05 | 4.981586607e-05 | 4.575488095e-08 |
| 2026-09-25 | NQZ26 | 8.163625052e-05 | 7.689302468e-05 | 4.743225843e-06 | 3.937019836e-05 | 4.226605216e-05 | 1.899536374e-08 |

The six causal cutoffs cover the RTH boundary, post-RTH boundary, first rolled minute, subsequent RTH, and Sunday reopening. No future mutation changed any returned prefix field. Threshold BPV is null in this acquisition because no ex ante threshold was configured; it was not independently validated here.

## Coverage and source limitations

The selected active series has **13,800 / 13,800 actual raw traded minutes**, ten complete sessions, zero materialized bars and zero UNKNOWN minutes. Completeness of these daily target grids therefore does not depend on interpreting absent active bars as no trades.

The full three-contract panel has 33,981 normalized rows: 21,406 TRADED and 12,575 carried NO_TRADE. It has 69 NO_TRADE_UNPRICED absent slots, all the initial NQH27 minutes on September 14, ending at 19:08 EDT September 13; the first traded price arrives at 19:09 EDT. That third-contract session is **incomplete**, although the active session and roll comparison are complete. Its daily target must not be treated as complete. NQU26 on expiration day has only 930 eligible minutes through 09:29 EDT; absence from 09:30 is expiration, not a missing afternoon session. After expiry it has no eligible minutes.

Provider UTC-day condition is available for the range. For thin inactive contracts, absence of raw records is only inferred NO_TRADE; a daily condition does not independently prove minute-level feed health. No second licensed vendor, provider web export, underlying trades, or status messages were supplied. DBN-to-JSONL agreement validates retained representations, not the exchange truth or absence of provider corrections. A small matched-source/trade reconstruction audit remains useful before stronger data-quality claims, but is not required for this bounded internal-transformation PASS.

`request.json` says download_complete=false, whereas the final manifest and sidecar say true. This is the immutable pre-download request snapshot, followed by successful finalization, not evidence of an incomplete stream; hashes and DBN metadata were checked independently. Old DATABENTO/VOLATILITY prose saying no key or no acquisition existed is historical and superseded by this report. Existing READY_FOR_HUMAN_REVIEW reports were preserved rather than overwritten.

## Full offline test suite

Command: `.venv/bin/python -m pytest`.
Python 3.12.13 / pytest 8.4.2. Result: **240 passed, 1 deselected, 13.27 seconds**, exit status 0. All 241 tests were collected; pytest.ini excludes the opt-in live integration test. No offline test was skipped or failed. This was the complete configured offline suite, including Databento, sessions, rolls, volatility, execution/risk, CLI and legacy engine coverage. The independent arithmetic and prefix scripts additionally passed. An earlier run passed 235 offline tests in 3.97 seconds; concurrently added volatility-chart files/tests appeared during review, so the full suite was rerun against the updated workspace and passed all 240. Those concurrent changes were preserved and were not authored by this acceptance review.

## Minimum additional NQ history for a serious first HAR walk-forward study

My research-design minimum is **at least 778 accepted session observations**: 22 lag warm-up sessions, 504 initial training response days, and 252 sequential out-of-sample forecast days. This is a practical floor, not a theorem or a guarantee of statistical power. Each training row requires its target and point-in-time lag features. Freeze the one-day horizon and daily/weekly/monthly convention before implementation. [Corsi's original HAR paper](https://doi.org/10.1093/jjfinec/nbp001) motivates the horizon components; the 504/252 split is this review's recommendation.

Request a bounded-chunk historical span approximately **August 2023 through September 25, 2026**, extending its start backward if the reviewed calendar and coverage filters leave fewer than 778 usable observations. End at the retained complete September 25 session, not the current partial session. Existing ten accepted days can be reused, so at least **768 additional accepted session observations** are needed, plus acquisition buffers. Do not count missing targets as zero or compress over unknown gaps to manufacture contiguous lag history. If using only standard full-length sessions, handle short sessions explicitly and extend history accordingly.

Minimum schemas: raw unadjusted GLBX.MDP3 NQ outright ohlcv-1m plus definitions with snapshots available before each chunk; overlapping active/next contracts and one prior complete session at each acquisition start for causal liquidity selection. Preserve at least the nearest three for compatibility with the present panel, refreshing selections per chunk. Statistics are optional for a volume-only HAR experiment; acquire them only if settlement/OI validation is deliberately included, and retain retrospective OI semantics. Full parent retrieval may cost more than the retained panel; obtain a new whole-request estimate before any billed download.

Review dated calendars over the entire span, including all holidays, early closes and both DST changes; explicitly validate retained real early-close and DST-adjacent sessions before extending acceptance. The ten-day fixed initial contract choice and unverified exception-date handling must not be silently copied to the larger history. Use complete single-contract within-session daily targets, keep paired roll evidence, and predeclare a 5m primary RV target with 1m/15m sensitivity on matched support. An approximately 17-week dataset is suitable for plumbing experiments, but is insufficient for this proposed training/evaluation split. No historical purchase, HAR/GARCH/ML implementation, fit, or trading change is authorized or performed by this report.
