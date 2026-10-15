# NQ definition and statistics retrieval preflight

**Prepared:** 2026-10-14; amended at 22:25 UTC
**Disposition:** metadata-only diagnostic prepared; no time-series retrieval, tier change, production edit, or HAR fit.
**Preserved request source:** [`results/nq-contract-evidence-acquisition-plan.json`](../results/nq-contract-evidence-acquisition-plan.json), `request_manifest.databento.definition_full` and `statistics_full`. The 120 date-level roster and predecessor checks use its `date_coverage` array.

## Exact proposed requests

These are the amended acquisition requests, with inclusive `start`, exclusive `end`, no `limit` (all matching records), and no substitution of parent or continuous symbology. The `definition` request is unchanged. The `statistics` request changes only its end from the preserved manifest:

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

**Superseded statistics request version:** identical dataset, ordered symbols, `stype_in`, schema, start, and omitted `limit`, but `end="2022-11-20T00:00:00Z"`. Its earlier quote was $0.027844086289, 29,897,360 bytes, and 373,717 records. The preserved JSON manifest remains unchanged as historical evidence; the November 23 request above is the current proposed acquisition scope.

The manifest has 120 target CME trade dates, June 2–November 21, and completed predecessors, June 1–November 18. The optional May 31 boundary is also inside both windows. The old statistics end excluded Sunday November 20, when [Databento says Friday CME cleared-volume statistics normally publish](https://databento.com/docs/knowledge-base/datasets). The amended end includes Sunday November 20 and Monday/Tuesday November 21–22 UTC; CME's separate [Daily Bulletin schedule](https://www.cmegroup.com/market-data/daily-bulletin.html) places the following-business-day preliminary and final updates around Monday 06:00 and 16:00 UTC. This permits a bounded check of initial messages and nearby revisions, **not** proof of actual publication on schedule or absence of corrections received November 23 or later. Databento filters historical records by their index timestamp (`ts_recv` where present), so a `ts_ref` of November 18 does not pull a later-arriving message into this request. [Databento timestamp convention](https://databento.com/docs/standards-and-conventions/common-fields-enums-types).

## Fresh metadata evidence

Fresh authenticated Databento Historical SDK `0.87.0` calls began at **2026-10-14 22:25:39 UTC** and finished at **22:25:54 UTC**. For each exact request above, the calls were `metadata.get_cost`, `metadata.get_billable_size`, and `metadata.get_record_count`. No `timeseries.get_range` call was made.

| Schema | Estimated cost (USD) | Estimated billable bytes | Estimated records |
| --- | ---: | ---: | ---: |
| `definition` | $0.001183066517 | 747,240 | 1,437 |
| Amended `statistics` | $0.028197541833 | 30,276,880 | 378,461 |
| **Combined** | **$0.029380608350** | **31,024,120** | **379,898** |

The earlier authenticated `metadata.get_dataset_range(dataset="GLBX.MDP3")` check found per-schema `definition` and `statistics` ranges beginning `2010-06-06T00:00:00Z` and extending past the proposed 2022 bounds. The earlier `metadata.get_dataset_condition(dataset="GLBX.MDP3", start_date="2022-05-23", end_date="2022-11-22")` returned **158 UTC dates, all `available`**, with `last_modified_date` in 2026 for every returned date. This condition endpoint has an **inclusive** `end_date`, unlike the time-series request. `available` means no known dataset/day issue; it is not a guarantee of complete NQ symbols, statistics types, feed sequences, or 2022 point-in-time availability. A 2026 modification date does not identify which records changed. Counts and bytes are estimates; the quote is neither a cost cap nor a record-level coverage certificate. The fresh **combined estimate is below the $0.10 pre-download gate**, with $0.070619391650 estimate headroom; re-quote immediately before any later authorized download and abort before either schema if the total exceeds $0.10. Actual billing is based on bytes sent, so the gate alone is not a provider-enforced invoice ceiling. [Databento historical metadata reference](https://databento.com/docs/api-reference-historical).

### Historical raw-symbol resolution check

The free `symbology.resolve` metadata request used `dataset="GLBX.MDP3"`, the exact 11-symbol list, `stype_in="raw_symbol"`, `stype_out="instrument_id"`, `start_date="2022-05-23"`, `end_date="2022-11-21"`. It returned `not_found=[]` and the following historical mappings. The 2022 contract identities below follow the CME month code and the nine-contract listing cycle; **expiry, venue class, and exact effective intervals still require inspection of definition records**. The returned `d1` values are symbology resolution interval bounds, not evidence of contract expiration.

| Raw symbol | Intended outright | Instrument ID | Resolution starts | Note |
| --- | --- | ---: | --- | --- |
| `NQM2` | June 2022 | 2895 | May 23 | Resolved |
| `NQU2` | September 2022 | 10391 | May 23 | Resolved |
| `NQZ2` | December 2022 | 13613 | May 23 | Resolved |
| `NQH3` | March 2023 | 20631 | May 23 | Resolved |
| `NQM3` | June 2023 | 3522 | May 23 | Resolved |
| `NQU3` | September 2023 | 2130 | June 5 | Partial across entire query; early mapping needs roster reconciliation |
| `NQZ3` | December 2023 | 260937 | May 23 | Resolved |
| `NQZ4` | December 2024 | 106364 | May 23 | Resolved |
| `NQZ5` | December 2025 | 158704 | May 23 | Resolved |
| `NQZ6` | December 2026 | 261401 | May 23 | Resolved |
| `NQZ7` | December 2027 | 23041 | September 4 | Partial across entire query; early mapping and 2027 expiry need definition review |

The two `partial` symbols lack mappings at the beginning of the query. Their first resolved dates, **June 5** for `NQU3` and **September 4** for `NQZ7`, precede the expected post-expiry roster transitions. That discrepancy is a specific reason to inspect the dated definitions and exchange rule before asserting nine-contract venue eligibility on every target date; a symbology mapping is not by itself an active-listing certificate. In particular, the one-digit `NQZ7` must be confirmed as **December 2027**, not an earlier decade's symbol, by the definition's expiration and instrument fields. [CME 2022 listing notice](https://www.cmegroup.com/notices/ser/2022/04/SER-8975.pdf).

## Validation protocol for an eventual authorized retrieval

1. **Complete historical roster.** Decode every definition, retain raw bytes and response metadata, join by `instrument_id` and raw symbol, and require XCME NQ outright futures with no spread legs. Reconstruct the nine eligible target contracts on each of the 120 dates from the May 23 rule and dated additions/removals; compare against the effective definitions at the prior-close decision time. Investigate any missing definition, duplicate ID, temporary symbol reuse, or exception. The expected roster is five consecutive March-cycle quarters plus four additional December months, not the three-symbol legacy bar filter.
2. **Activation and expiration.** Record definition `ts_event`/`ts_recv`, activation, expiration, last-trade, security status, and all definition revisions per instrument. Compare venue-effective dates with the June and September transitions, especially `NQU3` and `NQZ7`. Do not use a later retrospective definition as proof that it was available at an earlier forecast origin.
3. **Statistic identity and trade date.** Inventory every `stat_type` and its value representation; `CLEARED_VOLUME` is type `6` and uses `quantity`. Select it only if that is the chosen ranking metric. Preserve `ts_ref` and establish its CME trade-date meaning. Reconcile May 31, June 21, July 5, and September 6 combined holiday sessions against the corrected calendar, rather than grouping on UTC calendar date alone. Check all 1,080 target-contract/predecessor cells from the manifest.
4. **Publication and receipt.** Preserve `ts_event`, `ts_recv`, publisher, instrument ID, `ts_ref`, and any source-publish field or external bulletin timestamp. For each decision, identify the last value actually received by the origin, ordinarily 5 p.m. ET at the completed predecessor close (21:00 UTC in daylight time, 22:00 UTC in standard time). Separate that as-of value from later preliminary and final reports. If exchange publication time is absent, `ts_recv` supplies a provider receipt bound, not proof of exchange-wide availability.
5. **Corrections and revisions.** Keep the full ordered stream per `(instrument_id, stat_type, ts_ref)`, including `update_action`, `stat_flags`, venue `sequence`/`channel_id`, deletions, repeated values, and late messages. Derive both the value known at origin and the final observed value, show the change log, and mark any boundary-truncated stream unresolved. Requote a later bounded tail before relying on the final November 18 statistic.
6. **Numbers and explicit zeros.** Accept a volume only from a valid numeric cleared-volume `quantity` with matching contract and `ts_ref`; reject the `INT64_MAX` unused sentinel. Accept zero only if the venue explicitly publishes numeric zero or independently confirms nonlisting/zero with a complete source. A missing statistics row, missing OHLCV bar, sentinel, or empty response is **unknown**, never zero.
7. **Missing records and source coverage.** Reconcile response `partial`/`not_found`, requested intervals, record counts, definition continuity, expected trading dates, dataset conditions, and venue sequence/channel continuity or provider gap evidence. Investigate each absent cell and any unexplained day. A dataset-level `available` flag and a successful response are insufficient to certify every instrument/statistic or absence of volume.
8. **Cleared versus Globex electronic volume.** Label statistics as venue-cleared volume and the retained OHLCV as Globex electronic-trade volume. Compare same-contract, same-CME-trade-date totals after corrected session aggregation; quantify differences and investigate blocks, clearing-only activity, corrections, bar omissions, and source gaps. Do not silently use a cleared-volume ranking to validate a Globex-volume selection rule. [Databento statistics example](https://databento.com/docs/examples/futures/retrieving-oi-and-settlement-prices), [statistics schedule example](https://databento.com/docs/examples/futures/statistics-schedule).

## Acceptance and remaining limitations

The existing audit finds **1,080 eligible cells**, **328 positive retained predecessor-volume cells**, **752 cells without retained volume**, and **zero confirmed zero-volume cells**. These counts describe a gap, not a result from the proposed retrieval. [Causal universe audit](nq-causal-contract-universe-audit.md).

A contract winner can be promoted only after the full historically effective nine-contract roster is supported and every consequential competitor has a same-metric, same-trade-date, origin-available numeric volume, an explicit proven zero, or an independently certified upper bound below the leader. Preserve the existing `max(volume, contract code)` tie rule and record unresolved dates without substitution from target-day bar presence. Final historical statistics published after 5 p.m. ET cannot be treated as available at that origin; a later forecast origin would require a separately registered decision and target window.

The two quoted requests have not been retrieved. They cannot yet establish record-level coverage, actual activation/expiration, `CLEARED_VOLUME` presence, zero representation, revision chronology, or the causal winner on any of the 120 dates. The amended statistics end still excludes possible November 18 corrections received November 23 or later. Dataset condition does not close that gap. This report makes no change to the production selector, certification tier, or HAR study.
