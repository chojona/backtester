# NQ W1 five-gap evidence investigation

**Executed:** 2026-10-14T20:54:56.816009Z fresh authenticated account quote; completed 2026-10-14T20:55:45.863759Z. **Decision:** all five intervals are **provider-observed no trade** in the returned Databento stream, with trading-state evidence. This does not establish exchange-wide completeness or change certification. The ten authorized bounded responses are complete and preserved in `data/raw/databento/NQ/w1-five-gap-investigation-20261014T205456Z/`.

## Pre-retrieval gate

The candidate manifest SHA-256 was `b3a702768c7444f4c6cd5e692e57b1fc0b0e47919ff9445991adb465f6a07c2e`. Before the quote, the script compared all five active gap identities, raw symbols, session opens, and half-open minute bounds against a fixed independent five-row list, then compared all ten complete request argument sets and their order against `retrieval.requests` in the preserved candidate. It checked that the source Parquet and Phase 3 ledger still matched the hashes in that candidate and that retrieval had not already been marked performed. The same request and manifest checks passed again after the quote. No scope changed.

The fresh Databento Historical metadata quote was **$0.000777244568** combined, below the authorized **$0.01** stop threshold, with 31,520 estimated billable bytes and 665 estimated records. These are account-specific estimates, not invoice caps or actual charges. The preserved candidate quote was the same amount. No extra dataset, symbol, interval, or ten-minute comparison was retrieved.

## Exact requests and responses

Every row used `dataset="GLBX.MDP3"`, `stype_in="raw_symbol"`, one `symbols` entry shown below, the indicated `schema`, `start` inclusive, and `end` exclusive. The request had no record limit. The local file prefix refers to `.dbn.zst` and `.jsonl` files in the evidence directory. Times are UTC.

| # | Trade date | Schema / raw symbol | Start | End | Est. records / bytes / USD | Returned | DBN SHA-256 |
| ---: | --- | --- | --- | --- | ---: | ---: | --- |
| 1 | 2022-06-06 | `trades` / `NQM2` | `2022-06-05T23:27:00Z` | `2022-06-05T23:28:00Z` | 138 / 6,624 / $0.000172734261 | **0** | `112467a8d5302069bd5a9506d439d4b364cd4fea7af4fcdbe8472e616d3386a7` |
| 2 | 2022-06-06 | `status` / `NQM2` | `2022-06-05T22:00:00Z` | `2022-06-05T23:28:00Z` | 5 / 200 / $0.000000745058 | **2** | `0343c57283e7ffa585235ba6124a8c439dabb2507ecae0e29eba25190105cbd0` |
| 3 | 2022-07-27 | `trades` / `NQU2` | `2022-07-27T03:56:00Z` | `2022-07-27T03:57:00Z` | 102 / 4,896 / $0.000127673149 | **0** | `b8d97f09377b9830690cdbcf4f615b494c45fdab0173610548127fd9c75472a7` |
| 4 | 2022-07-27 | `status` / `NQU2` | `2022-07-26T22:00:00Z` | `2022-07-27T03:57:00Z` | 12 / 480 / $0.000001788139 | **3** | `249d5602819bd1243d7e2afbc47f4a364f83d90f94d087d01768d1989166a615` |
| 5 | 2022-08-16 | `trades` / `NQU2` | `2022-08-16T04:43:00Z` | `2022-08-16T04:44:00Z` | 137 / 6,576 / $0.000171482563 | **0** | `65d730ac93abbfb3067f2b9d702e5d5dca8686d539edcd81d99b6daba1d464e0` |
| 6 | 2022-08-16 | `status` / `NQU2` | `2022-08-15T22:00:00Z` | `2022-08-16T04:44:00Z` | 12 / 480 / $0.000001788139 | **3** | `fa936a430c14c8071a9b0c499ab0cb14f56da7cde34be0f271f718ccbdef3c8f` |
| 7 | 2022-08-18 | `trades` / `NQU2` | `2022-08-18T04:42:00Z` | `2022-08-18T04:43:00Z` | 111 / 5,328 / $0.000138938427 | **0** | `c150005a5430bce6e6bf0bf1afea1d49f3fca5ece834be282997da747d03be0f` |
| 8 | 2022-08-18 | `status` / `NQU2` | `2022-08-17T22:00:00Z` | `2022-08-18T04:43:00Z` | 12 / 480 / $0.000001788139 | **3** | `3eb707c24a042b8ca56688ea6cb19a934eea330d650f969c9d4a960e451b8938` |
| 9 | 2022-10-13 | `trades` / `NQZ2` | `2022-10-12T22:48:00Z` | `2022-10-12T22:49:00Z` | 127 / 6,096 / $0.000158965588 | **0** | `e4bde64ba11ede29802cb7e4062cc0d80075fb915e149c54508f29174d31762b` |
| 10 | 2022-10-13 | `status` / `NQZ2` | `2022-10-12T22:00:00Z` | `2022-10-12T22:49:00Z` | 9 / 360 / $0.000001341105 | **2** | `fee64e624c9f1a0033a431d527642e5e64c20fbed5a7444e6c3316bf7a7dd3ad` |

All ten DBN metadata blocks report the exact requested dataset, schema, raw symbol, and start/end nanosecond bounds; `limit=null`, `partial=[]`, and `not_found=[]`. The preserved manifest records each metadata block, local compressed DBN byte size, JSONL export hash and count, and exact request parameters. Independent rereads of all ten DBN files verified these metadata and every file hash. The five trade files contain zero records in total; the five status files contain 13 records in total. Local file bytes are not provider billable bytes.

The SDK responses did not report settled cost or actual billable bytes. `actual_reported_cost_usd` is null in the evidence manifest; the **$0.000777244568** figure remains an estimate.

## Independent comparison with retained OHLCV

The retained source is `results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet` (SHA-256 `16a626bf24c90a73a176e4a21138f58c40e3a5c35ae70a57643c3f1878f94c44`). For each raw symbol I queried the retained Parquet only from one minute before through one minute after the gap, then checked the exact missing timestamp, the adjacent bar volumes and matching instrument IDs against the returned status events. The gap has no retained bar in every case.

| Trade date / gap UTC | Prior bar volume | Next bar volume | Trades in bounded response | Status observations through gap | Classification |
| --- | ---: | ---: | ---: | --- | --- |
| 2022-06-06 / 2022-06-05 23:27 | 21 | 30 | **0** | 2 events at 22:00: action 6 then 7, trading Y | **Provider-observed no trade** |
| 2022-07-27 / 03:56 | 11 | 24 | **0** | 3 events: 22:00 action 6 then 7; 00:00 action 7 snapshot, trading Y | **Provider-observed no trade** |
| 2022-08-16 / 04:43 | 17 | 28 | **0** | 3 events: 22:00 action 6 then 7; 00:00 action 7 snapshot, trading Y | **Provider-observed no trade** |
| 2022-08-18 / 04:42 | 9 | 19 | **0** | 3 events: 22:00 action 6 then 7; 00:00 action 7 snapshot, trading Y | **Provider-observed no trade** |
| 2022-10-13 / 2022-10-12 22:48 | 1 | 2 | **0** | 2 events at 22:00: action 6 then 7, trading Y | **Provider-observed no trade** |

The status records also all have `is_quoting="Y"`; no returned halt, pause, suspend, close, or non-trading state appears. The 00:00 records carry the prior 22:00 `ts_event`, so they are state snapshots rather than new transitions. Each status instrument ID matches its adjacent retained OHLCV bars: 2895 for `NQM2`, 10391 for `NQU2`, and 13613 for `NQZ2`. With zero trade records returned, there is no `ts_event`/`ts_recv` boundary ambiguity within any one-minute trade response.

The empty trade responses and active-state status stream support the provider-observed no-trade classification for each interval. They do **not** prove no exchange trade occurred: a missing upstream message could affect both the trade stream and trade-derived OHLCV, while status reports changes rather than independently certifying every moment. No venue-sequence audit, independent provider tape, or repair attestation was obtained. Therefore none of the five intervals is classified as an observed trade with missing OHLCV or an observed exchange interruption; exchange-wide completeness remains unresolved. This evidence alone does not justify a certification-tier change or imputation.

## Preservation and verification

The original compressed DBN responses are preserved separately from the full-history acquisition at `data/raw/databento/NQ/w1-five-gap-investigation-20261014T205456Z/`. Its `manifest.json` binds the candidate, source hashes, fresh quote, all requests, all ten DBN SHA-256 digests, metadata, response counts, and local export hashes. The evidence directory is Git-ignored; it must be retained or separately archived with this report. The acquisition made exactly ten `timeseries.get_range` calls after the successful quote. A read-back audit passed for exact request and metadata matching, ten DBN and JSONL hashes and counts, source hashes, adjacent OHLCV bars, and status instrument IDs. Raw OHLCV, certification tiers, production estimators, and HAR artifacts were not edited.

The still-open calendar and predecessor-volume gates described in [NQ W1 final calendar readiness](nq-w1-final-calendar-readiness.md) are unaffected. The earlier [single-gap investigation](nq-databento-gap-investigation.md) explains the same trade-generated OHLCV and status-state interpretation used here.
