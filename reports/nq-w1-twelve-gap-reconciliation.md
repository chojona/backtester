# NQ W1: reconciliation of twelve front-three provider gaps

**Decision, 2026-10-15: NO-GO for a complete 120-date front-three series or HAR fit.** Two temporary-status gaps can be upgraded to bounded provider-observed zeros. Ten cells remain unknown: eight have clean zero-trade responses but positive later cleared statistics, and two combine that discrepancy with brief nontrading status events. No independent electronic-volume upper bound proves the winner on any of those ten dates. This is a retrospective provider-stream assessment, not an exchange-wide or decision-time certification.

The machine-readable [reconciliation](../results/nq-w1-twelve-gap-reconciliation.json) contains exact segments, request metadata and DBN hashes, raw status timelines, later cleared messages, definition identity, per-cell classification, missing evidence, and counterfactual thresholds. Reproduce it with `.venv/bin/python scripts/reconcile_nq_w1_twelve_gaps.py`. The script makes no provider calls and leaves the immutable acquisition run untouched.

## Chain of custody and metric checks

The original [acquisition manifest](../data/raw/databento/NQ/w1-electronic-volume-20261015T113810546399Z/acquisition-manifest.json) is complete. Its SHA-256 agrees with the prior [replay](../results/nq-w1-front-three-acquisition-replay.json) and the manifest checksum file. All **154** files in the run seal match recorded sizes and SHA-256 hashes, including **74 original DBNs**, **74 JSONL exports**, request/quote records, and the manifest. The approved 80 request IDs were independently recalculated from `(schema, raw symbol, exact UTC start, exact UTC end)`. The 74 executed requests and six skipped conditional requests partition those 80 identities exactly. Frozen plan, inventory, and candidate hashes match the manifest.

For every executed response, the saved DBN metadata and manifest agree on schema, symbol, UTC bounds, and no limit; `partial=[]` and `not_found=[]`. Each raw-symbol mapping identifies the expected instrument ID. The record count is equal in the DBN, JSONL, and manifest, and every decoded event lies inside its requested interval. All twelve gap cells have **zero trade records and zero summed trade quantity** over their exact active segments. The two cells that received a new `ohlcv-1m` request (September 19 and 23) have **zero returned bars**. The other ten received bounded `trades` and `status` requests but no new OHLCV request; their earlier retained-bar counts are zero. A missing OHLCV request is not represented as a returned zero-bar response.

The earlier definition and statistics DBN hashes match their preserved analysis. The relevant definition messages were reread from the raw DBN: `NQH3` is instrument 20631 (`NQH23`), active 2021-12-17 14:30 UTC through 2023-03-17 13:30 UTC; `NQM3` is instrument 3522 (`NQM23`), active 2022-03-18 13:30 UTC through 2023-06-16 13:30 UTC. Both are XCME NQ outright futures with no legs, and their definitions were received before each decision origin. Each is inside its activation/expiration interval at the relevant origin. This validates the observed identity and eligibility, but does not establish an independently complete as-of venue roster.

Every later cleared-volume `ts_ref` was rechecked against the **corrected predecessor CME trade date**, including the July 5 target's July 1 predecessor and the July 6 target's split July 5 session. The relevant cleared messages were reread from the raw statistics DBN; quantity, `ts_ref`, and receipt time agree with the lossless stream. All first cleared receipts follow their decision origins. The records are venue-published **contracts cleared for the prior trading date**, whereas `trades` and `ohlcv-1m` represent electronic trade events and derived bars. They cannot be substituted for one another. Databento documents these definitions in its [statistics](https://databento.com/docs/schemas-and-data-formats/statistics), [trades](https://databento.com/docs/schemas-and-data-formats/trades), and [OHLCV](https://databento.com/docs/schemas-and-data-formats/ohlcv) schema references.

The clean, mapped, unpartial trade responses are evidence of zero *returned provider-stream trades* for the bounded intervals. The positive cleared values remain a discrepancy, not a numeric electronic volume or a cap on it. No retained electronic bar conflicts with these responses, but no independent venue sequence audit or alternate electronic capture resolves whether the absence is complete. The empirical fact that cleared volume exceeded or equaled retained electronic bars in other matched cells is not an upper-bound theorem for these cells.

## Per-cell evidence and winner sensitivity

All volumes below are contracts. `Cleared` is a later diagnostic only. `Leader` and `runner-up` are the two **known** front-three predecessor electronic totals. `Threshold` is the minimum *counterfactual* missing-contract electronic volume that would change the known leader. Every unknown code is lexicographically smaller than its known leader; at exact equality the known leader wins under the frozen `max(volume, contract code)` rule. These thresholds say nothing about actual missing volume.

| Target | Corrected predecessor | Missing contract | Cleared | Known leader | Runner-up | Margin | Change threshold | Evidence classification |
| --- | --- | --- | ---: | --- | --- | ---: | ---: | --- |
| 2022-07-05 | 2022-07-01 | `NQH23` | 15 | `NQU22` 601,348 | `NQZ22` 333 | 601,015 | 601,349 | Cleared discrepancy; unknown |
| 2022-07-06 | 2022-07-05 | `NQH23` | 6 | `NQU22` 783,859 | `NQZ22` 450 | 783,409 | 783,860 | Cleared discrepancy; unknown |
| 2022-07-07 | 2022-07-06 | `NQH23` | 22 | `NQU22` 641,910 | `NQZ22` 310 | 641,600 | 641,911 | Cleared discrepancy; unknown |
| 2022-07-08 | 2022-07-07 | `NQH23` | 5 | `NQU22` 539,083 | `NQZ22` 353 | 538,730 | 539,084 | Cleared discrepancy; unknown |
| 2022-07-11 | 2022-07-08 | `NQH23` | 30 | `NQU22` 630,490 | `NQZ22` 466 | 630,024 | 630,491 | Cleared discrepancy; unknown |
| 2022-07-14 | 2022-07-13 | `NQH23` | 1 | `NQU22` 728,825 | `NQZ22` 376 | 728,449 | 728,826 | Transient status plus cleared discrepancy; unknown |
| 2022-09-19 | 2022-09-16 | `NQM23` | 1 | `NQZ22` 740,189 | `NQH23` 350 | 739,839 | 740,190 | Cleared discrepancy; unknown |
| 2022-09-23 | 2022-09-22 | `NQM23` | 14 | `NQZ22` 780,902 | `NQH23` 534 | 780,368 | 780,903 | Cleared discrepancy; unknown |
| 2022-10-13 | 2022-10-12 | `NQM23` | 0 | `NQZ22` 722,611 | `NQH23` 431 | 722,180 | 722,612 | Bounded provider-observed zero |
| 2022-10-25 | 2022-10-24 | `NQM23` | 0 | `NQZ22` 706,408 | `NQH23` 483 | 705,925 | 706,409 | Bounded provider-observed zero |
| 2022-10-28 | 2022-10-27 | `NQM23` | 153 | `NQZ22` 761,967 | `NQH23` 715 | 761,252 | 761,968 | Transient status plus cleared discrepancy; unknown |
| 2022-11-09 | 2022-11-08 | `NQM23` | 6 | `NQZ22` 717,993 | `NQH23` 852 | 717,141 | 717,994 | Cleared discrepancy; unknown |

The exact requested active UTC segments are preserved per cell in the JSON. They are inherited from the frozen plan and checked against the replay; the July 6 predecessor has **two** segments, while the other eleven have one. All twelve raw symbol mappings and zero-trade quantities were independently checked against those intervals. The known volumes were taken from the earlier retained electronic panel and compared with the replay's ranked known subset; they are not cleared values.

## Four status timelines

The machine result gives every observed status record in provider order, with `ts_event`, `ts_recv`, action, reason, and `is_trading`. The concise timeline below collapses duplicate `Y` messages at the same event time. Each `N` is action **1 (pre-open)**, reason **3 (market event)**, followed by actions **6/7** with `Y`; no record shows a full-session inactive state. The bounded status feed begins in `Y` and ends in `Y` for all four. Databento describes `is_trading` as a **best-efforts** state and notes that status snapshots can carry across UTC days; these records alone cannot prove venue-wide status completeness ([status schema](https://databento.com/docs/schemas-and-data-formats/status)).

| Target | Observed `N → Y` event-time intervals (UTC) | Separate trade/bar check | Conclusion |
| --- | --- | --- | --- |
| 2022-07-14 | Jul 13 12:30:01.173 → 12:30:06.172; 12:30:06.564 → 12:30:11.564; 12:30:12.827 → 12:30:17.827 | 0 returned trades; 0 retained bars; new OHLCV not requested | Temporary states, but later cleared 1 leaves electronic total unresolved. |
| 2022-10-13 | Oct 12 12:30:00.036 → 12:30:05.035 | 0 returned trades; 0 retained bars; new OHLCV not requested | Temporary state; bounded provider-stream zero supported by trade response. |
| 2022-10-25 | Oct 23 22:00:01.294 → 22:00:11.294 | 0 returned trades; 0 retained bars; new OHLCV not requested | Temporary state; bounded provider-stream zero supported by trade response. |
| 2022-10-28 | Oct 27 20:30:03.117 → 20:30:08.117; 20:30:09.189 → 20:30:14.189 | 0 returned trades; 0 retained bars; new OHLCV not requested | Temporary states, but later cleared 153 leaves electronic total unresolved. |

The two October zero classifications rely on the same bounded authenticated provider-stream assumption used for the prior 17 provider-observed zeros: exact, unpartial, mapped trade coverage for the full active interval. They do **not** infer zero from an `N` message or from zero cleared volume. The temporary interruptions explain why the replay's stricter `all(Y/~)` test left these two as gaps. Point-in-time receipt and independent venue completeness remain unverified.

## Updated feasibility and next step

The retrospective provider-stream front-three count moves from **108/120 to 110/120**; **10/120** remain indeterminate. Both newly assessable leaders match the legacy selector. **Zero dates** meet strict causal/exchange-wide certification. Replaying the fixed 23-date HAR windows leaves **73/98** potential rows with an unresolved selector date and **zero** rows supported when separate retained selected-bar gaps are also required to be absent. No dates or rows were dropped or bridged.

**GO for a read-only targeted reconciliation of the ten remaining cells using existing independent venue electronic-feed sequence/completeness evidence and record-level clearing-to-trade provenance, if available. NO-GO for new paid retrieval, winner promotion on a large margin alone, a complete 120-date release, certification promotion, or HAR fitting.** If independent evidence is unavailable, keep these ten electronic totals and winners unknown. The needed evidence is an exact-session electronic total or a separately justified electronic upper bound below the known leader, plus a documented explanation of why the later cleared statistic differs. Status records and tiny cleared quantities alone cannot establish that bound.
