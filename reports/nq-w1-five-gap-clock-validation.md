# NQ W1 five-gap clock-time mathematical validation

**Decision:** All five preserved intervals are mathematically resolved **for this experimental, provider-observed clock process**. The no-trade minute has a carried last observed trade price and a zero clock return, while the next observed price move remains in its original minute. Exchange-wide trade completeness, historical certification, dated-calendar exceptions, causal predecessor volume, and historical data availability remain unresolved. No HAR model was fitted.

## Preserved evidence and immutable inputs

The read-only audit verified the SHA-256 of all **ten compressed DBN files** and their JSONL exports against `data/raw/databento/NQ/w1-five-gap-investigation-20261014T205456Z/manifest.json`. It reopened every DBN and matched the exact `GLBX.MDP3` dataset, `trades` or `status` schema, raw symbol, inclusive start and exclusive end nanosecond bounds, `limit=null`, `partial=[]`, and `not_found=[]` to the preserved ten request arguments in `results/nq-w1-120-session-candidate.json`. The five trade DBNs each contain **zero** records. The status DBNs contain **2, 3, 3, 3, and 2** records for the June 6, July 27, August 16, August 18, and October 13 trade dates. Each starts with action 6 then 7 at the candidate session open, has `is_trading=Y` and `is_quoting=Y` throughout, and has no returned interruption state. The three longer windows include a UTC-midnight action-7 carried-state snapshot. Their instrument IDs match retained adjacent OHLCV bars.

The source Parquet SHA-256 is `16a626bf24c90a73a176e4a21138f58c40e3a5c35ae70a57643c3f1878f94c44`; the candidate and evidence manifest hashes are `b3a702768c7444f4c6cd5e692e57b1fc0b0e47919ff9445991adb465f6a07c2e` and `ec6df2be79e33a63562e55566fef43b4c85b114a6942ece14d99f3150955d1e8`. No network or paid retrieval was used. These checks establish what the preserved provider responses contain; zero returned trades does not prove the exchange sent none.

## Clock process and boundary rules

For each of the 120 candidate trade dates, I used its preserved selected raw contract and active-minute segments. I subdivided each active segment at the frozen 09:30 and 16:00 New York research boundaries (13:30 and 20:00 UTC on these dates). The three documented holiday halts remain separate active segments. Every resulting segment length is divisible by 15 minutes; no five-minute or fifteen-minute terminal tail is needed. At each halt, trade-date boundary, contract change, and research-segment boundary, the first return uses that segment’s first observed bar open. BPV pairs are allowed only within one continuous segment. No close-to-open jump across a boundary enters this process.

At an observed minute the clock price is the retained raw bar close. At **only** the five verified no-trade minutes it is the preceding observed last-trade price, with no bar, trade, or volume object added. Thus the gap return is exactly zero. The first following observed minute returns `log(next close / carried prior close)`, retaining any move that the sparse stream would otherwise restart from its own open. All other 169,015 selected observations remain source bars. This is an isolated mathematical series, not a production OHLCV revision.

Definitions: `RV1=Σr²`; positive and negative semivariance sum `r²` for `r>0` and `r<0`; `BPV=(π/2)Σ|rᵢrᵢ₋₁|` over eligible within-segment adjacent minutes, without a finite-sample correction. `RV5` squares each complete, nonoverlapping five-minute sum of `r`, with blocks anchored to the research-segment open. Values are dimensionless squared log returns and unannualized.

## Reconstructed full-session values

| Trade date | RV1 | RV5 | RS+ | RS− | BPV |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-06-06 | 0.000283036812811 | 0.000245855190682 | 0.000147365747282 | 0.000135671065529 | 0.000284667751943 |
| 2022-07-27 | 0.00026152012713 | 0.00033663157156 | 0.000170349132546 | 9.11709945837e-05 | 0.000249035287961 |
| 2022-08-16 | 0.000107216082592 | 0.000111166684581 | 5.12092070643e-05 | 5.60068755272e-05 | 0.000105963695664 |
| 2022-08-18 | 0.000130921321089 | 0.000134264770097 | 6.37126601869e-05 | 6.72086609022e-05 | 0.000133503685122 |
| 2022-10-13 | 0.0021974151265 | 0.00200747033321 | 0.000596909011416 | 0.00160050611509 | 0.00118542199813 |

Each ordinary date has 1,380 clock returns, 276 eligible five-minute blocks, and 1,377 within-segment BPV pairs (three segments, so two cross-boundary pairs excluded). The original sparse grid has 1,379 observed returns, 275 eligible five-minute blocks, and 1,375 BPV pairs: two would touch the absent minute. All five gap blocks occur within Overnight; no boundary was crossed by carrying a price. `RV1 = RS+ + RS−` on every date within floating-point tolerance. Independently telescoping every five-minute return from its first reference price to its last clock price agreed with the sum of its one-minute returns.

## Exact sparse comparison and difference attribution

The sparse comparator uses the same segment-open reset rule, includes only observed bars, restarts the first post-gap return at that bar’s open, and excludes any five-minute block containing the gap. It is an **incomplete diagnostic**, not a full-session target. The table gives experimental minus sparse diagnostic; a zero means the difference is algebraically zero apart from rounding.

| Trade date | ΔRV1 | ΔRV5 | ΔRS+ | ΔRS− | ΔBPV |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-06-06 | 1.54710371835e-08 | 1.94406503386e-08 | 0 | 1.54710371835e-08 | 3.73907530258e-09 |
| 2022-07-27 | 1.65858191909e-08 | 0 | 1.65858191909e-08 | 0 | 5.21038718215e-09 |
| 2022-08-16 | 9.36597977572e-09 | 1.63893940529e-08 | 9.36597977571e-09 | 0 | 5.25371899614e-09 |
| 2022-08-18 | 4.47723034713e-09 | 2.78876708015e-08 | 0 | 4.47723034711e-09 | 4.86876209214e-09 |
| 2022-10-13 | 2.12148685641e-09 | 2.12129144025e-09 | 2.12148685641e-09 | 0 | 9.99773179002e-09 |

For every date, let `P` be the prior observed close, `O` and `C` the first post-gap bar open and close, and `r_next` the following observed minute return. The one-minute difference is exactly `log(C/P)² − log(C/O)²`; it lands in the semivariance matching the sign of `log(C/P)` here. The BPV difference is `(π/2)|r_next| (|log(C/P)| − |log(C/O)|)`. Both BPV products touching the zero gap return are zero. No other one-minute or BPV term changes. The RV5 difference is the square of the sole block excluded by the sparse comparator; all other five-minute blocks match. The independent numeric audit verified these identities to `1e−15`.

| Trade date | Prior close P | Next open O | Next close C | Omitted sparse block start UTC | Clock block return |
| --- | ---: | ---: | ---: | --- | ---: |
| 2022-06-06 | 12552.75 | 12552.0 | 12550.75 | 2022-06-05T23:25:00Z | -0.00013942973262 |
| 2022-07-27 | 12276.5 | 12277.5 | 12278.25 | 2022-07-27T03:55:00Z | 5.58567406737e-17 |
| 2022-08-16 | 13668.5 | 13669.0 | 13670.5 | 2022-08-16T04:40:00Z | 0.000128021068785 |
| 2022-08-18 | 13471.75 | 13471.5 | 13470.0 | 2022-08-18T04:40:00Z | -0.000166996020316 |
| 2022-10-13 | 10855.25 | 10855.75 | 10855.75 | 2022-10-12T22:45:00Z | -4.60574797428e-05 |

July 27’s omitted block has a return of about `5.59e−17`, so its RV5 contribution rounds to zero despite restored five-minute eligibility. October 13’s next bar has `O=C=10855.75`: the sparse post-gap return is zero, but the clock return from `P=10855.25` is positive. This is why carrying the last price preserves, rather than erases, that first observed movement.

The original production sparse-bar estimator was also run read-only on the five selected bar streams with the ordinary 2022 break removed. For every date it reports `session_complete=false`, one missing minute, and **null canonical RV1, RV5, BPV, RS+, and RS−**, while retaining 275 five-minute samples and an `observed_rv` diagnostic. Its observed diagnostic differs from the segment-reset sparse comparator because the current production implementation uses the preceding close for the first RTH/Post-RTH return when minutes are contiguous. The experimental convention resets that first return at its own open as required here. The difference is exactly the sum, over those boundaries, of `log(boundary close / prior close)² − log(boundary close / boundary open)²` (within numerical rounding):

| Trade date | Production `observed_rv` | Segment-reset sparse RV1 | Production minus segment-reset |
| --- | ---: | ---: | ---: |
| 2022-06-06 | 0.000282988655155 | 0.000283021341774 | -3.26866190058e-08 |
| 2022-07-27 | 0.00026156131279 | 0.000261503541311 | 5.77714791703e-08 |
| 2022-08-16 | 0.000107175845703 | 0.000107206716612 | -3.08709091943e-08 |
| 2022-08-18 | 0.000130930233033 | 0.000130916843859 | 1.33891743116e-08 |
| 2022-10-13 | 0.00219749124235 | 0.00219741300502 | 7.82373311727e-08 |

This boundary-reference difference is separate from the five no-trade corrections. A production estimator or certification decision was not changed to reconcile it.

## Five-minute support and chronological HAR eligibility

All five affected Overnight blocks start at their segment-open plus an exact multiple of five minutes, as shown above. The experimental process has the complete 169,020-minute candidate grid, 33,804 eligible five-minute blocks, and full matched fifteen-minute support under the candidate calendar. The sparse source alone has only 169,015 selected bars and lacks one five-minute block on each gap date. None of the five sparse dates has a canonical full-session daily target.

I recalculated the candidate’s 120 chronological daily `RV5` values and all 98 potential target rows using the frozen 22-session warm-up. Each row uses the immediately preceding date as `RV_1`, the last five distinct dates as the arithmetic `RV_5` feature, and the last 22 distinct dates as the arithmetic `RV_22` feature; the next date is the target. No corrected daily RV is duplicated inside any feature window or used as a feature for its own target. The manifest’s target ordinals, feature starts, and forecast-origin dates matched the independent index reconstruction.

| Corrected trade date | Candidate ordinal | RV1-feature rows | RV5-feature rows | RV22-feature rows | Target rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-06-06 | 3 | 0 | 0 | 3 | 0 |
| 2022-07-27 | 38 | 1 | 5 | 22 | 1 |
| 2022-08-16 | 52 | 1 | 5 | 22 | 1 |
| 2022-08-18 | 54 | 1 | 5 | 22 | 1 |
| 2022-10-13 | 93 | 1 | 5 | 22 | 1 |

June 6 is in the 22-session warm-up, so it appears in only three RV22 feature windows before aging out and is never a target. Each later corrected date appears once as a target and in exactly 22 later RV22 windows. Across the 98 potential rows, 65 touch at least one of the five corrected dates (38 train, 4 validation, 23 test); 61 are feature-only and four have a corrected target. The other 33 do not touch these gaps. Potential split counts remain 50/20/28.

**Actual eligible certified/HAR-fit rows remain zero.** These 98 rows are conditional arithmetic candidates under the preserved 120-date calendar and selected-contract plan. The nine guarded calendar dates, predecessor-volume completeness, certification tiers (93 B and 27 C in the candidate), and historical publication/availability timing remain separate gates. Neither the gap evidence nor this clock calculation promotes a tier, qualifies the 120-session run for the preregistered study, or authorizes a fit.

## Reproduction and scope

The read-only calculation is in `scripts/validate_nq_w1_five_gap_clock.py`; numeric results, individual five-minute blocks for the five dates, evidence hashes, and chronological feature dates are in `results/nq-w1-five-gap-clock-validation.json`. The script verifies source and evidence hashes before computing, reads the retained Parquet, and writes only that separate result file. It neither creates synthetic OHLCV/volume nor edits production estimators, raw data, certification, or HAR artifacts.
