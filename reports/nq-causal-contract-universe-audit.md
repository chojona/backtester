# NQ causal contract universe and roll audit

**Audit date:** 2026-10-14 (America/New_York)
**Scope:** 120 retained-panel CME trade dates, 2022-06-02 through 2022-11-21, with the corrected June 1 and holiday trade-date predecessors.
**Disposition:** **NO-GO** for using this proposed universe with the present evidence in a separately preregistered exploratory HAR experiment. This is an audit and a candidate rule, not a recertification or a fitted model. The date-level replay is in [`nq-causal-contract-universe-audit.json`](../results/nq-causal-contract-universe-audit.json).

## Finding

The existing historical selector is **not strictly causal at the forecast origin**. It uses the prior observed trade date's retained volume to rank, but first admits only contracts with at least one **current trade-date** OHLCV bar. Current-day presence is learned after the target session starts. A missing current-day bar can mean no trade, incomplete acquisition, or a contract absent from the requested symbol set; it is not a listing test. The rule therefore conditions the candidate set on future observation, even though the volume used for ranking is lagged.

The corrected retained-panel replay has **zero changed known winners** in 120 decisions. That does not establish the winner over the full eligible NQ outright universe. The 2022 CME listing rule yields nine expected outrights per target date, while the local acquisition requested three nearby raw symbols per chunk. Across the 120 dates, 328 of 1,080 eligible contract/date cells have a positive retained predecessor volume; **752 have unknown predecessor volume**. Every decision has six or seven unknown candidates, so **zero full-universe winners are determined**. Observed volumes are lower bounds until source completeness is independently shown.

## Existing rule, exactly

1. [`scripts/prepare_nq_history.py`](../scripts/prepare_nq_history.py:46) chooses the first three quarterly raw symbols whose calculated expiry spans each request chunk, including overlap. The request is neither a full exchange listing roster nor a point-in-time security-definition snapshot. The local 2022 chunks requested `NQM2/NQU2/NQZ2`, then `NQU2/NQZ2/NQH3`, then `NQZ2/NQH3/NQM3`.
2. [`scripts/accept_nq_history.py`](../scripts/accept_nq_history.py:57) accepts definitions only for matching quarterly `NQ` futures, XCME, USD, no legs, and maps their raw symbol and expiration to a contract code. It retains positive-volume one-minute OHLCV observations. At each observed trade date, [`current_contracts`](../scripts/accept_nq_history.py:194) is the set with at least one retained bar **that day**. On the first observed date it selects the nearest expiration among that set, provisionally. Thereafter it selects `max(current_contracts, key=(previous observed date's summed volume, contract code))`; missing prior volume is treated as **zero**. If the prior leader disappears today, the next highest prior-volume contract that is present today wins. The actual equal-volume tie rule selects the **lexicographically largest** code.
3. The acceptance stage's current-day volume creates `current_contracts` through positive OHLCV presence and is also accumulated for **tomorrow's** decision. Its magnitude does not directly rank today's winner. After selection, current-day selected bars drive paired roll evidence, coverage, and volatility measurements. Those are downstream of the decision.
4. The corrected W1 replays repeat the same membership condition in [`scripts/build_nq_w1_holiday_candidate.py`](../scripts/build_nq_w1_holiday_candidate.py:65) and [`scripts/build_nq_w1_120_candidate.py`](../scripts/build_nq_w1_120_candidate.py:80). They combine the retained Monday-labeled holiday portions into Tuesday CME trade dates, sum their volumes, enumerate contracts with bars on the target date, and rank by the previous completed corrected trade date. Their displayed rank breaks equal volumes by **ascending** code, whereas `max(volume, code)` selects descending code; this only matters on a tie. Their `current_volume` fields are diagnostics, not ranking inputs. The Phase 3 certification script consumes the historical selected contract; it does not create a separate full-universe selector. [`backtester/rolls.py`](../backtester/rolls.py:58) implements a distinct online continuous-series policy and is not the historical NQ acceptance selector audited here.

## Listing eligibility and causal alternative

CME's [April 26, 2022 SER-8975](https://www.cmegroup.com/notices/ser/2022/04/SER-8975.pdf) and [April 25 Globex notice](https://www.cmegroup.com/notices/electronic-trading/2022/04/20220425.html) announced that, effective trade date **May 23, 2022**, NQ futures would list **five consecutive March-cycle quarters plus four additional December contract months**. The historical [CME NQ specification](https://www.cmegroup.com/trading/equity-index/files/emini-nasdaq-100-futures-options.pdf) places last trading at 8:30 a.m. CT on the third Friday of the contract month. These dated rules make a deterministic **expected** nine-contract roster possible before each target session. For June 14 it is `NQM22, NQU22, NQZ22, NQH23, NQM23, NQZ23, NQZ24, NQZ25, NQZ26`; for September 13 it is `NQU22, NQZ22, NQH23, NQM23, NQU23, NQZ23, NQZ24, NQZ25, NQZ26`.

For a new, separately versioned study, freeze at the completed prior CME trade-date close: (a) the dated exchange listing notice and an as-of instrument-definition snapshot confirming the outright roster, activation, expiration, and any exceptional delisting; (b) the next trade date and its known listing-cycle transition; and (c) complete, available **prior** trade-date volume for every eligible outright. Rank by descending prior volume, preserving the existing `max(volume, contract code)` tie rule. Treat absent or unverified prior volume as **unknown**, not zero. If an eligible candidate has unknown volume, the winner is unresolved unless an independently certified upper bound proves it cannot win. If the chosen contract has no target-session bar, mark that target unusable under a frozen coverage rule; do not substitute a contract after seeing target activity. This defines a causal selection policy, but the current retained data do not satisfy its inputs.

A listing rule supplies eligibility independently of whether a contract traded in a minute or a whole session. The local definition files contain only the three requested symbols for each chunk, and their retrospective `activation` and `expiration` fields do not prove that a complete nine-contract security-definition book was available to this research process at every historical origin. A complete dated definition book, or equivalent exchange roster with effective timestamps, is needed to turn the rule-derived roster into an independently auditable actual roster.

## Roll transitions and 120-date comparison

| Target trade date | Completed predecessor | Retained known volumes | Known-roster winner | Full-roster status |
| --- | --- | --- | --- | --- |
| 2022-06-14 | 2022-06-13 | NQU22 **610,767**; NQM22 **387,941**; NQZ22 **268** | NQU22, matching historical roll; margin over NQM22 **222,826** | Six eligible contracts have unknown prior volume, including NQH23 and later December expiries. |
| 2022-09-13 | 2022-09-12 | NQZ22 **367,205**; NQU22 **313,361**; NQH23 **135** | NQZ22, matching historical roll; margin over NQU22 **53,844** | Six eligible contracts have unknown prior volume, including NQM23 and later December expiries. |

The nine-contract replay keeps each contract with a **positive retained prior volume** even if it has no bar today. It finds **0/120 known-winner changes**. There are **9 decisions** where the original current-day filter discards such a contract:

| Target date | Prior date | Eligible contract removed by target-day absence | Retained prior volume |
| --- | --- | --- | ---: |
| Jul 13 | Jul 12 | NQH23 | 13 |
| Jul 18 | Jul 15 | NQH23 | 1 |
| Jul 21 | Jul 20 | NQH23 | 5 |
| Oct 6 | Oct 5 | NQM23 | 1 |
| Oct 12 | Oct 11 | NQM23 | 5 |
| Oct 24 | Oct 21 | NQM23 | 5 |
| Oct 26 | Oct 25 | NQM23 | 1 |
| Oct 31 | Oct 28 | NQM23 | 2 |
| Nov 8 | Nov 7 | NQM23 | 1 |

The original rule also assigns zero prior volume to **11 current-day-present candidate cells** for which the retained predecessor has no bar. These are unknown-volume cases, not demonstrated zero-volume cases. Overall, the rule-derived roster has six unknown prior-volume candidates on **88** dates and seven on **32** dates. The JSON lists the roster, every known volume and bar count, every unknown contract, the nine suppressed positive-volume candidates, and the 11 zero-imputed cases date by date. Holiday-combined Tuesday sessions are treated as one predecessor session, including May 31 at the June 1 boundary and June 21, July 5, and September 6 within the run.

## Evidence required to make the universe independently auditable

1. Preserve the historically effective CME NQ listing notices and a dated full outright security-definition snapshot for each origin, including raw symbol, instrument ID, XCME outright class, activation and last-trade times, additions, removals, and revisions. Verify the May 23 expansion actually took effect. A rule-derived nine-symbol list alone cannot prove the exact active venue book on each date.
2. Obtain complete, time-stamped prior CME trade-date volume for **all nine** eligible outrights on each decision, or an official exchange total plus a feed-completeness/sequence reconciliation covering every instrument and corrected holiday trade-date segment. Show true zero volume explicitly. The three-symbol OHLCV requests cannot establish the six or seven absent candidate volumes, and sparse observed bars do not establish complete volume for included contracts.
3. Preserve publication and correction timestamps or adopt a conservative, preregistered availability lag before the forecast origin. A finalized historical volume total is not automatically a point-in-time available total.
4. Freeze a versioned candidate-universe and decision manifest, including source hashes, as-of cutoff, tie rule, unknown treatment, and no substitution after target-session observation. The existing calendar, minute-status, matched-support, and certification gates remain separate requirements for any HAR sample.

**Recommendation: NO-GO with current evidence.** The proposed roster and prior-volume policy is causally specified and suitable for a separately preregistered *audit protocol*. It should not yet select the 120-session exploratory HAR targets: all 120 complete-universe winners remain unresolved, and the existing HAR eligibility blockers remain. Reassess only after the roster, all-candidate prior volumes, and as-of availability are independently evidenced and a new sample manifest is frozen before fitting. No selector code, historical results, certification tier, or HAR fit was changed; no paid data was retrieved.
