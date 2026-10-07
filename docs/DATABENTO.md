# Databento NQ historical data

The offline adapter is implemented. The phase is **not accepted yet**: the live key
is absent, so no licensed dataset, account cost estimate, human timestamp review,
or real weekly-VWAP result has been obtained. No historical data has been fabricated.

## Runtime and credentials

The default `.venv` now points to `.venv-py312` (Python 3.12.13); the original
Python 3.9.6 environment is preserved at `.venv-py39-backup-20261005`.
Restoring that environment also requires restoring pre-migration source/runtime
requirements from the retained backup; moving an environment alone is not a source rollback.

Use the project's Python 3.12 environment and official `databento==0.87.0` extra.
The core remains provider independent and uses the standard library. The SDK is
imported only for network acquisition; existing daily and intraday commands remain.
`requirements-py312.lock` records the tested dependency versions; its scope is this
macOS Python 3.12 installation, not a universal platform lock with wheel hashes.

The only credential source is the process environment `DATABENTO_API_KEY`.
`.env.example` is a template; the adapter deliberately does not automatically load
`.env`. Set the environment through your local secret-management workflow. Never
paste the key into chat, config, shell examples, test output or source control.
With no key, `download` prints `SKIPPED` and exits successfully without creating data.

## First range and cost gate

First estimate ten complete trading dates, September 14–25, 2026. This includes the
September quarterly expiry window. Expected nearby outrights are NQU26, NQZ26 and
NQH27; actual IDs, raw symbols and expirations must come from downloaded definitions.

```sh
cd /Users/jonathancho/Desktop/Projects/backtester
source .venv/bin/activate
backtester download --provider databento --symbol NQ --schema ohlcv-1m \
  --start 2026-09-13T22:00:00Z --end 2026-09-25T21:00:00Z \
  --estimate-only
```

`start` is inclusive and `end` exclusive. Bare dates mean midnight UTC and can
produce partial exchange sessions; use explicit UTC instants for complete dates.
Estimation requests cost, billable bytes and record counts for all three schemas.
They cover the **entire parent selection**, including outrights excluded later
from nearby normalization. No account cost/size/count can be reported without key.
[Databento cost endpoint](https://databento.com/docs/api-reference-historical/metadata/metadata-get-cost).

After reviewing the estimate, authorize a specific ceiling. This example permits
only an aggregate estimate of at most one dollar; choose your own approved ceiling.
No automatic retries or additional purchases occur after a failed request.

```sh
backtester download --start 2026-09-13T22:00:00Z --end 2026-09-25T21:00:00Z \
  --calendar calendars/nq-2026-09-validation.json --output data \
  --max-cost-usd 1 --no-trade-policy materialize --nearby-contracts 3
```

The ceiling gates the estimate; it is **not a provider-enforced invoice cap**.
The command refuses a range longer than sixteen calendar days unless explicitly
permitted with `--allow-large-range`. `--estimate-only` never downloads time series.
Do not execute a meaningfully expensive request without reviewing and authorizing
its total. Missing key skips both requests above cleanly.

## Boundary and storage

The gateway calls official Historical metadata endpoints `get_cost`,
`get_billable_size`, `get_record_count`, `get_dataset_condition`, `get_dataset_range`,
then `timeseries.get_range` for `definition`, `ohlcv-1m`, `statistics`.
Every request uses `dataset=GLBX.MDP3`, `symbols=[NQ.FUT]`, `stype_in=parent`.
Definitions include whole UTC days around the requested interval, to obtain an
initial snapshot. Bars and statistics use exactly the requested interval. Output
IDs use the SDK's default `instrument_id` symbology. There is no continuous chart
input, live endpoint, broker connection or new strategy.

Each acquisition gets a unique directory and refuses existing directories:

```text
data/raw/databento/NQ/<acquisition-id>/
  request.json
  definition.dbn.zst + definition.jsonl
  ohlcv-1m.dbn.zst + ohlcv-1m.jsonl
  statistics.dbn.zst + statistics.jsonl
  manifest.json

data/normalized/databento/NQ/<acquisition-id>/
  bars.csv
  metadata.json
  research-config.json
```

DBN data is retained alongside fixed-point, integer-nanosecond JSONL exports.
Successful raw files are made read-only. The manifest hashes each schema and the
request file; the normalized sidecar hashes the manifest, source files and CSV.
Loaders verify hashes. Read-only permissions and SHA256 detect accidental change;
they are not tamper-proof archival storage or a signature proving source origin.
Partial requests keep raw files and a failure marker, and cannot be normalized.
DBN metadata must show the full range, no record limit, and no partial/not-found
symbols before the request is considered complete.

Re-normalization is offline, deterministic and goes to a new directory:

```sh
backtester normalize data/raw/databento/NQ/ID --output data/normalized/databento/NQ/NEW_ID \
  --calendar calendars/nq-2026-09-validation.json --no-trade-policy materialize
```

Identical inputs/options produce identical CSV bytes. Sidecars retain acquisition
and output-location provenance, so metadata for different locations is not promised
to be byte-identical. The normalizer materializes the narrow panel in memory; large
history should be acquired and reviewed in bounded chunks.

## Contract and timestamp semantics

`ts_event` is the **start** of the aggregation interval, based on trade-message
capture time (`ts_recv`), and the internal feature becomes available at bar end.
This matches the engine's interval-start convention. It does not establish exact
matching-engine trade timing or the latency of a live OHLCV publication.
Databento emits an OHLCV record only for intervals with a trade.
[Official OHLCV schema](https://databento.com/docs/schemas-and-data-formats/ohlcv).

The definition index applies metadata only after its event/capture availability,
rounding sub-microsecond availability upward. Raw one-digit years are normalized
using the provider's actual expiration year, retaining both raw symbol and ID.
Only NQ quarterly futures outrights are retained; spreads and more distant contracts
remain in raw data and their exclusion is counted. The default panel selects the
nearest three eligible expirations known at the request start. Contracts newly
listed later are not added retrospectively; long requests need bounded panels.
Missing definitions, conflicting versions, ambiguous UTC date-only expiration,
wrong exchange/currency or economics disagreement fail normalization.

Provider tick size and unit-of-measure quantity must agree with NQ's 0.25-point
minimum tick and $20/point ($5/tick). `contract_multiplier` counts deliverables and
is stored separately rather than mistaken for dollar point value. Unknown sentinel
values remain identifiable in raw metadata. The CME NQ page independently confirms
the economics. [CME NQ specification](https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.contractSpecs.html),
[Databento definitions](https://databento.com/docs/schemas-and-data-formats/instrument-definitions).

## Coverage and no-trade policy

For a scheduled minute, complete untruncated download plus provider UTC-day condition
`available` is treated as `PROVIDER_AVAILABLE`. An absent constituent record is then
classified `NO_TRADE`, with explicit evidence stating that **minute completeness is
inferred**, not independently proven. Missing/degraded/pending condition, uncovered
range or incomplete request is `UNKNOWN`. Published traded bars on unknown days are
retained but cannot establish complete research windows.
[Provider condition semantics](https://databento.com/docs/api-reference-historical/metadata/metadata-get-dataset-condition).

The default `preserve` policy leaves every absent record absent, with an audit entry.
Explicit `materialize` can create a flat previous-known-traded-price grid bar only
for an inferred available minute: `NO_TRADE`, zero volume, `published=False`, source
provenance retained and no fabricated `ts_event`. No initial backfill is permitted;
a no-trade minute before a contract's first known price is `NO_TRADE_UNPRICED` and
remains absent. **UNKNOWN is never filled.**

No-trade grid bars advance covered time but cannot change VWAP volume, price highs,
lows, opens, ATR samples, reaction touches, barriers or executable stop/fill state.
Forward windows spanning unknown coverage are censored. Daily provider health is
not a per-minute exchange audit; an unreported outage on an available day could
still be misclassified. This is the central limitation to inspect on the live trial.

## Rolls and OI

Completed-session volume determines the next contract; only the active and next
contracts must have complete matched prior-session coverage. Sparse unrelated third
contracts do not invalidate that comparison. A selected roll may wait until both
old/new bars are traded at the same minute. Carried grid prices cannot supply roll
opens. Missing active bars, incomplete liquidity comparison or lack of a traded
pair stops the run instead of inventing a transition.

Statistics type 9 is OI. The default preserves it as `RETROSPECTIVE`, and attaches
none to bars. Explicit `--oi-policy capture-time` permits a conservative capture
bound only when event/receive timestamps, update action and flags are valid. Its
availability is max(event,receive), rounded upward; `ts_ref` never becomes an
availability timestamp. Deletions clear eligible OI; unknown flags/timing stay
retrospective. This policy is an opt-in research assumption about capture-time
availability, not a live delivery guarantee. Default OI rolling therefore fails
when it lacks causal observations. [Official statistics schema](https://databento.com/docs/schemas-and-data-formats/statistics).

## Dated calendar and manual acceptance

`calendars/nq-2026-09-validation.json` explicitly covers the ten trial trading dates,
uses 18:00–17:00 ET ETH and 09:30–16:00 cash-session RTH, excludes daily maintenance
and weekends, and has no holiday exception within this narrow range. Its source
review note and canonical document are hashed. Dated overrides support full closure,
early close and intraday scheduled halts. Outside reviewed dates the adapter fails.

The legacy generic equity template retains a 16:15–16:30 ET pause for reproducible
old fixtures. It is obsolete for current NQ: CME removed the affected pause from
June 28, 2021. The Databento path excludes it. This change is supported by
[CME SER-8788](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2021/06/SER-8788.pdf)
and the [electronic trading notice](https://www.cmegroup.com/notices/electronic-trading/2021/06/20210621.html).
The [CME holiday index](https://www.cmegroup.com/trading-hours.html) places the 2026
Labor Day window before the chosen trial. Direct original-source downloads were
blocked with HTTP 403; the retained source note is an authored review with links,
not an exchange-signed archived schedule. Unscheduled halts remain unverified.

After acquisition, validate and produce a manual sample audit:

```sh
backtester validate-data data/normalized/databento/NQ/ID/bars.csv --symbol NQ \
  --config data/normalized/databento/NQ/ID/research-config.json
backtester inspect-provider data/normalized/databento/NQ/ID/bars.csv \
  --config data/normalized/databento/NQ/ID/research-config.json --samples 8
```

The audit hashes retained raw files, compares OHLCV with raw records, and displays
symbol, ID, timestamp, session, trading date, current and previous completed-bar
weekly VWAP, selected contract and roll details. It is a review aid, not proof of
completed human inspection. Inspect old/new overlapping bars, expiry metadata,
09:30 and 16:00 ET boundaries, Sunday/week resets, missing-state counts and roll
opens against the retained provider records and Databento's own display/export.
An independent licensed source is a useful further cross-check when available.

Only after that real trial passes manual review, run the existing event study:

```sh
backtester run --strategy weekly-vwap-reaction-v1 --symbol NQ \
  --data data/normalized/databento/NQ/ID/bars.csv \
  --config data/normalized/databento/NQ/ID/research-config.json
```

The generated volume-roll configuration is deliberately strict; missing active
coverage or a thin next-contract opening can require a separately reviewed roll
policy. A fixed-roll run with `--allow-missing` retains censoring where selection
is possible; that flag does not bypass invalid contract transitions. No sample
counts or performance conclusions are available until the real dataset runs.

## Tests and larger plan

Default tests are offline. `tests/test_databento.py` uses expressly invented fixtures
and covers mapping, IDs, fixed-point conversion, overlap, coverage, causal OI,
no-trade behavior, completed-session rolls, deterministic normalization, hashes,
redaction, failure retention, SDK DBN round trips, CLI provenance and cost gates.
The live integration check is metadata/estimate only; opt in explicitly:

```sh
BACKTESTER_LIVE_TESTS=1 python -m pytest -q -m integration
```

After the ten-day acceptance, the recommended first larger study is seventeen full
weeks: trading dates **2026-06-08 through 2026-10-02**, UTC request
`2026-06-07T22:00:00Z` to `2026-10-02T21:00:00Z`. Expected study constituents are
NQM26/NQU26/NQZ26; retain an additional nearby contract where needed for overlap.
These are planning symbols, not downloaded confirmations. Extend and review the
dated calendar for Juneteenth, Independence Day, Labor Day and all applicable
exceptions before acquisition. Estimate the entire parent, definitions and statistics
first; exact record count, bytes and account cost remain **unavailable without key**.

```sh
backtester download --start 2026-06-07T22:00:00Z --end 2026-10-02T21:00:00Z --estimate-only
```

There is no authorization here to execute a large billed request. Do not treat the
seventeen-week recommendation or tiny smoke sample as evidence of a trading edge.
