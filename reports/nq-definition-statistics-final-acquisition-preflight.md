# NQ definition/statistics final acquisition preflight

**Prepared:** 2026-10-14 (America/New_York); amended at 22:25 UTC. **State:** exact bounded requests and metadata quotes only. No paid download or analysis promotion occurred. The preserved source is [`results/nq-contract-evidence-acquisition-plan.json`](../results/nq-contract-evidence-acquisition-plan.json), `request_manifest.databento.definition_full` and `statistics_full`; the amended companion report is [`nq-definition-statistics-retrieval-preflight.md`](nq-definition-statistics-retrieval-preflight.md).

## Publication boundary and chosen cutoff

The last required predecessor is the **Friday, November 18, 2022 CME trade date** for the Monday, November 21 target. Databento's [GLBX.MDP3 venue notes](https://databento.com/docs/knowledge-base/datasets) say CME cleared volume and open interest normally publish on the next UTC date, **except Friday sessions, which normally publish on the following Sunday**. Thus the expected first feed publication for November 18 belongs to **Sunday, November 20 UTC**. The original statistics end of `2022-11-20T00:00:00Z` excluded all of that Sunday. CME's [Daily Bulletin schedule](https://www.cmegroup.com/market-data/daily-bulletin.html) instead describes preliminary bulletin updates around **midnight CT on the following business day** and final updates around **10 a.m. CT**; for that Friday, Monday November 21 corresponds approximately to **06:00 UTC** and **16:00 UTC**. The bulletin timing describes a separate report, not the actual timestamp of the MDP 3.0 statistic. Databento also says CME often sends multiple statistics for one `ts_ref`, with initial and final values. A publication schedule is an expectation to test against the retrieved `ts_event` and `ts_recv`, not evidence that any particular NQ record was sent.

The amended **end-exclusive** statistics bound is **`2022-11-23T00:00:00Z`**. It includes all of Sunday November 20, the Monday November 21 bulletin cycle, and messages indexed through Tuesday November 22 UTC for a bounded nearby-correction check. It is a diagnostic tail, **not a guarantee that revisions ceased**: any correction received at or after November 23 remains outside scope and must be separately identified or the final value labeled only “latest observed within this window.” The first-publication test uses the earliest matching `CLEARED_VOLUME` message; revision chronology retains every later matching message through this cutoff. Databento's [timestamp convention](https://databento.com/docs/standards-and-conventions/common-fields-enums-types) says historical time-series filtering uses `ts_recv` as index timestamp when present, so `ts_ref=2022-11-18` alone does not include a later-received message.

## Exact two-request acquisition scope

`start` is inclusive, `end` exclusive, timestamps are UTC, and **`limit` is omitted** so there is no record limit. The definition request is byte-for-byte identical in parameters to the preserved manifest. The statistics request changes **only** its end.

```json
{
  "dataset": "GLBX.MDP3",
  "symbols": ["NQM2", "NQU2", "NQZ2", "NQH3", "NQM3", "NQU3", "NQZ3", "NQZ4", "NQZ5", "NQZ6", "NQZ7"],
  "stype_in": "raw_symbol",
  "schema": "definition",
  "start": "2022-05-23T00:00:00Z",
  "end": "2022-11-22T00:00:00Z"
}
```

```json
{
  "dataset": "GLBX.MDP3",
  "symbols": ["NQM2", "NQU2", "NQZ2", "NQH3", "NQM3", "NQU3", "NQZ3", "NQZ4", "NQZ5", "NQZ6", "NQZ7"],
  "stype_in": "raw_symbol",
  "schema": "statistics",
  "start": "2022-05-29T00:00:00Z",
  "end": "2022-11-23T00:00:00Z"
}
```

The **superseded original statistics request** is preserved here and in the unchanged manifest:

```json
{
  "dataset": "GLBX.MDP3",
  "symbols": ["NQM2", "NQU2", "NQZ2", "NQH3", "NQM3", "NQU3", "NQZ3", "NQZ4", "NQZ5", "NQZ6", "NQZ7"],
  "stype_in": "raw_symbol",
  "schema": "statistics",
  "start": "2022-05-29T00:00:00Z",
  "end": "2022-11-20T00:00:00Z"
}
```

Its earlier authenticated estimate was **$0.027844086289**, **29,897,360 bytes**, and **373,717 records**. The two statistics versions differ only in that end-exclusive timestamp.

No `ALL_SYMBOLS`, parent, continuous, format conversion, or third schema is implicit in these requests. A changed end or symbol list requires a new quote and new review of the cap.

## Fresh authenticated metadata quote

Using Databento Historical SDK **0.87.0**, authenticated `metadata.get_cost`, `metadata.get_billable_size`, and `metadata.get_record_count` were called for each exact amended request between **2026-10-14 22:25:39 and 22:25:54 UTC**. No `timeseries.get_range` or batch submission was called.

| Request | Estimated USD | Billable bytes | Records |
| --- | ---: | ---: | ---: |
| Preserved `definition` | $0.001183066517 | 747,240 | 1,437 |
| Amended `statistics` | $0.028197541833 | 30,276,880 | 378,461 |
| **Combined** | **$0.029380608350** | **31,024,120** | **379,898** |

Against the original November 20 end, the extension adds an estimated **$0.000353455544**, **379,520 billable bytes**, and **4,744 records**. A separate free `metadata.get_dataset_condition(dataset="GLBX.MDP3", start_date="2022-11-18", end_date="2022-11-28")` call returned nine dated rows, all `available`, each last modified `2026-08-31`; its check included the November 20–22 amendment interval. The condition endpoint's dates are inclusive and its result is dataset/day level; it does not certify particular NQ messages, symbols, revisions, or feed completeness. These account-specific estimates are not settled charges. [Databento historical metadata reference](https://databento.com/docs/api-reference-historical).

## Hard acquisition gate: $0.10 total

For any later authorized acquisition, treat **$0.10 USD as the maximum permitted combined pre-download estimate across these two schemas**. Immediately before either paid call, assert exact request equality against the two JSON objects above and rerun all three authenticated metadata methods for both. Parse costs as finite, nonnegative decimal USD; add them without rounding. **Abort before either download if either quote fails, parameters differ, or the combined fresh estimate is greater than $0.10.** Do not split the requests, change `limit`, or download one schema after the other schema fails the gate. Save that fresh quote and its UTC timestamp with the acquisition evidence. The current combined quote is **below $0.10** and leaves **$0.070619391650** of estimate headroom.

This is a hard **pre-download authorization gate**, not a provider-enforced invoice ceiling. Databento says billing is based on actual bytes sent, so metadata estimates alone cannot guarantee final billed spend below $0.10. If an actual-charge ceiling is required, obtain a provider-enforced cap or separately approve the residual billing risk before any download. [Databento historical metadata reference](https://databento.com/docs/api-reference-historical).

## Raw evidence preservation and post-retrieval checks

If separately authorized later, write each response directly as its original `.dbn.zst` to a new immutable run directory. Preserve the exact ordered request parameters, omitted `limit` semantics, fresh quotes, SDK version, UTC call/receipt times, response DBN metadata (`dataset`, `schema`, actual bounds, encoding, `limit`, `partial`, `not_found`, symbol mappings), and SHA-256 of each original DBN before any decode or export. Preserve any reported actual cost and bytes, decoded record counts, derivative-file hashes, and a read-back check binding each file to its request. Retain original timestamp precision and fields, including definition `ts_event`/`ts_recv`, activation/expiration, and statistics `ts_event`, `ts_recv`, `ts_ref`, `ts_in_delta`, `sequence`, `channel_id`, `stat_type`, `quantity`, `update_action`, and `stat_flags`. Do not overwrite the original files with normalized output.

1. **Historical roster and identity.** Reconstruct the effective XCME NQ outright book at every decision origin and compare the expected nine-contract roster on all 120 target dates with dated definitions and exchange listing rules. Check activation, expiration, last-trade, revisions, missing definition intervals, and the early historical symbology mappings for `NQU3` and `NQZ7`. The earlier free resolver mapped `NQZ7` to instrument ID **23041** beginning September 4, 2022; **confirm from the retrieved definition** that this is an outright with December **2027** expiration, correct venue/product, and no spread legs. If identity or effective listing is ambiguous, mark affected rosters unresolved.
2. **Volume identity and zeros.** Inventory statistic types, then isolate `CLEARED_VOLUME` (`stat_type=6`) and its numeric `quantity` with the correct instrument and CME trade-date `ts_ref`. Reject invalid/sentinel quantities. Distinguish an explicit numeric zero from no matching record, missing feed, nonlisting, or `not_found`. Never replace a missing statistic with zero, even if an illustrative Databento example fills missing values for a different purpose. [Statistics schema](https://databento.com/docs/schemas-and-data-formats/statistics).
3. **Origin and revisions.** For each `(instrument_id, stat_type, ts_ref)`, sort the full received stream by `ts_recv` with venue sequence tie checks. Record first publication, every subsequent quantity/action change, latest in-window value, and last value actually received by the 5 p.m. ET predecessor-close origin. Friday November 18's close was **22:00 UTC**. A Sunday or Monday volume is retrospective at that origin. Separate venue `ts_event`, Databento `ts_recv`, and CME Daily Bulletin schedule; a later final value must never be backdated as origin-available.
4. **Coverage and metric reconciliation.** Check all **1,080** expected contract/predecessor cells, including corrected combined holiday sessions, against definition continuity, response `partial`/`not_found`, dataset conditions, sequence/channel evidence, and independent source coverage. Compare cleared volume with Globex electronic OHLCV only after matching contract and CME trade date; investigate blocks, clearing-only activity, corrections, and incomplete electronic bars. The original audit had **752 unknown predecessor-volume cells**, not 752 zeros. A date's winner remains unresolved until the full eligible roster and all consequential competing volumes or certified upper bounds are supported. Preserve the existing `max(volume, contract code)` tie rule. [Causal universe audit](nq-causal-contract-universe-audit.md).

Successful download, a low quote, and `available` dataset condition establish none of record-level completeness, explicit zero volume, 2022 as-of availability, or causal contract winners. No paid retrieval, production change, certification promotion, or HAR fitting was performed for this preflight.
