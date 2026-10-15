# NQ front-three causal selector feasibility

**Audit date:** 2026-10-15. **Decision:** **NO-GO** for implementing an undropped 120-date exploratory continuous-futures series from the existing data. The complete date/cell evidence is in [`nq-front-three-selector-feasibility.json`](../results/nq-front-three-selector-feasibility.json). Rebuild it with `PYTHONDONTWRITEBYTECODE=1 python3 scripts/audit_nq_front_three_selector.py`. No paid retrieval, certification change, production selection change, or HAR fit was made.

## Preregistered rule examined

At each predecessor CME trade-date close, normally **5 PM New York time**, enumerate the three nearest unexpired March-cycle NQ quarterly futures under the listing rule effective May 23, 2022. Check each against the retained effective-dated definition identity, activation, and expiration. Rank the three by predecessor **electronic** volume, then by lexicographically largest contract code on an exact tie. The target trade date's bars do not determine eligibility or selection. Corrected CME predecessor segments, including the combined June 21, July 5, and September 6 holiday sessions, determine the sums. The legacy rule is replayed only for comparison.

The exploratory rank assumes that a complete, corrected `GLBX.MDP3` one-minute OHLCV response for every requested symbol and predecessor segment could have been received, summed, and available by the **5 PM ET** origin. Retained historical bars lack their original provider receipt or publication timestamps, and no feed-continuity certificate is retained. Thus every numeric electronic total is an observed lower bound and every exploratory winner is **conditional**, not strictly causally validated. A requested symbol with no bar has unknown volume; neither that absence nor a later cleared-volume value supplies an origin-available zero or upper bound. Retrospective definitions support the three expected identities on all 120 dates, but do not certify a complete as-of venue book.

## Coverage and winner comparison

| Front-three predecessor cell classification | Count |
| --- | ---: |
| Requested for every active segment, with observed volume | 328 |
| Requested for every active segment, no retained bar | 21 |
| Not requested for every active segment | 11 |
| Ineligible or not yet listed | 0 |
| **Total** | **360** |

**88/120 dates** have an observed volume for all three competitors and therefore a conditional exploratory rank. All **88 conditional winners match the legacy selected contract**; zero established differences were found. The other **32 dates are indeterminate**, so this is not a claim that the front-three series and legacy series match on all 120 dates. The June 14 conditional roll is NQU22 over NQM22 and NQZ22; the September 13 conditional roll is NQZ22 over NQU22 and NQH23. Exact volumes, source request paths, segment bounds, and timestamps are recorded per cell in the JSON.

The **11 not-requested** cells are NQH23 on June 21, 22, 23, 24, and 27, and NQM23 on September 19, 20, 21, 22, 23, and 26. The **21 requested/no-bar** cells are NQH23 on June 28, 29, 30; July 1, 5, 6, 7, 8, 11, 14, 15, 19, and 22; and NQM23 on October 7, 13, 25, 27, 28; November 1, 2, and 9. Missing bars are not assigned zero, and no later cleared-volume observation is used to rank at the predecessor close. For all 32 unresolved dates the exact gap is a missing electronic volume or an origin-available upper bound for the third competitor.

## HAR chronology

The corrected index retains the proposed **22 warmup sessions plus 50 train, 20 validation, and 28 test targets** as an arithmetic schedule. For each of the 98 potential target rows, the JSON checks the target and its preceding 22 selector dates without removing any date. **81/98 rows** contain at least one unresolved front-three selector date in that window: 35 train, 18 validation, and 28 test. Only 17 rows have a conditionally complete selector window. Independently, **65/98 rows** touch one of the five retained selected-contract minute gaps already identified by the W1 candidate; the gap check uses the legacy selected-bar grid as a retained-data diagnostic, not a newly established front-three target grid. **Zero rows** clear both checks. Dated calendar guards and origin-time availability remain additional gates.

## Recommendation

**NO-GO with existing retained data** for an exploratory implementation that preserves all 120 dates and the 22/50/20/28 chronology. The front-three rule removes most of the nine-contract unknowns but leaves 32 dates unresolved and does not establish the 5 PM ET data-availability premise. An implementable version would need complete predecessor electronic-volume evidence or defensible origin-available upper bounds for those cells, full feed/definition coverage, point-in-time availability evidence or a separately declared assumption that is scientifically acceptable for the exploratory study, and independent resolution of the minute/calendar gates. Strict certification remains separate and unchanged.

The audit reads the retained [minute Parquet](../results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet), historical OHLCV request manifests, the [corrected W1 candidate](../results/nq-w1-120-session-candidate.json), and the [definition/statistics evidence](../results/nq-definition-statistics-evidence.json). The prior [nine-contract causal audit](nq-causal-contract-selection-register.md) and legacy historical results are preserved.
