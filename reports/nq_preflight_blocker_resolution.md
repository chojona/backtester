# NQ preflight blocker resolution — 2026-10-14

Baseline: `reports/research_preflight_audit.md`. Decision: **strict HAR remains NO-GO**.
No HAR fit, paid data request, threshold change, or session promotion occurred.

## BPV consistency

The frozen estimator is `bpv-segment-v1.0.0`, specified in `docs/VOLATILITY.md`.
Both streaming and historical derived BPV exclude the Overnight→RTH and
RTH→Post-RTH adjacent-return products. The earlier historical CSV uses
`bpv-all-adjacent-v0.0.0` and remains unchanged. The new derived CSV and
manifest are under `results/databento-nq-full-history/bpv-segment-v1.0.0/`.
All 1,200 legacy rows reproduced the prior RV and BPV from the retained
consolidated bars before recalculation. All 1,200 BPVs changed. The original CSV
SHA-256 is `c21a648087055aa65efce95b446ff4ac7b5c2e508ded10586dafab91e1ebf010`;
the versioned CSV SHA-256 is
`683cebbf646884cf9977dbd9b763093b968267e64e6032063608d76927119be3`.
A second rebuild returned the same output hash. The source parquet SHA-256 stayed
`16a626bf24c90a73a176e4a21138f58c40e3a5c35ae70a57643c3f1878f94c44`.

## Calendar and source evidence

The 56 unobserved weekday candidates were individually enumerated in
`reports/nq-certification-blockers/all-56-unobserved-weekdays.csv`, with their
nearby retained provider conditions and observed neighboring bar counts. None
was inferred to be closed from OHLCV silence. Five ordinary-regime 2014 dates
(June 12–13 and September 23–25) overlap `degraded` UTC-day provider conditions;
the adjacent observed dates also show degraded metadata. The five remain
**possible provider gaps**, with no retained independent trade or status feed to
prove minute-level loss or exchange-open status. The other 51 require dated CME
holiday or exception evidence before their absence can be classified.

CME's [2012 equity-index hours diagram](https://www.cmegroup.com/content/dam/cmegroup/education/files/eq-trading-hours.pdf)
and [SER-6465](https://www.cmegroup.com/rulebook/files/ser-6465_Equity_Index_Futures_Options_on_Equity_Index_Futures_20121114.pdf)
support a concrete pre-2012 correction: on ordinary Monday–Thursday dates,
16:30–17:30 ET trades belonged to the **next** trade date, whereas the retained
parquet assigns them to the current date. The isolated mapping function and
boundary tests implement that rule. Scanning the retained parquet found 24,601
rows with a different ordinary trade date among 873,296 pre-transition rows;
12 additional rows fall outside ordinary hours and require individual review.
The original parquet and selected-contract results were not rewritten. A dated
holiday/exception calendar and versioned selected-contract rebuild are needed
before recertifying the 635 pre-2012 Tier C dates.

The [CME 2015 close notice](https://www.cmegroup.com/tools-information/lookups/advisories/electronic-trading/20150824.html)
and [2021 pause notice](https://www.cmegroup.com/notices/electronic-trading/2021/06/20210621.html)
support the ordinary regimes already in the registry, but those notices do not
provide day-by-day exceptions for 2010–2026. CME's current
[holiday-hours page](https://www.cmegroup.com/trading-hours.html) exposes current
windows, not a verified complete historical NQ event register. No unsupported
historical exception was added.

## Certification before and after

| Tier | Before | After evidence audit | Primary unresolved issue |
|---|---:|---:|---|
| A | 11 | 11 | Already strict |
| B | 1,336 | 1,336 | Individual dated CME schedule and exception evidence |
| C | 2,858 | 2,858 | Trade-date, holiday, causal roll, coverage, or provider evidence |
| D | 2 | 2 | Initial buffer and non-session preopen artifact |

`reports/nq-certification-blockers/all-excluded-and-provisional-sessions.csv`
records every B/C/D date and **every failed strict gate**, including overlapping
calendar, provider, contract, and coverage failures. Primary C reasons are:
1,527 incomplete prior-session contract evidence (1,273 also have sparse or
off-schedule coverage); 635 pre-2012 mapping; 489 guarded holidays/early closes;
159 sparse or off-schedule coverage with otherwise present causal contract
evidence; 34 degraded or missing provider metadata; and 14 unresolved 2026
holiday hours. These reason counts are mutually exclusive by priority, but the
gate columns show the overlapping blockers.

The pre-2012 date assignment is a **fixable implementation defect** whose
ordinary rule is now defined, but rebuilding its downstream contract selection
and validating exceptions remain required. Provisional holiday guards are a
conservative evidence policy, not proof of closure. Degraded provider conditions,
unknown no-trade versus missing intervals, and incomplete prior-session volume
are **data or source-evidence problems**. A full active OHLCV grid on Tier B
dates is insufficient to prove the exchange's dated schedule or provider
completeness. No B or C row was promoted automatically.

Strict Tier A remains 11 sessions, split into segments of 10 and 1. The longest
uninterrupted strict sequence is September 14–25, 2026 (10 sessions). It cannot
support a 22-session HAR lag window. `comparison.json` contains the input
decision and missing-date hashes and the before/after counts.

## Final checks

- Complete offline suite: **301 passed, 1 live test deselected**.
- Independent mathematical validation: **27 passed**.
- Independent 4,207-date history verifier: **PASS_WITH_EXPLICIT_EXCLUSIONS**;
  67 raw chunks, 7,301,216 raw rows, 516,400 exact duplicates, zero conflicting
  duplicates, and 6,784,816 consolidated rows. Original Phase 3 decision hash
  remains `8f539c28a437f5e13266f15ad048cb11f87ccd51d13cdcaa3dac59eb8c23d40c`.
- Independent strict-day arithmetic still matches streaming segment-aware BPV;
  the retained legacy BPV differs by the two boundary products.
- The new BPV CSV was rebuilt twice with the same SHA-256, while both retained
  source and original historical CSV hashes stayed fixed.

## Blocking evidence

Strict recertification beyond 11 dates needs a reviewed dated CME NQ
open/pause/close and holiday-event record, plus independent provider/trade-status
evidence where retained OHLCV is absent, degraded, or sparse. The five 2014
candidate gaps and minute-level provider completeness cannot be resolved from
the retained OHLCV and daily condition flags. Assuming regular hours on all
provisional dates, or treating silent minutes as exchange closures, would be an
unsupported historical assumption. Work stops at that evidence boundary.
