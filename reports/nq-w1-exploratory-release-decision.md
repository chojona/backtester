# NQ W1 conditional exploratory dataset release decision

**Decision, 2026-10-15: GO for separately versioned, assumption-dependent model development.** This approval covers the 120-date conditional path in [`nq-w1-exploratory-v1.0.0`](../results/nq-w1-exploratory-v1.0.0/manifest.json). It does not establish strict causal validity, point-in-time historical availability, exchange-wide completeness, or any trading alpha. No HAR model was fit. The existing NO-GO candidate, original preregistration, production selector, and historical certification tiers remain unchanged.

## Contract selection and affected calculations

The independent retrospective provider-stream replay supports **110/120** front-three winners. They are labeled `provider_supported_retrospective_winner`, subject to provider completeness, and never labeled observed or certified. Ten predecessor electronic-volume cells remain `null` and their winners remain unresolved. For those ten target dates, this release **assumes** the existing selected contract as a conditional calculation path; it does not fill an unknown volume or promote a winner. A later cleared-volume statistic is not an electronic-volume substitute. The frozen descending `(volume, contract code)` tie rule means equality with the known leader leaves that leader ahead; the exact first integer reversal levels are retained below and in [`winner-uncertainty.json`](../results/nq-w1-exploratory-v1.0.0/winner-uncertainty.json).

| Assumed path date | Assumed contract | Unknown competitor | First reversal volume | Affected 23-date target windows |
| --- | --- | --- | ---: | --- |
| Jul 5 | NQU22 | NQH23 | 601,349 | Jul 6–Aug 4 (22) |
| Jul 6 | NQU22 | NQH23 | 783,860 | Jul 6–Aug 5 (23) |
| Jul 7 | NQU22 | NQH23 | 641,911 | Jul 7–Aug 8 (23) |
| Jul 8 | NQU22 | NQH23 | 539,084 | Jul 8–Aug 9 (23) |
| Jul 11 | NQU22 | NQH23 | 630,491 | Jul 11–Aug 10 (23) |
| Jul 14 | NQU22 | NQH23 | 728,826 | Jul 14–Aug 15 (23) |
| Sep 19 | NQZ22 | NQM23 | 740,190 | Sep 19–Oct 19 (23) |
| Sep 23 | NQZ22 | NQM23 | 780,903 | Sep 23–Oct 25 (23) |
| Oct 28 | NQZ22 | NQM23 | 761,968 | Oct 28–Nov 21 (17) |
| Nov 9 | NQZ22 | NQM23 | 717,994 | Nov 9–Nov 21 (9) |

**All six daily measures** on each of those ten paths—RV1, RV5, RV15, positive and negative semivariance, and BPV—depend on the assumed selected contract. A winner reversal would require new minute paths and new values; the table's levels are sensitivities, not upper bounds or estimates. The union is **73 of 98** potential 23-date feature/target windows. [`har-window-impact.json`](../results/nq-w1-exploratory-v1.0.0/har-window-impact.json) lists all 98 windows, their exact 22 feature dates and target date, and every selector and calendar assumption each window inherits. These are chronology and impact records, not fitted HAR rows.

## Calendar and clock

The nine original provisional dates—Jun 22, Jul 6, Sep 7, Oct 10–12, and Nov 9–11—retain their `provisional` evidence flags and historical reasons. This release applies a **versioned assumed ordinary-hours path** to them. The four retained CME holiday workbooks continue to govern the documented combined Tuesday sessions. An independent chronology check found 123 civil weekdays from Jun 2 through Nov 21, removed only the three documented combined-date Mondays (Jun 20, Jul 4, Sep 5), and matched all **120** candidate trade dates in order. No date was dropped, inserted, or bridged. The ordinary-hours assumption does not clear strict calendar certification.

The five proposed provider no-trade clock minutes are finalized for this **provider-stream exploratory clock**: Jun 6, Jul 27, Aug 16, Aug 18, and Oct 13. The preserved verifier reopened the ten paired trade/status responses and checked source hashes, symbols, bounds, zero trades, and active trading/quoting status. Each minute carries the last observed price with zero return; its following observed return keeps the real price move. The full grid has **169,015 observed trade minutes plus five provider-supported no-trade minutes = 169,020** classified active minutes. RV1, RV5, RV15, semivariance, and BPV use the frozen continuous return reference, research-segment block anchors, and within-segment BPV pairs. Coverage matches at one, five, and fifteen minutes: **33,804** complete RV5 blocks and **11,268** complete RV15 blocks. On every date RV1 equals the two semivariances within `1e-15`, all estimators are finite and nonnegative, and no unknown clock minute was used. These are conditional selected-path values, not exchange-certified daily targets.

## Finalization and execution timing

The accepted exploratory timing assumption is a completed predecessor observation cutoff at its active close, finalization **45 minutes later**, and selection at that finalization deadline (ordinarily **17:45 ET**). The earliest target execution is its first active instant (ordinarily **18:00 ET**). Every one of the 120 replayed deadlines precedes its target open; the smallest buffer is 15 minutes. Weekend and combined-holiday transitions have a 2,895-minute buffer; the fall daylight-saving weekend has 2,955 minutes. The dated UTC timestamps are in [`daily-series.json`](../results/nq-w1-exploratory-v1.0.0/daily-series.json). Historical publication and revision timestamps are absent, so the 45-minute availability premise is explicitly `assumed` on every date. The timing calculations must be replayed if a provisional calendar boundary changes.

Under a **one-completed-session availability lag**, the immediately preceding final volume misses the target opening for **120/120** decisions. The frozen selector therefore fails that stress scenario. No older predecessor is substituted. This failure remains visible in the manifest and each daily record.

## Release contents and controls

The immutable version directory contains [`daily-series.json`](../results/nq-w1-exploratory-v1.0.0/daily-series.json) with 120 identities, assumed selected paths, uncertainty flags, daily estimators, minute coverage, timing, and the **22/50/20/28** split; [`minute-classifications.csv.gz`](../results/nq-w1-exploratory-v1.0.0/minute-classifications.csv.gz) with every observed or provider-supported minute; winner sensitivities; window impact; [`manifest.json`](../results/nq-w1-exploratory-v1.0.0/manifest.json) with input and output SHA-256 maps; and [`SHA256SUMS`](../results/nq-w1-exploratory-v1.0.0/SHA256SUMS). Labels distinguish `observed` trade bars, `provider_supported` retrospective evidence and no-trade samples, `assumed` paths/calendar/availability, and `unresolved` electronic-volume and strict-certification evidence. The release builder refuses to overwrite an existing version.

The builder verified every source and output hash of the prior candidate, its SHA256SUMS, 120 daily records, all 169,020 minute classifications, estimator identities, split counts, and the 98-window chronology before writing. Reproduction: `.venv/bin/python -m scripts.release_nq_w1_exploratory`; run only with a new version name if this directory already exists. Verify the current seal with `cd results/nq-w1-exploratory-v1.0.0 && shasum -a 256 -c SHA256SUMS`. Source raw responses and the release directory are Git-ignored workspace artifacts; preserve them together. Any failed arithmetic, chronology, or scenario-consistency assertion prevents a new version and leaves the prior NO-GO ledger intact.
