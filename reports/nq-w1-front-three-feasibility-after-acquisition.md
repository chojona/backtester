# NQ W1 front-three feasibility after bounded Databento acquisition

**2026-10-15 decision: NO-GO for a complete 120-date front-three series or HAR fit.** The approved acquisition succeeded, but 12 predecessor cells remain provider gaps and their target-date winners are indeterminate. No production selector, frozen inventory, certification tier, or HAR model was changed.

## Quote and acquisition gates

The [approved request manifest](../data/raw/databento/NQ/w1-electronic-volume-20261015T113810546399Z/approved-requests.json) was generated from the unchanged [frozen remediation plan](../results/nq-w1-targeted-remediation-plan.json). Its 80 unique request IDs derive from schema, raw symbol, and exact UTC start/end bounds. The scope audit matched 32 unresolved cells, 34 active segments, 56 initial requests, and 24 conditional requests. The [incremental quote ledger](../data/raw/databento/NQ/w1-electronic-volume-20261015T113810546399Z/quote-ledger.jsonl) contains 80 authenticated successes, with cost, billable bytes, record count, timestamp, and HTTP outcome per request. No prior estimate was substituted.

The unrounded decimal sum for all 80 quotes, including every conditional fallback, was **$0.000096157191**, below the **$0.01** gate. The 56 initial requests were downloaded. Nine clean empty OHLCV segments triggered 18 conditional trade/status requests; three nonempty OHLCV segments caused six conditional requests to be skipped. Thus the [acquisition manifest](../data/raw/databento/NQ/w1-electronic-volume-20261015T113810546399Z/acquisition-manifest.json) records **74 original DBNs** and their SHA-256 hashes. The executed-request quoted sum was **$0.000081732867**; the actual provider charge is not yet supplied. All 74 response metadata checks passed for request bounds, symbol, schema, `partial=[]`, and `not_found=[]`. Decoded records were checked against UTC bounds and raw-symbol instrument mappings; all raw DBN and JSONL hashes were rechecked against the manifest. The read-only run has a [154-file SHA-256 seal](../data/raw/databento/NQ/w1-electronic-volume-20261015T113810546399Z/run-seal.json).

## Cell evidence and selector replay

The [per-cell replay](../results/nq-w1-front-three-acquisition-replay.json) classifies **3 positive electronic-volume cells**, **17 provider-observed zeros**, and **12 provider gaps**. The positive cells have bounded OHLCV volumes of 1, 2, and 4 on September 21, September 22, and September 26. A provider-observed zero means an exact, unpartial, symbol-matched zero-trade response with active status over the approved segment, under the explicit assumption that this authenticated response covers Databento's provider stream. It is neither an exchange-wide zero certification nor proof that the observation was available at the decision origin. Empty OHLCV alone was never used as zero evidence.

Eight gaps have zero-trade provider responses but a positive later cleared-volume diagnostic (July 5–11, September 19 and 23, and November 9); the different metric and later availability require reconciliation. Four gaps have `is_trading=N` within the bounded status response (July 14, October 13, October 25, and October 28). These 12 cells retain unknown electronic volume and no defensible upper bound. The positive later cleared values were not substituted for electronic volume.

Under the frozen descending `(predecessor electronic volume, contract code)` tie rule, **108 of 120** dates now have retrospective provider-stream winners; **12** remain indeterminate. There are **zero established winner disagreements** with the legacy selector among the 108 assessable dates. Strict causally certified dates remain **zero**, given unresolved venue completeness and point-in-time publication evidence.

The original chronology remains 22 warmup sessions and 98 potential HAR targets split **50 train / 20 validation / 28 test**. **75 of 98** target rows have an unresolved selector date in their 23-date window. The separate retained selected-bar gaps affect 65 rows; **zero rows** satisfy both the selector and retained-grid conditions without dropping or bridging dates. The independent calendar, clock, and availability gates also remain unreleased.

## Decision

**Acquisition gate: GO and completed within approved scope. Feasibility gate: NO-GO.** Preserve this run as the immutable raw evidence set. Reconcile the 12 provider gaps and the separate chronology gates before any complete 120-date release or HAR fit.
