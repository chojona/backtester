# NQ causal contract-selection evidence register

**Audit date:** 2026-10-15. **Scope:** 120 target CME trade dates, June 2–November 21, 2022. The reproducible date and contract records are in [`results/nq-causal-contract-selection-register.json`](../results/nq-causal-contract-selection-register.json); rebuild them with `python3 scripts/audit_nq_causal_contract_selection.py`.

The audit independently resums the retained one-minute electronic bars inside each corrected predecessor CME trade-date segment. It reconstructs each nine-contract expected roster from the CME listing cycle effective May 23, 2022, and checks each identity against the preserved effective-dated definition analysis. It replays the historical selector using target-date bar presence and `max(predecessor volume or zero, contract code)` solely for comparison. The audit's own candidate rank preserves unknown volumes and uses descending `(volume, contract code)` order. The register pins input hashes and includes each request manifest's hash, exact UTC segment bounds, last bar start and completion, definition activation and expiration, first definition receipt, source request coverage, and later cleared-volume event and receipt times.

| Evidence gate | Result |
| --- | ---: |
| Rule-derived target/contract cells | 1,080 |
| Retrospectively valid definition identities at origin | 1,080 |
| Retained positive electronic-volume cells | 328 |
| Unknown electronic-volume cells | 752 |
| Contract/segment cells covered by an OHLCV request | 349 |
| Requested cells with no retained bar; zero unproved | 21 |
| Later numeric cleared-volume cells | 575 |
| Later cleared-volume cells received by decision origin | 0 |
| Historical decisions reproduced by exact selector replay | 120/120 |
| Causally validated decisions | 0/120 |

All **120 decisions are unresolved** for an independently established causal winner. The known electronic subset supports each retained winner, including the June 14 and September 13 rolls, but no date has a full electronic-volume roster. A requested symbol with no retained bar is still unknown, not zero. The 731 unrequested cells and 21 requested/no-bar cells make up the 752 unknowns. The retained OHLCV totals are observed lower bounds: neither the acquisition requests nor the preserved bar data certify full venue feed continuity or the availability time of a complete predecessor total. The full as-of venue security-definition book is also unverified; effective-dated identities and a published cycle establish a strong expected roster, not an independently complete venue book.

For June 14, predecessor June 13 closes at **2022-06-13T21:00:00.000000000Z**. The retained known rank is NQU22 610,767, NQM22 387,941, NQZ22 268; six eligible electronic volumes are unknown. For September 13, predecessor September 12 closes at **2022-09-12T21:00:00.000000000Z**. The known rank is NQZ22 367,205, NQU22 313,361, NQH23 135; six are unknown. The register gives the later cleared rank for every date as a separate comparison. Cleared volume is a different metric and every observed cleared message arrived after its decision origin. Its sparse rows and later timestamps cannot close any electronic-volume or origin-availability gate.

The observed bar's minute start, its one-minute completion, the predecessor's final scheduled segment end, the provider receipt of a definition or cleared statistic, and the decision origin are separate fields. No provider receipt timestamp was retained for the electronic bar panel, so `electronic_volume_provider_available_utc` remains `null` throughout. The register's `causally_validated` flag can only be true after a complete as-of roster, complete electronic-volume coverage, and decision-time availability are independently evidenced; none is currently true.

The dated listing rule and prior audit are documented in [`nq-causal-contract-universe-audit.md`](nq-causal-contract-universe-audit.md). The definition/statistics source and its scope limits are documented in [`nq-definition-statistics-acquisition-evidence.md`](nq-definition-statistics-acquisition-evidence.md). This register changes no production roll selector, certification tier, historical decision, or HAR input.
