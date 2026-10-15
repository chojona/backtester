# NQ W1 front-three feasibility after acquisition preflight

**2026-10-15 decision: NO-GO.** The authenticated metadata requote failed with `504 The remote gateway timed out.` Because the approved plan requires every exact quote to succeed before any paid request, acquisition stopped. There are **no new DBNs, raw-response hashes, electronic-volume measurements, provider-zero determinations, or selector changes**. The hash-bound [preflight failure record](../data/raw/databento/NQ/w1-electronic-volume-quote-abort-20261015T113239Z/preflight-failure.json) and [per-cell evidence ledger](../results/nq-w1-front-three-quote-abort-evidence.json) preserve the outcome. The previous plan estimate was not used in place of a fresh all-request quote.

## Scope audit completed before the quote failure

The frozen [32-cell plan](../results/nq-w1-targeted-remediation-plan.json), [gap inventory](../results/nq-front-three-selector-feasibility.json), and [120-date candidate](../results/nq-w1-120-session-candidate.json) agree on the ordered dates and predecessor identities. Eleven cells were never requested; 21 had completed, unpartial original OHLCV requests with no retained bar. Their 34 active predecessor segments include both separate intervals on **June 21** and **July 5**. Every proposed request contains one unresolved raw symbol, one exact half-open active predecessor interval, and one approved schema. None spans the scheduled holiday halt, enters a target session, or includes another contract.

The initial batch is 12 OHLCV, 22 trades, and 22 status requests (**56**). The conditional batch is 12 trades and 12 status requests (**24**), each tied to a never-requested segment and permitted only after a clean empty OHLCV response. An authenticated metadata quote batch for the 80 exact requests was attempted, but at least one quote failed with a provider 504. The failing request identity was not preserved by the concurrent quote call. A fresh cumulative estimate therefore does not exist, and the **$0.01 gate did not pass**. No `timeseries.get_range` call was made.

## Per-cell and 120-date result

The [evidence ledger](../results/nq-w1-front-three-quote-abort-evidence.json) lists all 32 target/predecessor dates, raw symbols, UTC bounds, original request status, retained bar count, and later cleared-volume diagnostic. Every cell remains **unresolved with provider completeness unassessed**. No cell has newly observed positive electronic volume, a provider-observed zero, an independently certified exchange-wide zero, or an origin-available upper bound. The existing cleared-volume values remain later, non-equivalent diagnostics. Empty OHLCV is never treated as zero.

The original [front-three feasibility](nq-front-three-selector-feasibility.md) therefore remains the numeric baseline: **88/120** dates have conditional retained-panel ranks, **32/120** are indeterminate, and **zero established winner disagreements** with the legacy selector were found among the 88. No new disagreement can be assessed. Strictly causally certified dates remain **zero**. The unchanged sequence still has **22 warmup sessions, 50 train, 20 validation, and 28 test targets**; 81 of 98 potential HAR rows include an unresolved selector date. No date was dropped, substituted, or bridged.

## Gate decision

**NO-GO to release this 120-date front-three series or advance it as eligible for the calendar and clock gates.** Those independent evidence investigations may continue separately, but they cannot repair the failed electronic-volume gate or authorize a HAR fit. A later acquisition attempt needs a new complete authenticated quote batch and a fresh gate check before any paid request. The proposed [availability timing convention](nq-w1-exploratory-availability-timing-proposal.md) is for review only and has not been implemented.

The requested completed acquisition manifest and DBN hashes cannot exist for this attempt because no paid response was retrieved. The preflight failure record is write-once and has a companion SHA-256 file; its hash is also recorded in the per-cell ledger.
