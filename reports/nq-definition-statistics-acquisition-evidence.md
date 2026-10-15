# NQ definition and cleared-volume acquisition evidence

**Acquired:** 2026-10-14 22:31 UTC. **Scope:** the two exact requests in [the approved preflight](nq-definition-statistics-final-acquisition-preflight.md). **Disposition:** retrieval complete; retrospective comparison possible; causal winner unresolved on all 120 dates. No further dataset was purchased.

## Reproduction and chain of custody

Run `.venv/bin/python scripts/analyze_nq_definition_statistics.py` from the repository root. The script checks the plan and original DBN SHA-256 hashes before decoding. It writes [cell and date results](../results/nq-definition-statistics-evidence.json) and the [lossless integer-field cleared-volume stream](../results/nq-cleared-volume-stream.jsonl). The [acquisition script](../scripts/acquire_nq_definition_statistics.py) contains an independent fixed copy of the two approved requests and verifies it against the preserved plan, with only the authorized statistics end amendment. It obtained all six fresh metadata quotes before either download and enforced a decimal $0.10 combined cost gate. Its [run manifest](../data/raw/databento/NQ/definition-statistics-20261014T223138Z/acquisition.json) preserves ordered parameters, omitted `limit`, UTC quote/call/receipt times, SDK 0.87.0, quotes, response metadata, raw file sizes, and hashes. Both raw files were written directly as compressed DBN and read back without alteration. The response metadata matched each exact request, including bounds and ordered symbols.

| Schema | Fresh estimated USD | Billable bytes | Estimated / decoded records | Original DBN SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `definition` | $0.001183066517 | 747,240 | 1,437 / 1,437 | `3540a481934599a2a1c4f056ea04ebd1eefb8ee83988d52a1f0d4d3158b2b4f0` |
| `statistics` | $0.028197541833 | 30,276,880 | 378,461 / 378,461 | `4d461664fdeb055439806d47bd4d8ce2568d164b51ebc7c5e866a5c98d30c79c` |
| **Combined** | **$0.029380608350** | **31,024,120** | **379,898 / 379,898** | — |

The compressed files are `01-definition.dbn.zst` (10,378 bytes) and `02-statistics.dbn.zst` (8,713,059 bytes) in the run directory above. Databento returned no settled charge in these responses; `actual_charge_usd` is therefore `null`. The quoted cost is an estimate, not an invoice. Both responses report `partial=[NQU3,NQZ7]` and `not_found=[]`; these partial intervals match the preflight's early raw-symbol mapping gaps. No unquoted request or retry was made.

## Historical roster and identity

All 1,437 dated definition messages were decoded. The relevant 11 instrument IDs map uniquely to XCME `NQ` outright `FUT` contracts (`instrument_class=F`, `leg_count=0`). In particular, `NQZ7` is instrument **23041**, December **2027**, expiring 2027-12-17 14:30 UTC, with no legs. `NQU3` was first received June 5 and has June 17 activation; `NQZ7` was first received September 4 and has September 16 activation. The rule-implied nine contracts have matching definition identity and effective activation/expiration at each of the 120 decision origins. The early partial raw-symbol intervals precede those activations. Per-date evidence, including first receipt and activation/expiration nanoseconds, is in the machine result. Definition snapshots do not certify completeness of every venue definition feed interval or every exchange rule exception.

## Cleared-volume cells and publication

Of the **1,080** expected `(target date, predecessor CME trade date, contract)` cells, **575** have numeric `CLEARED_VOLUME` (`stat_type=6`) and **505** have no matching record in the approved window. Of the **752 previously unknown** cells, **247** now have numeric values: **207 explicitly published zeros** and **40 positive values**. The remaining **505 are unknown, never inferred zero**. Missing cells concentrate in `NQZ25` (120), `NQZ26` (120), `NQZ23` (82), `NQZ24` (82), `NQZ27` (46), `NQU23` (45), and `NQM23` (10). No date has all nine numeric volumes, so the retrospective full-roster rank is unresolved for every date. The absent statistics may reflect CME's sparse publication of far contracts, but these data alone do not prove zero trading, nonlisting, a feed gap, or an upper bound below the leader.

The full statistics response contains 378,461 records; 1,178 are cleared-volume messages. They form 589 `(instrument ID, ts_ref)` groups, each with two `NEW` messages with identical quantities and distinct venue event/receipt times and sequences. There are **no observed quantity changes** in this bounded window. The later message is a repeat, not evidence that the value was final; corrections received on or after November 23 UTC remain outside the request. The original nanosecond `ts_event`, `ts_recv`, `ts_ref`, `ts_in_delta`, sequence, channel, action, flags, quantity, and publisher are retained in the raw DBN and integer-field JSONL. The first received cleared volume for a covered predecessor cell arrived **4.26 to 45.51 hours after** its 5 p.m. ET close (median **4.66 hours**). No covered cell had cleared volume by its decision origin. `ts_event` is venue message time, `ts_recv` provider receipt, and `ts_ref` CME trade date; a scheduled bulletin time is not substituted for any of them.

The Friday November 18 predecessor illustrates the boundary: `NQZ22` volume **585,873** for `ts_ref=2022-11-18` first arrived at **2022-11-20 18:30:27.604092887 UTC**, then repeated unchanged on November 21. Both are after the Friday **22:00 UTC** forecast origin. The November 23 exclusive end includes these publications but does not establish a forever-final value.

## Roll decisions: retrospective versus causal

| Target / predecessor | Retained Globex OHLCV leader and runner-up | Later cleared volume leader and runner-up | Decision at 5 p.m. ET predecessor close |
| --- | --- | --- | --- |
| June 14 / June 13 | `NQU22` 610,767; `NQM22` 387,941 | `NQU22` 737,529; `NQM22` 530,220 | Cleared values first received June 14 02:37 UTC; five roster contracts lack cleared numeric values. Full causal winner unresolved. |
| September 13 / September 12 | `NQZ22` 367,205; `NQU22` 313,361 | `NQZ22` 485,300; `NQU22` 444,255 | Cleared values first received September 13 02:02 UTC; four roster contracts lack cleared numeric values. Full causal winner unresolved. |

Thus the later *observed* cleared leaders agree with the historical two roll choices among published competitors. They do not prove full-roster retrospective winners or origin-available cleared-volume decisions. The retained Globex ranking uses a different metric and an incomplete contract panel; it remains a provisional separate calculation. The existing `max(volume, contract code)` tie rule is preserved in the machine result, and no missing quantity is ranked as zero.

## Cleared versus Globex OHLCV and coverage limit

The **328** cells with retained positive Globex predecessor volume all have numeric cleared volume. Cleared volume exceeds the retained OHLCV sum in **285**, equals it in **43**, and is lower in **none**. The summed cleared-minus-retained difference over these matched cells is **2,557,299** contracts (median cell difference **424**). These figures compare the same contract and corrected CME trade date; they do not identify the cause. Clearing-only activity, blocks, reporting corrections, or incomplete electronic bars require independent record-level investigation. The retained OHLCV is a lower bound where coverage is uncertain, and cleared volume must not silently replace the metric used by the historical selector.

This acquisition stops at the requested scope. The 505 missing statistics and the absence of all origin-time cleared volumes are material coverage limitations. Dataset/day `available` conditions and successful DBN responses do not certify those missing cells, venue sequence continuity, independent source completeness, or any causal winner. No production selector, certification tier, or HAR fit was changed.
