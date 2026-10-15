# NQ W1 targeted remediation plan

**Decision (2026-10-15): NO-GO with current evidence.** A separately versioned exploratory HAR study is feasible in principle after the gates below; no result is strictly causally certified. This plan makes no paid retrieval, production change, tier promotion, or HAR fit. The original [HAR preregistration](nq-har-exploratory-study-design.md) remains unchanged. Full request arguments, source hashes, and per-cell evidence are in [the JSON plan](../results/nq-w1-targeted-remediation-plan.json).

## A. The 32 frozen selector gaps

The [frozen inventory](../results/nq-front-three-selector-feasibility.json) has **11 never-requested** and **21 requested/no-bar** cells. I checked every cited raw OHLCV request manifest: the 21 requested cells are covered by completed, unpartial `GLBX.MDP3` requests and their retained DBNs, yet the frozen Parquet has no bar in these cells. The 11 others have no matching request in the inventory. No existing trade/status manifest matches these NQH3/NQM3 predecessor sessions. Later cleared-volume entries include 13 positive diagnostics, but were received after the 5 PM ET origin and are not electronic-volume or origin-time upper bounds. None of the 32 has a defensible volume or independent upper bound today.

Each row gives target date, predecessor CME trade date, exact half-open active UTC bound(s), raw symbol, and prior request class. `R` means requested/no bar; `N` means never requested. The second bound on Jun 21 and Jul 5 is part of the same CME predecessor date; the halt between bounds is excluded.

| Target | Predecessor | Active UTC bound(s) [start, end) | Raw | Class |
| --- | --- | --- | --- | --- |
| 2022-06-21 | 2022-06-17 | 2022-06-16T22:00:00Z → 2022-06-17T21:00:00Z | `NQH3` | N |
| 2022-06-22 | 2022-06-21 | 2022-06-19T22:00:00Z → 2022-06-20T17:00:00Z<br>2022-06-20T22:00:00Z → 2022-06-21T21:00:00Z | `NQH3` | N |
| 2022-06-23 | 2022-06-22 | 2022-06-21T22:00:00Z → 2022-06-22T21:00:00Z | `NQH3` | N |
| 2022-06-24 | 2022-06-23 | 2022-06-22T22:00:00Z → 2022-06-23T21:00:00Z | `NQH3` | N |
| 2022-06-27 | 2022-06-24 | 2022-06-23T22:00:00Z → 2022-06-24T21:00:00Z | `NQH3` | N |
| 2022-06-28 | 2022-06-27 | 2022-06-26T22:00:00Z → 2022-06-27T21:00:00Z | `NQH3` | R |
| 2022-06-29 | 2022-06-28 | 2022-06-27T22:00:00Z → 2022-06-28T21:00:00Z | `NQH3` | R |
| 2022-06-30 | 2022-06-29 | 2022-06-28T22:00:00Z → 2022-06-29T21:00:00Z | `NQH3` | R |
| 2022-07-01 | 2022-06-30 | 2022-06-29T22:00:00Z → 2022-06-30T21:00:00Z | `NQH3` | R |
| 2022-07-05 | 2022-07-01 | 2022-06-30T22:00:00Z → 2022-07-01T21:00:00Z | `NQH3` | R |
| 2022-07-06 | 2022-07-05 | 2022-07-03T22:00:00Z → 2022-07-04T17:00:00Z<br>2022-07-04T22:00:00Z → 2022-07-05T21:00:00Z | `NQH3` | R |
| 2022-07-07 | 2022-07-06 | 2022-07-05T22:00:00Z → 2022-07-06T21:00:00Z | `NQH3` | R |
| 2022-07-08 | 2022-07-07 | 2022-07-06T22:00:00Z → 2022-07-07T21:00:00Z | `NQH3` | R |
| 2022-07-11 | 2022-07-08 | 2022-07-07T22:00:00Z → 2022-07-08T21:00:00Z | `NQH3` | R |
| 2022-07-14 | 2022-07-13 | 2022-07-12T22:00:00Z → 2022-07-13T21:00:00Z | `NQH3` | R |
| 2022-07-15 | 2022-07-14 | 2022-07-13T22:00:00Z → 2022-07-14T21:00:00Z | `NQH3` | R |
| 2022-07-19 | 2022-07-18 | 2022-07-17T22:00:00Z → 2022-07-18T21:00:00Z | `NQH3` | R |
| 2022-07-22 | 2022-07-21 | 2022-07-20T22:00:00Z → 2022-07-21T21:00:00Z | `NQH3` | R |
| 2022-09-19 | 2022-09-16 | 2022-09-15T22:00:00Z → 2022-09-16T21:00:00Z | `NQM3` | N |
| 2022-09-20 | 2022-09-19 | 2022-09-18T22:00:00Z → 2022-09-19T21:00:00Z | `NQM3` | N |
| 2022-09-21 | 2022-09-20 | 2022-09-19T22:00:00Z → 2022-09-20T21:00:00Z | `NQM3` | N |
| 2022-09-22 | 2022-09-21 | 2022-09-20T22:00:00Z → 2022-09-21T21:00:00Z | `NQM3` | N |
| 2022-09-23 | 2022-09-22 | 2022-09-21T22:00:00Z → 2022-09-22T21:00:00Z | `NQM3` | N |
| 2022-09-26 | 2022-09-23 | 2022-09-22T22:00:00Z → 2022-09-23T21:00:00Z | `NQM3` | N |
| 2022-10-07 | 2022-10-06 | 2022-10-05T22:00:00Z → 2022-10-06T21:00:00Z | `NQM3` | R |
| 2022-10-13 | 2022-10-12 | 2022-10-11T22:00:00Z → 2022-10-12T21:00:00Z | `NQM3` | R |
| 2022-10-25 | 2022-10-24 | 2022-10-23T22:00:00Z → 2022-10-24T21:00:00Z | `NQM3` | R |
| 2022-10-27 | 2022-10-26 | 2022-10-25T22:00:00Z → 2022-10-26T21:00:00Z | `NQM3` | R |
| 2022-10-28 | 2022-10-27 | 2022-10-26T22:00:00Z → 2022-10-27T21:00:00Z | `NQM3` | R |
| 2022-11-01 | 2022-10-31 | 2022-10-30T22:00:00Z → 2022-10-31T21:00:00Z | `NQM3` | R |
| 2022-11-02 | 2022-11-01 | 2022-10-31T22:00:00Z → 2022-11-01T21:00:00Z | `NQM3` | R |
| 2022-11-09 | 2022-11-08 | 2022-11-07T23:00:00Z → 2022-11-08T22:00:00Z | `NQM3` | R |

**Smallest staged request plan.** Start with 56 exact segment/schema requests: 12 OHLCV for the never-requested cells and 22 full-segment trade plus 22 status requests for the prior no-bar cells. Only if the new OHLCV response is empty, make the 24 conditional trade/status requests for those segments. The two two-segment holidays account for 34 bounded segments across 32 cells. Do not query a halt, target session, other contract, or a previously resolved cell.

Authenticated metadata-only estimates: initial **$0.000067129729**, conditional fallback **$0.000029027462**, all-path estimate **$0.000096157191**. Quoted 2026-10-15T11:19:12.124547+00:00; estimates are account-specific forecasts, not invoice caps or evidence that any trade occurred. No paid request was made.

**Acceptance.** Positive electronic volume needs a symbol/instrument matched complete response across every active segment, valid bounds and metadata, and a declared completeness standard; sum the volume and recompute the rank with the frozen tie rule. Empty OHLCV alone never means zero. A provider-stream verified zero needs an exact zero-trade response for every active segment, active status, clean response metadata, and an explicit exploratory provider-completeness assumption. Strict zero needs independent feed or venue-completeness evidence. A partial response, ambiguous status, mapping mismatch, or contradiction is a provider gap. Without numeric volume or an independently defensible upper bound below the observed winner (with tie rule), keep the date unresolved and preserve downstream chronology. A metadata estimate of zero records is not such proof.

## B. Five preserved no-trade minutes

The five [clock-validation](nq-w1-five-gap-clock-validation.md) intervals have zero returned trades and active `is_trading=Y`/`is_quoting=Y` status through each gap. I rechecked all ten DBN and JSONL hashes, their bounds, and empty `partial`/`not_found` lists against the preserved manifest. They support provider-stream no-trade samples, subject to the recorded upstream completeness limit. A new `nq-har-exploratory-study-design-v1.1.0` could admit exactly these as clock samples: carry the prior observed trade price and set that minute return to zero; the next observed close still carries its true move. This creates no trade, bar, or volume. Keep the frozen preregistration unchanged.

| CME trade date | Missing minute UTC | Raw symbol | Trades | Status records |
| --- | --- | --- | ---: | ---: |
| 2022-06-06 | 2022-06-05 23:27–23:28 | `NQM2` | 0 | 2 |
| 2022-07-27 | 2022-07-27 03:56–03:57 | `NQU2` | 0 | 3 |
| 2022-08-16 | 2022-08-16 04:43–04:44 | `NQU2` | 0 | 3 |
| 2022-08-18 | 2022-08-18 04:42–04:43 | `NQU2` | 0 | 3 |
| 2022-10-13 | 2022-10-12 22:48–22:49 | `NQZ2` | 0 | 2 |

Under the versioned clock rule, RV1 gains a zero squared term at each gap; positive/negative semivariance also gain zero at that minute. The next observed return retains its price move, so these aggregates can differ from a sparse diagnostic. RV5 and RV15 use complete nonoverlapping segment-anchored blocks on the same 15-minute support; the carried sample can restore an otherwise missing block. BPV uses adjacent within-segment return pairs; the zero sample makes its two touching products zero without connecting across a segment boundary. No estimator convention is revised here; see the [validated arithmetic](nq-w1-five-gap-clock-validation.md).

The 120 identities still map to 22 warmup sessions and 98 potential target rows (50 train, 20 validation, 28 test). Sixty-five potential rows touch a corrected gap. The five-gap policy alone releases **zero** eligible rows; the selector, calendar, and availability gates still apply.

## C. Calendar and availability

Nine dates remain provisional despite complete ordinary-rule grids. The exact missing authoritative evidence is:

| Dates | Missing authoritative NQ evidence |
| --- | --- |
| Jun 22, Jul 6, Sep 7 | Dated Wednesday NQ hours and trade-date confirmation after the respective holiday Tuesday, or a complete effective rule-and-exception register. |
| Oct 10–12 | Dated NQ Globex Columbus guard-window schedule or authoritative confirmation of ordinary hours and no exception; clearing/settlement notices do not answer this. |
| Nov 9–11 | Dated NQ Globex Veterans guard-window schedule or authoritative confirmation of ordinary hours and no exception; clearing notice does not answer this. |

A documented historical OHLCV availability assumption is acceptable **only for a labeled exploratory retrospective study** if fixed before fitting and applied consistently to completed feature/target values. The proposed assumption is that final predecessor OHLCV and derived volume were available at the 5 PM ET decision origin; a one-session-lag sensitivity must show which selector decisions or HAR rows cease to be usable. The 98 rows have correct structural ordering, but original provider publication/revision timestamps are absent. No point-in-time or strict causal claim follows from an assumption.

## D. Blocker matrix

| Blocker | Current evidence | Missing evidence | Minimum remediation | Expected cost | Acceptance | Prevents |
| --- | --- | --- | --- | --- | --- | --- |
| 32 front-three volumes | 328 observed-volume cells, 11 never requested, 21 requested/no bar; no exact trade/status evidence for 32; later cleared values are post-origin and non-equivalent | Exact electronic volume or independently defensible origin-available upper bound for 32 cells; completeness support | Execute only proposed exact bounded requests after separate authorization; verify metadata and raw hashes; rank only resolved cells | $0.000067129729 | All 360 front-three cells resolved and every winner deterministic under complete predecessor volumes or valid bounds | Exploratory and strict |
| Five clock minutes | Five zero-trade bounded responses paired with active status; 169015 observed bars and five provider no-trade samples | Separate versioned exploratory acceptance policy; independent venue completeness only for strict claim | Issue v1.1 exploratory spec and immutable manifest; retain zero clock return and carry prior price at five exact minutes | $0 for policy and local recomputation; external completeness evidence unquoted | Versioned policy, intact evidence hashes, complete matched 1m/5m/15m support, no other unknown minute | Exploratory and strict |
| Nine calendar guards | Ordinary CME rule, four original holiday workbooks, full ordinary-rule grids; nine dates remain provisional | Dated authoritative NQ hours/trade-date response or auditable effective rule-and-exception inventory for each date | Obtain and hash the nine-date authoritative schedule evidence; replay segment grid | Unknown; no paid calendar quote | Every date has authoritative active UTC segments and trade-date identity; no unexplained intervening date | Exploratory and strict |
| OHLCV availability | 98 potential rows have structural feature-before-target order; original publication/revision timestamps absent | Point-in-time provider availability for strict causality; for exploratory, prespecified retrospective assumption and sensitivity lag | Declare conservative availability convention in new version before fitting; seek timestamp evidence only for strict label | $0 for documentation; external timestamp evidence unquoted | Exploratory assumption explicit and chronology replayed; strict label only with point-in-time proof | Exploratory and strict |
| 120-session gate | 120 candidate identities, historical 93 B/27 C, 22 warmup plus 50/20/28 arithmetic, zero released rows | Fresh versioned eligibility decision after selector, calendar, clock, availability gates | Freeze source/code hashes and 120-session manifest before any fit; retain all dates and split | $0 local review; no fit in this task | One uninterrupted 120-session run with 98 targets; no row dropped or bridged; strict tiers separately certified | Exploratory and strict |

**Sequence:** Resolve the exact predecessor cells and nine date schedules, version the clock and availability policy, then replay the complete 120-date selector/grid and freeze an immutable eligibility manifest. Historical 93 B/27 C labels stay historical; none is silently promoted. If any date remains unresolved, the unchanged 22/50/20/28 schedule cannot be released or fitted. Strict certification additionally needs point-in-time provider and venue completeness evidence.

**Minimum isolated engineering:** add a research-only selector/clock adapter that consumes the frozen raw responses, labels each predecessor cell as positive, verified zero, provider gap, or unresolved, and labels each expected minute as observed, verified provider no-trade, or unknown. Recompute matched RV1/RV5/RV15, semivariance, and BPV and write an immutable 120-session manifest with source hashes and the fixed split. Check the two holiday segment sums, five carried minutes, selector tie rule, and 98-row chronology before any later fit. This work belongs to the new exploratory version and does not revise production estimators or the original HAR study.
