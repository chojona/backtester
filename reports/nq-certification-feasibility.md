# NQ certification feasibility — targeted windows

Date: 2026-10-14 (America/New_York). Decision: **start with 2022-01-05 through 2022-12-23; strict HAR remains NO-GO.** This is a feasibility ranking, not a certification decision. No session is promoted, no gate is relaxed, and no historical acceptance or HAR result is changed.

## Population and decision rule

The analysis covers **all 4,207 observed trading dates** in [`certification-by-session.csv`](../results/databento-nq-full-history/phase3-v3.0.0/certification-by-session.csv), from 2010-06-07 through 2026-10-06. The complete date-level failure ledger is [`all-excluded-and-provisional-sessions.csv`](nq-certification-blockers/all-excluded-and-provisional-sessions.csv): it lists every failed strict gate for the 4,196 non-A dates. The other 11 dates are Tier A and have no failed gate. The decision file's SHA-256 is `8f539c28a437f5e13266f15ad048cb11f87ccd51d13cdcaa3dac59eb8c23d40c`; its counts are A=11, B=1,336, C=2,858, D=2. Gate counts below **overlap** and must not be added as if they were independent sessions.

| Strict gate | Failed observed dates | Meaning of failure |
|---|---:|---|
| Calendar | 4,196 | 3,052 provisional regular-regime dates, 492 holiday-guard dates, 15 specific unresolved 2026 holiday-hour dates, 636 pre-2012 mapping dates, and one non-session preopen artifact. These are registry states, not proven CME closures. |
| Provider | 35 | 34 degraded and one missing-condition-metadata date. The remaining 4,172 have available or revised-available daily metadata; that metadata alone does not prove minute completeness. |
| Causal contract | 2,054 | 2,053 incomplete prior-session volume decisions and one initial date without a prior-session buffer. An incomplete decision often follows a guarded or sparse prior date; it is not necessarily a separate bad data event. |
| Selected-contract coverage | 2,372 | 1,735 sparse or off-schedule dates plus 637 without a resolved trade-date grid (including the pre-2012 group). A missing trade minute alone does not establish provider loss. |

The primary C reason codes are 1,527 incomplete causal-contract decisions, 635 pre-2012 remaps, 489 holiday or early-close guards, 159 sparse/off-schedule grids, 34 provider conditions, and 14 unresolved 2026 holiday-hour cases. Reason codes are assigned by priority; the failure ledger records the other simultaneous failures. The two D dates are the 2010-06-07 initial buffer and the 2018-08-05 Sunday preopen artifact. The 56 unobserved weekday candidates are audited separately in [`all-56-unobserved-weekdays.csv`](nq-certification-blockers/all-56-unobserved-weekdays.csv). **The authoritative number of expected or missing CME sessions is unknown.** Five 2014 dates are possible provider gaps; none of the ten selected windows contains them.

## Search and ranking

For each target size (252, 504, 778), I scanned every consecutive block of that many **observed rows** in date order (3,956, 3,704, and 3,430 blocks respectively). I counted unobserved weekdays between the endpoints, all four failed gates, and the reason-code overlaps. Nearby rolling windows with essentially the same blockers were collapsed into representative candidates. The ranking first favors a smaller evidence campaign, then weighs unobserved weekdays, degraded provider days, sparse grids, unresolved roll predecessors, and calendar review as separate workload and success risks. It is a judgmental effort ranking, not a measured probability or a bar-count sort. Existing bars and Tier B counts are not treated as proof of certifiability. The 252/504/778 sizes are planning targets; **none is yet a proven contiguous sequence of CME trading sessions**. Each unobserved weekday requires a dated exchange determination, and an open date would require source bars or a revised window.

In the tables, **G/H** means observed holiday-guard / specific unresolved 2026 holiday-hour dates; a guard includes adjacent dates and is not a count of actual exchange exceptions. **P** is degraded or missing provider metadata; **S** is a sparse/off-schedule selected-contract grid; **R** is incomplete prior-session contract evidence. **Switches** are selected-contract changes within the window, not the count of bad roll decisions. All ten windows have **zero pre-2012 dates and zero pre-2012 mapping dependencies**.

| Rank | Target | Inclusive observed endpoints | Observed | Unobserved weekdays* | Current A/B/C/D | G/H | P | S | R | Switches | Effort / success outlook |
|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| 1 | 252 | 2022-01-05–2022-12-23 | 252 | 1 | 0/192/60/0 | 32/0 | 0 | 18 | 41 | 4 | Lowest relative effort; best first test, conditional on CME and gap evidence |
| 2 | 252 | 2025-10-16–2026-10-06 | 252 | 2 | 11/184/57/0 | 22/15 | 5 | 14 | 43 | 4 | Good grids and 11 A dates; provider/2026 holiday evidence adds risk |
| 3 | 252 | 2021-09-14–2022-09-02 | 252 | 2 | 0/180/72/0 | 33/0 | 2 | 23 | 50 | 3 | Moderate; two degraded dates and more causal predecessors |
| 4 | 252 | 2021-01-05–2021-12-22 | 252 | 0 | 0/171/81/0 | 33/0 | 1 | 32 | 54 | 4 | No weekday absence, but more sparse and roll failures |
| 5 | 504 | 2021-01-04–2022-12-12 | 504 | 2 | 0/359/145/0 | 67/0 | 2 | 50 | 100 | 7 | Best two-year candidate; substantial incremental evidence |
| 6 | 504 | 2022-01-06–2023-12-15 | 504 | 3 | 0/352/152/0 | 70/0 | 0 | 59 | 104 | 8 | No flagged provider days, but more gaps and sparse grids |
| 7 | 504 | 2024-10-24–2026-10-06 | 504 | 5 | 11/348/145/0 | 65/15 | 9 | 43 | 105 | 8 | Many full grids; provider and 2026 holiday proof is harder |
| 8 | 778 | 2020-04-02–2023-04-05 | 778 | 7 | 0/543/235/0 | 111/0 | 7 | 83 | 163 | 12 | Lowest estimated three-year effort, still a major evidence project |
| 9 | 778 | 2021-04-06–2024-04-08 | 778 | 7 | 0/529/249/0 | 112/0 | 2 | 92 | 171 | 12 | Fewer provider flags than rank 8; more coverage/roll work |
| 10 | 778 | 2023-10-03–2026-10-06 | 778 | 8 | 11/523/244/0 | 107/15 | 11 | 80 | 173 | 12 | Most provider and 2026-specific uncertainty of these three-year candidates |

\*Unobserved **weekday candidates**, not established missing expected trading sessions. Within rank order their dates are: (1) 2022-04-15; (2) 2025-12-25, 2026-01-01; (3) 2021-12-24, 2022-04-15; (4) none; (5) 2021-12-24, 2022-04-15; (6) 2022-04-15, 2022-12-26, 2023-01-02; (7) 2024-12-25, 2025-01-01, 2025-04-18, 2025-12-25, 2026-01-01; (8) 2020-04-10, 2020-12-25, 2021-01-01, 2021-12-24, 2022-04-15, 2022-12-26, 2023-01-02; (9) 2021-12-24, 2022-04-15, 2022-12-26, 2023-01-02, 2023-12-25, 2024-01-01, 2024-03-29; (10) 2023-12-25, 2024-01-01, 2024-03-29, 2024-12-25, 2025-01-01, 2025-04-18, 2025-12-25, 2026-01-01.

### Recoverability and external evidence exposure

This partition is mutually exclusive **within each observed window**. “Calendar-first” means an available provider condition, full selected-contract grid, and usable prior volume: those dates are plausible promotions **only after dated CME review**. “Roll-only” has the same provider/grid conditions but incomplete causal-contract evidence; many may clear by re-evaluating the retained prior day after calendar review. “Source/coverage” has a degraded provider flag or a sparse/off-schedule grid and needs a dated explanation; the subset needing outside provider/trade-status records cannot be determined from OHLCV silence alone. Already-A dates are shown separately. These are conditional workload groups, **not proposed tier changes**.

| Rank | Already A | Calendar-first | Roll-only | Source/coverage | Flagged provider dates |
|---:|---:|---:|---:|---:|---|
| 1 | 0 | 196 | 38 | 18 | None |
| 2 | 11 | 190 | 35 | 16 | 2025-11-28; 2026-03-16–17, 04-10, 05-25 |
| 3 | 0 | 185 | 42 | 25 | 2021-12-06; 2022-01-03 |
| 4 | 0 | 174 | 45 | 33 | 2021-12-06 |
| 5 | 0 | 367 | 85 | 52 | 2021-12-06; 2022-01-03 |
| 6 | 0 | 359 | 86 | 59 | None |
| 7 | 11 | 361 | 83 | 49 | 2025-09-17–18, 09-24–25, 11-28; 2026-03-16–17, 04-10, 05-25 |
| 8 | 0 | 556 | 134 | 88 | 2020-05-05–06, 06-30–07-02; 2021-12-06; 2022-01-03 |
| 9 | 0 | 543 | 141 | 94 | 2021-12-06; 2022-01-03 |
| 10 | 11 | 544 | 136 | 87 | 2024-09-18–19; 2025-09-17–18, 09-24–25, 11-28; 2026-03-16–17, 04-10, 05-25 |

The source/coverage group is a **conservative external-evidence exposure**, not proof of irrecoverable data. An exchange-verified early close could explain some sparse grids; an ordinary one-minute hole may instead require provider-level records. Conversely, the calendar-first group is not locally certifiable because its dated CME exceptions remain unreviewed. The roll-only count can include a boundary date whose predecessor lies just outside the reported window; that predecessor must be audited before the first date can become strict.

## Recommended first window: 2022-01-05–2022-12-23

This candidate has 252 observed dates, 192 B and 60 C, **no degraded provider condition**, no off-schedule selected minute, and one unobserved weekday candidate (2022-04-15). Its 18 sparse dates contain a total of 1,920 minutes absent from the provisional ordinary grid. The shortfall is concentrated in several 1,140/1,380-minute holiday candidates, while ordinary-regime dates also have one- or two-minute holes. None can be classified solely from the bars. The dates needing direct coverage adjudication are **2022-01-17, 02-16, 02-21, 04-08, 05-26, 05-30, 06-06, 06-20, 07-04, 07-27, 08-16, 08-18, 09-05, 10-13, 11-24, 11-25, 12-13, and 12-22**.

The 41 incomplete contract decisions are not 41 independent roll gaps. Among the 38 full-grid, good-provider roll-only dates, 28 follow a conservatively guarded date, nine follow a sparse date, and one is the window's first date whose prior session is outside the window. Four selected-contract switches occur inside. This makes prior-day evidence review a tractable next step, but the existing logic cannot infer a causal roll from the selected contract alone.

### Evidence needed before any recertification

1. **Dated CME NQ session schedule** for every observed and intervening weekday in the window: open, pause, close, early close, holiday closure, reopening, and trade-date assignment in ET. Resolve all 32 guarded observed dates and 2022-04-15. Preserve source URLs/documents, effective dates, retrieval metadata, and the resulting expected-minute grid per trade date. A generic holiday rule or today's schedule is insufficient.
2. **Minute-level source adjudication** for the 18 sparse dates. Compare each absent minute with the dated CME grid; for minutes expected to trade, obtain independent provider completeness/trade-status or exchange records that distinguish no trade, halt, and missing delivery. Preserve the provider's condition/revision history and the raw-chunk and consolidated-parquet hashes. Do not fill or silently discard missing intervals.
3. **Causal contract selection proof** for all 252 dates and the immediately preceding trade session. Retain complete prior-session volume for eligible NQ expiries, the comparison and tie rule at each of the four roll switches, and any source revision. Re-evaluate the 28 guard-propagated and nine sparse-predecessor roll-only cases after those predecessors are resolved; investigate any remaining incomplete decision with provider records.
4. **Versioned, independently checked recertification** only after the source packet exists. Rebuild expected grids and selected-contract decisions into a new isolated version; compare every session's four strict gates and ensure all authoritative expected trading dates are present, including any newly verified open weekday. Reconcile raw/chunk/derived hashes and keep the current Phase 3 decisions intact for audit. A candidate passes only if every expected session in the intended span is Tier A under the existing gates and the 252-session count remains valid after holiday adjudication.

If 2022-04-15 was an exchange-open date without recoverable bars, or any ordinary missing minute lacks adequate independent status/completeness evidence, **this 252-session span is blocked**. Move the start/end to a newly scored neighboring window; do not bridge the gap. Once the first window is resolved, the 504-session 2021–2022 candidate is the next staged target, followed by a freshly rescored 778-session candidate.

## Local work versus records that must come from outside

**Local and retained-evidence work:** enumerate all failed gates; reproduce hashes; implement and validate the already specified pre-2012 ordinary trade-date mapping in an isolated future rebuild; derive versioned candidate grids from *documented* CME exceptions; rerun causal prior-volume comparisons using retained raw bars; trace roll-only failures to guarded/sparse predecessors; check raw duplicates, selected-minute coverage, and estimator version (`bpv-segment-v1.0.0`). These actions can diagnose or remove implementation and propagation defects but cannot certify an undocumented exchange event or unexplained empty interval.

**External CME evidence:** date-specific NQ hours and event notices for each candidate span, including holidays, early closes, pauses, exceptional reopenings, and whether an unobserved weekday was a trading date. **External provider or exchange trade-status evidence:** degraded/missing provider-condition days; ordinary expected minutes without OHLCV; possible provider gaps; incomplete prior-session volume when the retained eligible-contract book cannot prove the decision. No paid data request is made here.

Pre-2012 windows are currently poor first candidates: 636 observed dates have unresolved pre-2012 calendar mapping (635 C and the initial D). The retained audit identified 24,601 ordinary rows needing a trade-date change and 12 off-hours rows needing exception review. Code can apply the ordinary mapping, but dated CME exceptions, a versioned selected-contract rebuild, and earlier causal history for the first date remain dependencies. This is why all ten ranked windows start after 2012; **their pre-2012 dependency count is zero**.

## Boundary of this decision

The ranking estimates work from current gate outcomes; it is not a probability of success. Sparse-bar causes, authoritative expected-session counts, and provider completeness cannot be inferred from the retained OHLCV and daily condition flags. The first evidence packet should be assessed against the existing strict gates before funding or performing a larger historical campaign. Until a fully contiguous Tier A window is independently verified, strict HAR remains **NO-GO**.
