# Independent NQ mathematical validation

This suite checks arithmetic, stream boundaries, strict certification metadata, and unfitted HAR feature alignment. Its synthetic paths establish implementation consistency, not estimator performance or HAR predictive validity. The retained history readback checks certification labels and allowlist identity, not independent exchange truth.

## Measurement conventions

- Prices are raw, positive NQ contract OHLC values. A one-minute return is `log(current close / previous close)` when the prior bar is contiguous in the same contract and trading session. The first bar of a session or after a gap uses `log(current close / current open)`. An `UNKNOWN` observation contributes no return. There is no forward fill or zero substitution.
- The one-minute grid uses completed bars and the configured trading calendar. RV is `sum(r_i^2)`; positive and negative semivariance partition that sum by `r_i > 0` and `r_i < 0`. BPV is `(pi/2) sum |r_i r_(i-1)|` for eligible adjacent pairs, without finite-sample correction. Pairing stops at gaps, scheduled halts, contract changes, trading-session changes, and overnight/RTH/post-RTH segment boundaries. The destination segment receives its own return at a segment boundary.
- Five- and fifteen-minute returns sum nonoverlapping constituent one-minute log returns in blocks anchored to each calendar segment opening. A block requires every minute. Incomplete tails are omitted. Frequency comparisons in the suite use exactly 30 minutes of common support: 30 one-minute, six five-minute, and two fifteen-minute returns. RV at the three frequencies need not be equal because within-block signs can cancel.
- All variation values are dimensionless squared log returns, with no annualization, percentage conversion, demeaning, or drift correction. A future annualized *variance* would require an explicit sessions-per-year factor and a complete comparable session definition; this suite applies neither. No partial-window value is promoted to a daily target.
- A canonical streaming estimate is null for an incomplete prefix or unknown coverage. `observed_rv` remains a diagnostic sum over available returns. The next session resets measurement; a close-to-open overnight gap is excluded.

## Strict inputs and HAR alignment

`load_strict_nq_parquet` reconciles every parquet row against a versioned Tier A CSV allowlist by date, contract, tier, version, and segment. `write_research_dataset(..., strict=True)` rejects a non-A selection before reading source data and validates its output after writing. Tier B, C, and D injection tests cover both metadata validation and the loader. Callers should use the strict loader before constructing daily research observations.

`build_har_rows` constructs no fitted model. For feature session `t`, it uses `RV_t`, the arithmetic mean of `RV_(t-4)..RV_t`, and the arithmetic mean of `RV_(t-21)..RV_t`; the target is `RV_(t+1)`. All 22 feature sessions and the target must be complete Tier A observations at the expected version, have consecutive ordinals from the full observed-session ledger, share one research segment, and have strictly increasing aware availability times. An excluded date, missing accepted session, or segment break prevents a row that spans it. The output `as_of` is the completion time of session `t`; the target becomes available later. An ordinal is an observed-session sequence position, not a calendar-day difference.

The current 11 Tier A sessions cannot supply a single 22-session HAR feature window with a next-session target. This validates feature plumbing only and makes no predictive validity claim.

## Reproduction

From the repository root with the project's Python environment:

```sh
.venv/bin/python -m scripts.validate_nq_math --output results/nq-math-validation.json
.venv/bin/python -m pytest -q
```

The first command writes per-check pass/fail outcomes and the command to JSON. A nonzero exit denotes a failed check. The second command runs the existing suite as well. The validation suite contains independent reference loops and synthetic NQ bars; it does not call production formulas to compute expected values. Where the retained licensed Phase 3 files are present, it also audits the real strict parquet labels against the Tier A allowlist; otherwise that check is explicitly skipped.

## Discrepancy log

During implementation, a workspace change made total-session BPV pair returns across research segment boundaries. The independent boundary check and the pre-existing `test_coarse_boundary_returns_and_tails` both identified the mismatch with the documented convention; the latter reported `0.006126105674499959` where `(pi/2) * 37 * 0.0001 = 0.005811946409141118` was expected. The one-line boundary rule was restored to exclude that pair. No scalar estimator formula was changed.
