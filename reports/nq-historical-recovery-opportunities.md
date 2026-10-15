# NQ historical recovery opportunity audit

Date: 2026-10-14 (America/New_York). **Decision: investigate 2022-06-07 through 2022-11-21 first.** This is a 120-*observed*-session opportunity, not an eligible 120-session HAR sample. The existing longest uninterrupted A/B run is 44 sessions. No paid data was requested, no tier or estimator was changed, and neither strict nor exploratory historical HAR can run yet.

## Local basis and counting rules

This audit uses the retained Phase 3 [session decisions](../results/databento-nq-full-history/phase3-v3.0.0/certification-by-session.csv), [calendar register](../calendars/nq-history-v3.json), [unobserved weekday register](../results/databento-nq-full-history/phase3-v3.0.0/missing-date-candidates.csv), selected-contract [consolidated OHLCV](../results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet), the [complete failure ledger](nq-certification-blockers/all-excluded-and-provisional-sessions.csv), and the [completed no-trade experiment](nq-no-trade-minute-validation.md). Input SHA-256 hashes and every Tier C date's primary reason, simultaneous failed gates, and coverage counts are in the [machine-readable manifest](../results/nq-recovery-candidate-windows.json). Its 2,858 `tier_c_sessions` entries are the complete enumeration, in trading-date order; the pre-existing ledger remains the full B/C/D strict-gate inventory.

A window counts consecutive *observed rows* inclusively. An intervening unobserved weekday is listed separately and cannot be assumed closed. Missing minutes are `ordinary-regime expected active UTC minutes − retained selected-contract minute timestamps`; dated CME exceptions could reduce these provisional counts. The manifest groups adjacent missing minutes into half-open UTC intervals and records the actual raw symbol found in the retained selected-contract rows. The ordinary grid is unavailable for pre-2012 dates, so this audit does not invent their minute intervals. All seven selected windows begin after the 2012 regime change and contain no D date or pre-2012 mapping dependency.

## All Tier C failures and recoverability

The primary reason code is a classifier priority, while the four gate states in each manifest entry capture simultaneous failures. These primary groups partition all **2,858** Tier C sessions:

| Primary Tier C reason | Sessions | Recovery question |
|---|---:|---|
| Incomplete causal contract evidence | 1,527 | Verify the previous trade date, candidate-contract volumes, and predecessor's calendar/coverage before re-evaluating the roll. |
| Pre-2012 trade-date remap required | 635 | Rebuild the known ordinary assignment in an isolated version, then resolve dated exceptions and downstream rolls. |
| Holiday or early-close guard | 489 | Obtain dated CME NQ hours; a guard is not proof of an exchange exception. |
| Sparse or off-schedule selected bars | 159 | Compare exact minutes with a dated CME grid; obtain independent trade/status/completeness evidence for minutes that remain active. |
| Degraded or absent provider metadata | 34 | Resolve provider condition and source completeness; retained daily metadata cannot prove minute completeness. |
| Specific 2026 holiday hours unresolved | 14 | Obtain the exact dated NQ holiday/reopening schedule. |

Across these same C rows, the overlapping states are **1,735 sparse/off-schedule**, **635 date-mapping unresolved**, and **488 full ordinary grids**; **2,052** have incomplete prior-volume evidence and **34** have degraded provider status. Nineteen sparse/off-schedule C rows have no ordinary-grid minute *shortfall*, so they cannot be called missing-minute recoveries. The original 56 unobserved weekday candidates are separate calendar questions. The two Tier D rows are the initial 2010-06-07 date lacking a prior-session roll buffer and the 2018-08-05 Sunday preopen artifact; the latter is a non-session observation, and the former cannot be made causal with the retained starting boundary alone. No Tier C missing interval has been proven irrecoverable; equally, none is automatically recoverable from OHLCV silence.

This separates the work into (1) potentially recoverable expected-minute gaps, subject to schedule and independent source evidence; (2) calendar or trade-date evidence, including guarded dates and unobserved weekdays; (3) provider integrity; and (4) causal contract evidence. All four applicable gates must pass together. A full grid or a zero-trade provider response cannot bypass another failed gate.

## Candidate windows

The scan evaluated 120-row spans in the post-2012 ledger and retained representative low-gap windows, plus a 150-row extension. Ranking favors no unknown weekday or provider flag, then fewer sparse sessions and ordinary one-minute holes; the larger 2026 opportunity is shown for its potential length. Calendar and roll counts overlap the C count. `Minutes` are provisional absent ordinary-grid minutes, not proven data loss. Every row has zero off-schedule and duplicate selected minutes.

| Rank / ID | Inclusive observed dates | Upper bound | Current A/B/C | Sparse sessions / minutes | Unknown weekdays | Provider flags | Guard / specific 2026 hours | Incomplete rolls | Investigation complexity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 / W1 | 2022-06-07–11-21 | 120 | 0/92/28 | 7 / 724 | 0 | 0 | 15 / 0 | 20 | Lowest: four isolated minutes plus three 240-minute holiday-pattern shortfalls. |
| 2 / W2 | 2022-02-25–08-12 | 120 | 0/97/23 | 7 / 724 | 1 | 0 | 11 / 0 | 15 | Similar gap work, but 2022-04-15 must be proved closed or supplied. |
| 3 / W3 | 2022-07-07–12-21 | 120 | 0/93/27 | 8 / 715 | 0 | 0 | 13 / 0 | 19 | Adds Thanksgiving overnight anomalies and December holes. |
| 4 / W4 | 2026-04-22–10-06 | 120 | 11/92/17 | 4 / 961 | 0 | 1 | 5 / 7 | 13 | Few sparse dates, but May 25 is degraded and specific 2026 hours remain unresolved. |
| 5 / W5 | 2023-07-10–12-22 | 120 | 0/86/34 | 11 / 716 | 0 | 0 | 14 / 0 | 22 | More distinct one-minute investigations and holiday anomalies. |
| 6 / W6 | 2026-02-20–09-17 | 150 | 4/119/27 | 7 / 1,434 | 0 | 4 | 6 / 9 | 19 | Potential 150-session span, with provider, holiday, and April 3 schedule work. |
| 7 / W7 | 2022-01-05–06-22 | 120 | 0/93/27 | 8 / 964 | 1 | 0 | 14 / 0 | 18 | Includes the experimentally inspected February 16 minute, plus more holiday work. |

All windows have **zero currently usable 120-session A/B runs**. Their stated lengths are upper bounds if every observed and intervening date, RV support, and existing eligibility gate clears. A failed date splits the run; dropping it does not preserve 120 consecutive sessions. W6's 150 observed rows may offer room to select a later 120-session subspan after evidence review, but no gap may be bridged by row deletion.

### Best first window: W1

The seven sparse sessions are 2022-06-20, 07-04, 07-27, 08-16, 08-18, 09-05, and 10-13. June 20, July 4, and September 5 contribute **240 provisional absent minutes each**. The other four dates contribute **one minute each**, for **724** total. The exact UTC intervals and raw `NQU2`/`NQZ2` symbols are in `missing_minute_intervals` and W1's `cost_estimation_scopes` in the manifest. None of these four one-minute gaps inherits the February 16 no-trade classification. W1 has **15 guarded dates**, **105 provisional regular-calendar dates**, **20 incomplete causal decisions**, no provider flag, and no unobserved weekday candidate. The preceding trade session for June 7 also needs causal-volume review.

W2 has five fewer C rows and five fewer incomplete rolls, but its April 15 unobserved weekday can interrupt the entire span. W4 has the fewest sparse dates, yet its 2026 holiday schedule and degraded May 25 source make the apparent 961-minute shortfall harder to adjudicate. These judgments reflect evidence workload, not a measured success probability.

## Five-minute RV experiment check

The isolated February 16 test uses retained raw `NQH2` bars from 04:40–04:49 UTC and a provider-stream no-trade observation for `[04:47, 04:48)`. The actual **04:40 open is 14557.25** and **04:44 close is 14557.25**. Therefore the first five-minute block is `log(14557.25 / 14557.25)^2 = 0`, using the first bar's **open** as reference. The second block starts at the prior block's 04:44 close, not the 04:45 open or the carried 04:47 price; its 04:49 endpoint is 14559.00. Its contribution is `log(14559.00 / 14557.25)^2 = 1.4449912269940095e-08`, which is the reported ten-minute RV5. The 04:47 carried sample is 14558.25 and has zero one-minute return; the 04:48 observed return is still measured from that price. The [experiment implementation](../backtester/nq_clock_experiment.py) and [independent arithmetic test](../tests/test_nq_clock_experiment.py) use this same reference rule. This verifies the local calculation, not full-session RV or a tier promotion.

## Databento estimate scopes and evidence sequence

The manifest gives an **estimate-only** scope per affected session: `GLBX.MDP3`, `stype_in=raw_symbol`, the retained raw symbol, one `trades` interval per provisional missing run, and a `status` context from the provisional session open through its last gap. These are request parameters to price after dated CME review, not requests sent or new quotations. For holiday-pattern 240-minute runs, obtain the dated NQ close/reopen grid first; estimate trades only for minutes still scheduled active. For the short gaps, preserve the interval, nearby retained OHLCV, instrument identity, provider condition/revision, response completeness, and returned response hashes. If several gaps share a session, compare separate narrow trade estimates with a combined session scope; provider minimum billing granularity can make interval sums misleading. The saved February 16 estimate was **$0.000114440918** for one-minute trades plus session-to-gap status, but it is account- and scope-specific and is **not** extrapolated to these windows. No new paid retrieval or cost-estimate API call was made.

The completed February 16 trade/status response found zero returned trades and an active carried trading state for its one minute. It supports a limited provider-stream clock-price experiment, not exchange-wide completeness or classification of any other interval. To make W1 eligible, collect dated CME NQ open/pause/close and trade-date evidence for all 120 observed dates and any intervening closure; establish whether its 720 holiday-pattern minutes are truly outside the scheduled grid; obtain independent trade/status/completeness or exchange evidence for the four ordinary missing minutes and any holiday minutes that remain active; prove complete prior-session eligible-contract volumes and roll choices, including the boundary predecessor; then perform an isolated, versioned recertification with unchanged A/B and strict gates and verify full-session matched RV support. Only if all 120 consecutive sessions pass the existing A/B rule could the prespecified exploratory HAR study proceed. Strict historical HAR still requires its Tier A gate and the longer design floor.
