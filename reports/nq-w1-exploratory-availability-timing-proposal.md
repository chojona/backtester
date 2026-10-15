# Proposed W1 exploratory availability timing convention

**Status: draft for review, not implemented.** This would require a new version of the exploratory HAR specification and selector manifest. It does not amend the frozen study or establish point-in-time causality.

## Three separate times

| Stage | Proposed rule on an ordinary W1 predecessor | What may be used |
| --- | --- | --- |
| Observation cutoff | **17:00 New York time** at predecessor CME trade-date close (21:00 UTC in EDT; 22:00 UTC in EST) | Only that completed predecessor's active-segment trades and one-minute bars; freeze the front-three eligible roster as of this cutoff. The 16:59–17:00 final minute completes at the cutoff. |
| Contract-selection decision | **17:45 New York time** on that same predecessor date (21:45 UTC in EDT; 22:45 UTC in EST) | Select the highest complete predecessor electronic volume, then lexicographically largest contract code on an exact tie, using only data and corrections assumed available by this deadline. No target-session observation enters the rank. |
| Next-session execution | **First active instant of the target CME trade date**, ordinarily 18:00 New York time (22:00 UTC in EDT; 23:00 UTC in EST) | Begin the chosen raw contract's target-session clock process at its first active segment; do not use its opening bar or volume to revise the already made selection. |

The rule applies to each of the 120 ordered target dates. On a Friday predecessor, the proposed 17:45 decision precedes the following Sunday's 18:00 target opening. On the combined Juneteenth, Independence, and Labor Tuesday predecessors, the 17:00 close follows both documented active segments and the intervening halt; the next target opens at 18:00 Tuesday. If authoritative date-specific CME hours differ, derive the UTC cutoff and execution from those hours and review the decision buffer before admitting that date. Do not infer a time from a civil weekday label.

## Availability and failure behavior

For exploratory retrospective research only, the proposed **45-minute publication/correction allowance** assumes that the final historical OHLCV records and electronic-volume sums for all three predecessor contracts were available by 17:45. This is an assumption, not evidence: retained OHLCV lacks original vendor publication/revision timestamps, and a 2026 retrieval time cannot prove 2022 availability. Store the cutoff, assumed availability deadline, actual decision deadline, and next-session execution timestamp separately in the new manifest. A corrected or missing contract value discovered after 17:45 cannot be backdated into that decision.

The HAR RV1, RV5, RV15 sensitivity measures and the HAR RV5 feature/target series should use the same availability deadline for the completed feature session. A target RV becomes a training or refit input only after its own session closes **and** its declared availability deadline passes. If any contract volume, required clock sample, or feature is unavailable by the decision deadline, mark that target decision unresolved and break the 120-session eligibility chain; do not choose another contract, delay execution silently, or join around the date.

Before implementation, replay a **one-completed-session lag sensitivity**. Under that lag, the prior day's final volume may miss the 17:45 deadline, so the frozen front-three selector may be unusable for the next opening and the 120-session gate can fail. Replacing it with an older predecessor would define a different selector and require a separate version. Preserve the unchanged 22/50/20/28 ordinal schedule until a complete run qualifies.

This convention separates observation from decision and execution, but it would remain **exploratory and retrospectively assumed**. Strict causal certification requires point-in-time publication/revision or receipt evidence for the actual values used, as well as the independent calendar, trade/status, and eligible-universe completeness gates. Review the 17:45 deadline, handling of dated schedule exceptions, and effect on selector/RV eligibility before implementing it.
