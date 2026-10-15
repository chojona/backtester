# NQ research session interface v1.0.0

`backtester.nq_research_data` reads existing sealed artifacts. It does not write raw data, certification, selectors, or forecasting code. The interface schema is `nq-research-session-v1.0.0`.

## Modes and sources

| Mode | Source | Gate | Availability |
| --- | --- | --- | --- |
| `strict` | Phase 3 Tier A Parquet and allowlist; versioned segmented BPV register | Tier A, full active grid, matching hashes | `unknown`; no historical receipt time is asserted |
| `conditional` | W1 exploratory v1.0.0 daily release and manifest | `allow_conditional=True`; all input/output hashes checked | `assumed`; session close plus 45 minutes is a research timing assumption |
| `prospective` | Caller-supplied sealed manifest and daily JSON | Observed receipt timestamp, complete session, hash-verified inputs | `observed`; no such release ships with this repository |

The `conditional` release is a separately approved calculation path. Its original Tier C dates remain Tier C in `historical_tier`. Its selected contracts are not silently promoted to certified winners. `strict` and `conditional` calls return separate tuples; window construction rejects mixing them.

## Observation schema

Each immutable `SessionObservation` has `schema_version`, `eligibility`, `cme_trade_date`, `selected_contract`, half-open `session_start_utc` and `session_end_utc`, `realized_variance`, `positive_semivariance`, `negative_semivariance`, `bipower_variation`, `eligible_minute_count`, `missing_minute_count`, `has_missing_minutes`, `continuity_ok`, `evidence_classification`, `assumption_ids`, `source_hashes`, `methodology_version`, `availability_time_utc`, `availability_status`, `session_ordinal`, `continuity_segment`, `calendar_status`, and `historical_tier`.

Measures are unannualized sums of one-minute log-return powers. Strict BPV uses `bpv-segment-v1.0.0`; conditional BPV uses the frozen `nq-clock-returns-v2.0.0` release. Missing or discontinuous sessions are rejected, never filled. The five W1 provider-supported no-trade minutes are evidenced zero-return clock minutes, listed by assumption ID and in the sealed minute-classification file; they are not invented OHLCV bars. `source_hashes` names all release inputs and outputs, including the selected Parquet or minute ledger and their manifests. Load verifies these hashes before returning observations.

The strict source contains no recorded historical delivery time, so `availability_time_utc=None` and `availability_status='unknown'`. The conditional release's `assumed_finalization_utc` field is a **predecessor selector deadline**, not availability of that target session's variance. For each conditional observation the interface assigns its own session close plus the release's assumed 45-minute finalization delay. This remains `availability_status='assumed'` and must never be treated as an observed timestamp. A prospective record requires a recorded availability time after its session end and a hash-linked source artifact.

## Consecutive windows

`consecutive_windows(sessions, length)` returns ordered `SessionWindow` objects containing the exact observations and combined hash lineage; it calculates no lag features, targets, forecasts, or models. A missing ordinal, strict certification-segment break, or unsupported date gap prevents a window. Conditional windows require `conditional_policy='release_chronology'`, which explicitly accepts the release's frozen 120-date sequence and its documented combined Tuesday holiday sessions. This policy carries the release's selector, calendar, and availability assumptions; it does not resolve them. Removing any released date breaks windows across that date.

```python
from backtester.nq_research_data import load_sessions, consecutive_windows

sessions = load_sessions("conditional", allow_conditional=True)
windows = consecutive_windows(sessions, 23, conditional_policy="release_chronology")
print(len(sessions), len(windows))  # 120, 98
print(windows[0].observations[0].cme_trade_date,
      windows[0].observations[-1].cme_trade_date)  # 2022-06-02, 2022-07-06
```

Run `.venv/bin/python -m scripts.example_nq_research_data` to inspect current counts. Prospective mode takes `prospective_manifest="path/inside/root/manifest.json"`; its JSON manifest must specify `schema_version`, `eligibility="prospective"`, `methodology_version`, `session_count`, `source_sha256`, `observations_file`, and `observations_sha256`. The observation JSON is a list of schema field names with ISO UTC timestamps and `evidence_classification="prospective_observed"`. Every source path is relative to the research root and must match its SHA-256 digest.

## Research limits

The W1 path has ten unresolved selector winners, nine provisional ordinary-hours dates, five provider-supported no-trade clock minutes, and no demonstrated historical point-in-time publication or revision times. Its 98 windows are conditional chronology windows, not evidence of forecast feasibility or trading alpha. The strict path has 11 Tier A dates in two continuity segments and no 23-session windows. Downstream work must keep each observation's eligibility, assumptions, availability status, and lineage with every derived result.
