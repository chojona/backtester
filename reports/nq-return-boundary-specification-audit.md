# NQ return-boundary specification audit — 2026-10-14

## Decision

The frozen return rule is **continuous close-to-close across a contiguous Overnight→RTH or RTH→Post-RTH boundary**. The first return belongs to the destination segment, while the **BPV pair** crossing that boundary is excluded. The production stream, independent acceptance reviewer, legacy historical RV calculation, and versioned historical BPV use that rule. The isolated W1 five-gap clock calculation instead uses the boundary bar's own open at both research cuts. That is a return-reference mismatch, not an ambiguity in the frozen specification. No implementation, tier, or historical output was changed in this audit.

The five dates have one missing source OHLCV minute each. Their production canonical full-session RV1, RV5, signed semivariances, and BPV remain **null**; the complete values below are conditional, evidence-backed clock-process calculations, not accepted historical targets.

## Authority and return-reference matrix

The controlling text is [`docs/VOLATILITY.md`](../docs/VOLATILITY.md), especially “Definitions and interpretation” and “Time, sampling, coverage and contract rules.” It specifies `bpv-segment-v1.0.0`: first observed bar `log(close/open)`; later bars `log(close/preceding close)` when adjacent on the same contract and trading date; and within-session/contract consecutive bars use the previous close **including an RTH boundary**. The opening bar of a new session, first bar after a gap, UNKNOWN bar, scheduled halt, or contract change starts/restarts from its own open. [`docs/NQ_MATH_VALIDATION.md`](../docs/NQ_MATH_VALIDATION.md) repeats the contiguous same-session rule. Neither document says to restart returns merely because the research segment label changes.

BPV is separately `(π/2) Σ |rᵢ₋₁rᵢ|` for adjacent, eligible one-minute returns. Pairs stop at gaps, halts, sessions, contracts, and Overnight/RTH/Post-RTH cuts. The destination boundary return still participates in the **next within-segment pair**. RV5 uses complete, nonoverlapping five-minute blocks anchored to the destination segment open, so its first block also retains that close-to-close boundary return. This is a sampling anchor, not a return reset.

| Boundary or observation | Frozen return reference | BPV treatment |
| --- | --- | --- |
| New trading-session open | Current bar open; exclude previous session close | No cross-session pair |
| Contiguous Overnight→RTH | Previous minute close | Exclude crossing pair; allow pair with following RTH return |
| Contiguous RTH→Post-RTH | Previous minute close | Exclude crossing pair; allow pair with following Post-RTH return |
| Scheduled holiday halt | First observed bar open after halt | No cross-halt pair |
| Contract change, including same-date roll | New contract bar open | No cross-contract pair; daily target remains incomplete if switched mid-session |
| Unknown or missing active minute | UNKNOWN has no return; first later observed bar uses its open; incomplete daily canonical measures are null | No pair through unknown/missing minute |
| Explicit evidence-backed NO_TRADE minute | Carry last observed price; zero return, then next observed close uses carried price | Zero products touching flat minute; later within-segment pairs resume |

The last row applies only to an explicitly supported clock sample or provider-evidenced `NO_TRADE` bar. An unexplained OHLCV absence does not receive a zero return. Source-status evidence supports the five investigated minutes for an isolated experiment; it does not certify exchange-wide completeness or the full dated calendar.

## Implementation inventory

| Calculation | Location | First return and research-cut behavior | BPV / status |
| --- | --- | --- | --- |
| Production stream | [`backtester/volatility.py`](../backtester/volatility.py), `RealizedVolatility.update` and `_Accumulator.add` | `previous.close` when adjacent; segment label does not reset return. Session, halt, gap, UNKNOWN, or contract change uses current open. | `segment_adjacent` suppresses the crossing product. Matches frozen rule. |
| Offline chart point returns | [`backtester/volatility_charts.py`](../backtester/volatility_charts.py), `prepare_sessions` | Recomputes plotted minute returns from previous close when adjacent on the same date/contract, including research cuts. | Session totals come from the production stream; this path does not calculate a second BPV. |
| Historical acceptance generation | [`scripts/accept_nq_history.py`](../scripts/accept_nq_history.py), lines 260–265 | First bar open, every later full-grid bar previous close, including both research cuts. | Original `bpv-all-adjacent-v0.0.0` includes crossing products; RV/semivariance return references match, BPV version differs. |
| Historical BPV versioning | [`scripts/version_nq_bpv.py`](../scripts/version_nq_bpv.py), `measures` | First open, then previous close. | `bpv-segment-v1.0.0` excludes research-cut pairs. Matches frozen rule on its complete-grid inputs. |
| Independent strict numeric check | [`scripts/audit_strict_nq_numeric.py`](../scripts/audit_strict_nq_numeric.py) | First open, then previous close. | Calculates both historical BPV conventions and checks streaming. |
| Independent retained-data acceptance reviewer | [`docs/acceptance/review_databento.py`](../docs/acceptance/review_databento.py), lines 128–149 | First open, then previous close across research cuts; RV5 blocks split at cuts. | BPV pairs only within label. Matches frozen rule. |
| Independent prefix acceptance check | [`docs/acceptance/check_databento_prefixes.py`](../docs/acceptance/check_databento_prefixes.py), lines 42–51 | First open, then previous close through the requested prefix and across research cuts. | BPV pairs only within label. Matches frozen rule on its acceptance sample. |
| Holiday candidate arithmetic | [`scripts/build_nq_w1_holiday_candidate.py`](../scripts/build_nq_w1_holiday_candidate.py), lines 72–105 | First open after each active-interval halt; otherwise previous close, including research cuts. | BPV excludes research-cut and halt pairs. Matches frozen reference on its candidate grid. |
| Experimental clock API | [`backtester/nq_clock_experiment.py`](../backtester/nq_clock_experiment.py), `experimental_clock_rv` | First open for **every caller-supplied segment**. It is correct at a true halt/session/contract break, but will reset at a research cut if the caller creates a segment there. | Returns RV1/RV5 only; caller controls segment IDs. |
| W1 five-gap validator | [`scripts/validate_nq_w1_five_gap_clock.py`](../scripts/validate_nq_w1_five_gap_clock.py), `segments` and `measure` | Splits every active interval at 09:30 and 16:00 ET, then takes each piece's first bar open for experimental and sparse comparator returns. | Manual BPV pairs only inside each piece. Pair boundary matches; return reference does not. Its saved full-session RV1/RV5/RS/BPV and 98 potential HAR rows inherit the reset convention. |

[`scripts/certify_nq_history_phase3.py`](../scripts/certify_nq_history_phase3.py) assigns quality tiers and research metadata; [`backtester/nq_har.py`](../backtester/nq_har.py) builds feature rows. Neither calculates minute returns. Scalar functions in `backtester/volatility.py` consume already calculated returns and cannot choose a bar reference themselves. The independent `logret` in the W1 validator and `log_return` in production implement the same logarithm; their **selected reference prices** differ.

## Small independent example

Take the last Overnight close as `100`; the first RTH bar opens `101`, closes `102`; the following RTH minute closes `103`; and the fifth RTH minute closes `106`. All five RTH minutes are present. Under the frozen rule, first RTH return is `ln(102/100) = 0.01980262729618`; under the reset rule it is `ln(102/101) = 0.009852296443012`. Its RV1 and positive-semivariance contributions are respectively `0.0003921440478314` and `0.00009706774520098`. The first RV5 block contributions are `ln(106/100)² = 0.0033952656539603` and `ln(106/101)² = 0.0023346849094750`.

The cross-boundary BPV product is excluded in **both** conventions. Yet the eligible product with the next RTH return `ln(103/102)` is `0.00030347454582016` under the frozen rule versus `0.00015098608601826` under the reset rule. This also shows why “exclude the BPV boundary pair” cannot be read as “reset the boundary return.” The same construction applies at RTH→Post-RTH. At a true session open, halt, roll, or unknown gap, the frozen rule explicitly uses the bar's own open, so that synthetic distinction disappears there.

For a separate negative RTH→Post-RTH example, take prior RTH close `100`, Post-RTH opening bar `O=99`, `C=98`, and next close `97`. Frozen first return `ln(98/100)=-0.02020270731752` contributes `0.00040814938295735` to **negative** semivariance; reset first return `ln(98/99)=-0.01015237146402` contributes `0.00010307064634341`. The eligible next Post-RTH BPV product is respectively `0.00032548324757367` and `0.00016356356515729`. Again, neither convention includes the preceding RTH×Post-RTH pair.

## Five-date quantification

I used the retained raw selected-contract Parquet and candidate UTC grids, with no network request. For each date and each research cut, I read the preceding close `P`, boundary open `O`, boundary close `C`, next close, and first five-minute block endpoint. I replaced only the experimental boundary `a=ln(C/O)` by the frozen `b=ln(C/P)` when the prior minute was contiguous. Thus `ΔRV1=b²−a²`, `ΔRV5=ln(endpoint/P)²−ln(endpoint/O)²`, and `ΔBPV=(π/2)|r_next|(|b|−|a|)`. Signed semivariance is assigned by the sign of each return. There is **no cross-cut BPV product** in either column. The input experimental complete-clock values are preserved in [`results/nq-w1-five-gap-clock-validation.json`](../results/nq-w1-five-gap-clock-validation.json); the deltas were independently recomputed from source boundary prices. `Δ` means frozen minus experimental, in squared log-return units.

| Trade date | ΔRV1 | ΔRV5 | ΔRS+ | ΔRS− | ΔBPV |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-06-06 | −3.26866190047e−08 | −4.76605681029e−08 | 0 | −3.26866190047e−08 | −1.23796093930e−08 |
| 2022-07-27 | +5.77714791688e−08 | +8.37371119768e−08 | 0 | +5.77714791688e−08 | +1.23553194052e−09 |
| 2022-08-16 | −3.08709091942e−08 | −2.68340805100e−08 | 0 | −3.08709091942e−08 | −9.49397341244e−09 |
| 2022-08-18 | +1.33891743105e−08 | −1.26922145270e−07 | +1.33891743105e−08 | 0 | +2.48126695755e−08 |
| 2022-10-13 | +7.82373311723e−08 | +1.10050666453e−07 | +7.82373311723e−08 | 0 | +1.25617017277e−07 |

Applying those deltas to the existing complete **experimental clock** series gives the frozen-reference counterfactual below. This comparison holds the five evidenced no-trade carries, selected contract, minute grid, BPV eligibility, and RV5 block anchors fixed. It is **not** the comparison with the incomplete sparse diagnostic in the earlier W1 report.

| Trade date | Frozen-reference RV1 | RV5 | RS+ | RS− | BPV |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-06-06 | 0.000283004126192 | 0.000245807530114 | 0.000147365747282 | 0.000135638378910 | 0.000284655372334 |
| 2022-07-27 | 0.000261577898609 | 0.000336715308672 | 0.000170349132546 | 0.000091228766063 | 0.000249036523493 |
| 2022-08-16 | 0.000107185211682 | 0.000111139850500 | 0.000051209207064 | 0.000055976004618 | 0.000105954201691 |
| 2022-08-18 | 0.000130934710263 | 0.000134137847952 | 0.000063726049361 | 0.000067208660902 | 0.000133528497791 |
| 2022-10-13 | 0.002197493363833 | 0.002007580383880 | 0.000596987248747 | 0.001600506115087 | 0.001185547615150 |

For a concrete source check, the 2022-10-13 RTH→Post-RTH cut has `P=11081.25`, `O=11081.75`, and `C=11084.25`; the reset and frozen returns are `0.000225570694812` and `0.000270690940274`. On 2022-06-06 and 2022-07-27 the Overnight→RTH `P=O`, so that cut contributes exactly zero; their Post-RTH cuts still differ. All five dates have at least one nonzero cut difference. The earlier experimental-minus-sparse differences (one no-trade minute and the first post-gap reference) remain a **separate** effect; adding them to these deltas without matching reference conventions would confound two changes.

## Historical and test dependence

The retained [`volatility-by-session.csv`](../results/databento-nq-full-history/volatility-by-session.csv) has 1,200 full-grid historical rows. Its RV and signed semivariance use the frozen close-reference rule; its BPV uses the separately labeled legacy all-adjacent convention. The derived [`bpv-segment-v1.0.0/volatility-by-session.csv`](../results/databento-nq-full-history/bpv-segment-v1.0.0/volatility-by-session.csv) corrects only BPV pairing from those same returns. Neither table depends on the W1 research-cut reset. The preserved holiday candidate also uses the frozen reference. Conversely, the W1 five-gap clock JSON, its five-date report, and all 120 experimental daily values use the reset; the 98 arithmetic HAR rows derived from their RV5 series are convention-dependent. They are **potential rows only**: the retained report records zero actually eligible certified/HAR-fit rows, and no HAR model has been fit. The five source-sparse dates have null production canonical measures, so no accepted historical daily target on those dates is being silently changed.

[`tests/test_nq_math_validation.py`](../tests/test_nq_math_validation.py) explicitly tests BPV exclusion and production close reference, but its `reference_stream_returns` helper resets on a segment-label change; its parameterized 30-minute cases do not reach a research cut. The explicit boundary fixture makes `boundary open = preceding close`, so both return rules give the same expected value. [`tests/test_bpv_estimator_version.py`](../tests/test_bpv_estimator_version.py) and [`tests/test_research_preflight_audit.py`](../tests/test_research_preflight_audit.py) similarly test pair exclusion with continuous synthetic opens. [`tests/test_nq_clock_experiment.py`](../tests/test_nq_clock_experiment.py) validates a true break and one no-trade minute, but does not exercise a contiguous research cut. The W1 validator's assertions and saved numbers instead lock in the reset convention. Existing tests therefore do not arbitrate the differing-open boundary case; the frozen prose and production reference logic do.

## Smallest versioned correction

Keep production `RealizedVolatility`, certification tiers, retained source and historical outputs unchanged. In a **new experimental clock return version**, for example `nq-clock-returns-v2.0.0`, and separate result path, give each minute both an active-continuity ID and research-segment label. At a research cut with an adjacent same-contract, same-trading-date prior clock sample, calculate the first destination return from the prior close; start a new RV5 block and suppress only the crossing BPV pair. At a true session/holiday halt/contract break or unknown gap, use the current observed bar open; preserve evidence-gated zero no-trade minutes. Recompute the five complete conditional series and any 120-date/98-row arithmetic candidates under that version; publish old-versus-new hashes and the five deltas above. Add one synthetic fixture with `P≠O` at each research cut that checks RV1, RV5, signed semivariance, and the **next eligible** BPV product, plus a true-halt reset fixture. Do not promote certification or use the corrected candidates for HAR until the independent calendar, volume, and coverage gates pass.

This audit created only this report. The source Parquet and existing results were read, not rewritten.
