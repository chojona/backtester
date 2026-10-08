# Full-history NQ preparation and acquisition

The scripts in `scripts/` extend the small NQ trial toward longer raw history.
They run from the repository root using Python 3.12+ and the optional Databento
extra. Credentials come only from the process environment; see
[DATABENTO.md](DATABENTO.md). Generated metadata, plans and reports live under
Git-ignored `results/databento-history-preparation/`; raw history lives under
`data/raw/databento/NQ/full-history/`.

## Scope and current limits

The acquisition plan uses `GLBX.MDP3`, explicit quarterly NQ outright raw symbols,
`definition` and `ohlcv-1m`. Unlike the trial CLI, it excludes parent-family spread
retrieval and does not request statistics. Each chunk selects three quarterly
expirations for overlap. Planning symbols use estimated quarterly expiry dates;
downloaded definitions must establish actual identifiers and expirations.

Core intervals are 90 calendar days, with up to seven calendar days of prior
history on following requests. OHLCV spans at most 97 calendar days per chunk;
definition requests round outward to whole UTC days. Requests have stable hashes.
The seven-day overlap supplies a prior-session buffer; it does not implement
cross-chunk causal state or verify deduplication by itself.

The retained ten-session trial is the currently documented accepted dataset.
Full-history raw downloads, if present locally, remain pending reviewed calendars,
normalization, overlap checks and acceptance. A provider availability endpoint
or an elapsed session close does not prove complete usable market data. The
preparation scripts do not implement forecasting or trading.

## Metadata-only preparation

```sh
python -m scripts.prepare_nq_history --discovery-only
python -m scripts.prepare_nq_history
```

Both commands contact metadata endpoints and make no time-series downloads.
Discovery records provider range, a ten-minute block containing the earliest
confirmed NQ observations, and a latest elapsed session candidate with provider
conditions. The first exact bar timestamp remains pending raw inspection.
The current latest-session probe assumes an ordinary October close and NQZ6;
review it before using this script at another date. Historical exception calendars
are a separate requirement.

Preparation writes `discovery.json`, `requests.json`, cached metadata responses,
per-chunk estimates and, only after successful estimation, `plan.json`. Estimates
cover the exact definition/OHLCV requests, including repeated overlap. Successful
metadata responses are reused on resume: these are dated observations, not fresh
prices. Use a new `--output results/NEW_PREPARATION` directory when scope, account
or pricing changes. Incomplete estimation does not supply an approved plan.

The script has a hard **$85 aggregate estimate limit**. It records
`AWAITING_EXPLICIT_USER_COST_APPROVAL` or `OVER_HARD_COST_LIMIT` and sets
`billable_download_authorized=false`. An estimate is not a guaranteed invoice cap.

## Local dry-run and coverage reports

After discovery, the default preparation directory can produce a non-acquisition
summary; the coverage report also requires the retained trial inputs:

```sh
python -m scripts.write_nq_history_dry_run
python -m scripts.report_nq_history_coverage
```

`write_nq_history_dry_run` describes the retained October 7, 2026 metadata-estimate
failure; it contains dated availability and condition statements. It is not a
general live status check or a replacement for a successful `plan.json`.
`report_nq_history_coverage` verifies the trial evidence input hashes and writes
`coverage-by-date.csv` plus `coverage-summary.json`. It lists every calendar date,
including weekends, and labels unacquired dates as unknown rather than market gaps.
New raw chunks are not automatically counted as accepted sessions.

## Frozen-plan preflight and acquisition

After reviewing a successful plan and obtaining explicit approval of its exact
total and SHA-256, run an offline preflight. Replace both placeholders with values
from that approved `plan.json`:

```sh
python -m scripts.acquire_nq_history \
  --plan results/databento-history-preparation/plan.json \
  --approved-plan-sha256 APPROVED_SHA256 \
  --approved-total-usd APPROVED_TOTAL
```

Without `--execute-approved-download`, this verifies the plan and retained complete
chunks without network calls. Supplying approval values alone is not the billed
execution switch. Add `--execute-approved-download` only for the explicitly
approved acquisition. The script verifies request hashes and reconciles totals,
reprices all remaining chunks before downloading, and stops if any chunk estimate
increases. Completed chunks are reused only after manifest and file-hash checks.
Partial/corrupt chunks stop for review instead of being automatically retried.

Acquisition retains compressed DBN, JSONL, request metadata and manifests. It ends
at `RAW_ACQUIRED_PENDING_CALENDAR_AND_ACCEPTANCE`; it does not normalize history.
The software cost gates do not enforce a provider invoice cap.

## Before using history for research

Review dated exchange calendars across the full span, including holidays, early
closes and DST. Verify definitions, source conditions and missing coverage;
compare duplicate contract-ID/timestamp records across overlaps before removing
them. Define initial-contract selection and maintain causal roll state across
chunks. Preserve paired traded opens and distinguish raw prices from adjusted
research coordinates. Independently verify daily targets and causal prefixes.

The [dated acceptance report](acceptance/databento-2026-10-07.md) proposes at least
778 accepted session observations for its first HAR study design. That is a
research recommendation, not an implemented model or an acquisition approval.
The ten-day trial and earlier seventeen-week proposal do not meet that design.
