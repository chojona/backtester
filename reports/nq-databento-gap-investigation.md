# Databento NQ missing-minute investigation

**Investigation time:** 2026-10-14 19:38–19:43 UTC (15:38–15:43 America/New_York).
**Result — explained within Databento's record stream:** The authorized bounded retrieval returned **zero `trades` records** in the missing minute. The returned `status` records show trading at the session open and in a midnight carried-state snapshot, with no subsequent halt or pause record before the gap. The absent OHLCV bar is consistent with a no-trade minute in Databento's available record stream. This test found no OHLCV/trade inconsistency; absolute exchange-level completeness is not established.

## Scope and credential handling

The target is **2022-02-15 23:47:00–23:48:00 EST**, equivalently **2022-02-16 04:47:00–04:48:00 UTC**, with an inclusive start and exclusive end. The dataset is `GLBX.MDP3`. The project-local `.env` contains `DATABENTO_API_KEY` on line 2, with file mode `0600`; the value was read only into the SDK process and was not printed or written to this report. The installed official Python SDK is `databento==0.87.0`. The initial sandboxed connection failed; the metadata-only retry succeeded with host network access.

## Authentication, availability, and identity

The authenticated Historical client successfully called `metadata.list_datasets`, `metadata.list_schemas`, `metadata.get_dataset_range`, `metadata.get_dataset_condition`, `symbology.resolve`, and the three estimate methods. `GLBX.MDP3` appeared in the dataset list. `trades`, `status`, `statistics`, and `ohlcv-1m` appeared in the schema list. For each of those schemas the reported dataset range covered the target: start `2010-06-06T00:00:00Z`; the range response ended `2026-10-14T11:38:36.230357Z` at the time queried. The UTC day `2022-02-16` had condition `available`, last modified `2026-08-31`.

The retained history names the canonical contract **NQH22**, but its Databento **raw symbol is `NQH2`**. For `2022-02-16` to `2022-02-17`, Databento resolved `NQH2` to instrument ID **3541** with status `OK`, no partial or missing symbols. Trying `NQH22` as a raw symbol returned `Not found`. All estimates below therefore use `symbols=["NQH2"]`, `stype_in="raw_symbol"`; they do not use a continuous or parent symbol.

Successful schema listing, range queries, symbology resolution, and account-specific estimates established metadata access and showed the schemas offered for this dataset. The later successful `trades` and `status` retrievals established practical access to those two bounded requests. No `statistics` time-series request was made, so its retrieval entitlement was not tested. The [Historical API documentation](https://databento.com/docs/api-reference-historical) identifies HTTP 403 as insufficient permissions and says metadata and symbology access are free.

## Pre-retrieval estimates

The exact missing-minute estimate used `2022-02-16T04:47:00Z` to `04:48:00Z`. All counts and byte sizes here are **provider estimates**, not retrieved records. Databento warns that estimates for spans shorter than discrete ten-minute blocks can over-report; actual billing is based on delivered bytes. [Cost method documentation](https://databento.com/docs/api-reference-historical).

| Schema and UTC window | Estimated records | Estimated billable bytes | Estimated USD |
| --- | ---: | ---: | ---: |
| `trades`, 04:47–04:48 | 90 | 4,320 | 0.000112652779 |
| `status`, 04:47–04:48 | 6 | 240 | 0.000000894070 |
| `statistics`, 04:47–04:48 | 0 | 0 | 0.000000000000 |
| **Combined one-minute scope** | **96** | **4,560** | **0.000113546849** |

For status context, a separate metadata-only estimate covered `2022-02-15T23:00:00Z` through `2022-02-16T04:48:00Z`: **12 estimated records, 480 bytes, $0.000001788139**. A ten-minute `status` window of `04:40–04:50Z` estimated 6 records, 240 bytes, $0.000000894070. The practical follow-up scope would pair the **one-minute `trades` request** with the **session-to-gap `status` request**, for a combined estimate of **$0.000114440918**, 102 estimated records and 4,800 estimated billable bytes. This is an estimate, not a guaranteed invoice cap. The wider status span matters because status changes can precede the missing minute; Databento also documents a carried-status snapshot at UTC midnight. [Status schema](https://databento.com/docs/schemas-and-data-formats/status).

These were the initial metadata-only estimates. Retrieval stopped at that stage pending authorization. The user then authorized one bounded `trades` and `status` investigation with a combined pre-retrieval estimated cost of at most $0.01; the execution below uses precisely those two windows. `statistics` was not retrieved.

## Authorized retrieval and actual records

Immediately before retrieval, at **2026-10-14 19:42:38 UTC**, the authenticated client again confirmed `GLBX.MDP3` access, `trades` and `status` in the schema list, their dataset ranges covering both windows, and `NQH2` resolving to instrument ID **3541** with no partial or missing mapping. The fresh account-specific estimates matched the earlier estimates. The script summed decimal estimates and enforced the user-authorized **$0.01** ceiling before either `timeseries.get_range` call. It made exactly two time-series calls, one per authorized schema and window, with no record limit and no additional paid queries. Both DBN responses report the requested dataset and schema, full start/end bounds, `limit=null`, `partial=[]`, and `not_found=[]`.

| Request, inclusive start / exclusive end UTC | Fresh estimated records | Fresh estimated billable bytes | Fresh estimated USD | Actual returned records | Local `.dbn.zst` bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `trades`, 2022-02-16 04:47–04:48 | 90 | 4,320 | 0.000112652779 | **0** | 109 |
| `status`, 2022-02-15 23:00 to 2022-02-16 04:48 | 12 | 480 | 0.000001788139 | **3** | 161 |
| **Combined** | **102** | **4,800** | **0.000114440918** | **3** | **270** |

The zero-record trade DBN has SHA-256 `b351972c9a66d514b97d6b944d90c783cdc770268078e18850a1b3d3059e805b`; the three-record status DBN has SHA-256 `d26aadc23c4ce02c5ed49574a1aa62f80fee2980581d6c3be0556e3de2c250c0`. The exact SDK-produced DBN responses and their JSON exports are preserved in the separate, Git-ignored `data/raw/databento/NQ/gap-investigation-20261014T194238Z/` directory, with request and response provenance and verified SHA-256 hashes in its `manifest.json`. This did not alter the earlier full-history acquisition. The trade JSON export was 0 bytes and the status JSON export 684 bytes. **These are local serialized file sizes, not actual provider billable bytes.** The SDK responses did not provide actual billable-byte counts or an invoice/settled charge. The reported amount above is an estimate, not a confirmed charge. The [Historical API cost documentation](https://databento.com/docs/api-reference-historical) says billing is based on bytes actually sent and cautions that short-window estimates can over-report.

The `trades` response contains **zero records total**, hence **zero events with `ts_event` in `[2022-02-16T04:47:00Z, 04:48:00Z)`**, and summed trade size zero. The DBN request metadata bounds are `1644986820000000000` to `1644986880000000000` nanoseconds. Counting by `ts_event` is deliberate: Databento's Historical time-series API filters `trades` by `ts_recv` where that field exists. With no returned records, there are no off-minute returned events to separate. [Historical time-series semantics](https://databento.com/docs/api-reference-historical).

All three returned `status` records identify instrument **3541**. Their `ts_event` is `2022-02-15T23:00:00Z`:

| `ts_recv` UTC | Action | Reason | `is_trading` / `is_quoting` | Interpretation |
| --- | --- | --- | --- | --- |
| 2022-02-15 23:00:00.014494598 | 6 | 1 | Y / Y | New price indication, scheduled |
| 2022-02-15 23:00:00.015571044 | 7 | 1 | Y / Y | Trading, scheduled |
| 2022-02-16 00:00:00 | 7 | 1 | Y / Y | Carried-forward trading state at UTC midnight |

Databento defines action 7 as trading and action 8/9 as halt/pause; `is_trading=Y` is its best-efforts trading-state flag. It documents a midnight snapshot of the last status for active instruments when state carries across UTC days. There is **no returned halt, pause, suspend, close, or non-trading state through 04:48Z**. The 00:00 record repeats the 23:00 `ts_event`, so it is a state snapshot, not a new 00:00 exchange transition. Assuming the returned status stream has all relevant changes, the midnight trading state carries through the missing minute. A status stream reports state changes, not one affirmation per minute; it does not independently certify that every possible interruption was captured. [Status schema and snapshot semantics](https://databento.com/docs/schemas-and-data-formats/status).

## Comparison with retained OHLCV

The retained consolidated source is `results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet`. Its underlying completed raw acquisition for the target is `data/raw/databento/NQ/full-history/8c2dcea828fa59a0/3ce0c93b12d8b08e/manifest.json`, which requested `ohlcv-1m` and `definition` for raw symbols `NQH2`, `NQM2`, and `NQU2` from `2021-12-28T23:00:00Z` to `2022-04-04T22:00:00Z`. The manifest marks the acquisition complete with no partial or not-found symbols. Its recorded SHA-256 for `ohlcv-1m.dbn.zst` is `75fda97820e0e822ca27e0ca53836ce504df6205bf4a37d92b05d8ccf9eb13c4`.

For raw `NQH2`, instrument ID 3541, retained bars start at **04:46Z** (open 14558.75, high 14559.25, low 14558.25, close 14558.25, volume 26) and resume at **04:48Z** (open 14558.75, high 14558.75, low 14557.25, close 14557.25, volume 10). There is **no 04:47Z bar** in the retained source. The existing certification ledger classifies the 2022-02-16 trading date as Tier C, `C_SPARSE_OR_OFF_SCHEDULE_TRADE_BARS`, with **1,379 of 1,380** expected active minutes and exclusion from strict research. The [2022 evidence pilot](nq-2022-evidence-pilot.md) identifies this same minute.

## Conclusion and limits

The returned raw trade stream has **no NQH2 trade in the missing minute**, matching the missing retained `ohlcv-1m` bar between positive-volume 04:46Z and 04:48Z bars. The returned status stream gives **no halt or pause explanation** and indicates trading was enabled as of the last carried state. Together, these observations favor a **no-trade minute in Databento's available feed** over a scheduled closure or recorded interruption. Databento's [OHLCV schema](https://databento.com/docs/schemas-and-data-formats/ohlcv) is trade-aggregated, so no trade normally means no published bar.

This is **provider-stream evidence, not proof that no exchange trade existed**. A missing trade message upstream could make both Databento's `trades` and derived OHLCV absent. The UTC-day dataset condition `available` means no known dataset issue, not minute-level completeness certification. The status flags are best efforts, and the requested status window begins at the session open; it does not independently verify every intervening moment. The earlier estimate of 90 trade records was a rounded metadata estimate, not an observed count. This investigation did not obtain a venue-sequence audit, independent vendor tape, or Databento repair attestation, and it did not alter the existing Tier C certification decision or fit HAR.

**Next recommended action:** Record this as a provider-observed no-trade minute with active-state evidence in the gap ledger, while keeping the date excluded from strict Tier A research. If a tier change is later proposed, require independent exchange or provider completeness evidence for this exact interval and review the applicable certification rule first. The one authorized paid investigation is complete; further Databento paid queries require new authorization.
