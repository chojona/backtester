# NQ official CME contract-volume inspection

**Inspection date:** 2026-10-14 (America/New_York)
**Question:** Can free, historical CME reports independently verify the June 13 and September 12, 2022 NQ predecessor-volume rankings, including the full eligible outright roster, at the original 5 p.m. ET forecast origin?

## Decision

**Retrospective contract-ranking evidence: unresolved.** CME publicly indexes a dated daily-volume workbook for each requested date, but neither workbook's bytes or cells were obtainable in this inspection. No 2022 contract-month row, explicit zero, nine-contract coverage, or figure can be attributed to either workbook. The retained Databento three-contract comparisons remain reproducible, not independently corroborated. The current CME Daily Bulletin illustrates that contract-month rows and distinct Globex/cleared-volume fields can exist, but its present-day format cannot establish the 2022 pages' contents. [CME daily-volume archive](https://www.cmegroup.com/ftp/daily_volume/); [current Equity and Index Futures bulletin page 11](https://www.cmegroup.com/daily_bulletin/current/Section11_Equity_And_Index_Futures.pdf).

**Point-in-time causal-ranking evidence: no.** CME describes the Daily Bulletin as updating preliminarily about **12 a.m. CT on the next business day** and finally about **10 a.m. CT that day**. It describes Daily Volume and Open Interest as an end-of-day preliminary report, with official figures the following morning. Neither is evidence that final or preliminary contract-month totals were available at the **June 13 or September 12, 2022, 5 p.m. ET** origins. The archive's file modification times are later than those origins if interpreted in either UTC or U.S. Central time, but the index states **no time zone** and a modification time is neither an original publication time nor a revision history. A time-stamped, as-received all-contract feed is still needed for the original causal rule. [CME Daily Bulletin schedule](https://www.cmegroup.com/market-data/daily-bulletin.html); [CME Volume and Open Interest timing](https://www.cmegroup.com/market-data/volume-open-interest.html).

**Bounded Databento diagnostic: still needed** if the audit is to advance beyond these two unverified public-file links. The previously [quoted `definition` + `statistics` diagnostic](nq-contract-evidence-acquisition-plan.md) can test the historical roster, cleared-volume records, `ts_ref`, and revisions for the 11 raw symbols; it has **not** been ordered here. Even complete retrospective statistics would not by themselves prove what was available by 5 p.m. ET or reconcile cleared volume to Globex OHLCV. No paid retrieval, production or certification change, or HAR fitting occurred.

## Source inventory and preservation

| Requested trade date | Direct public URL | Archive index `Last modified` | File status | SHA-256 |
| --- | --- | --- | --- | --- |
| 2022-06-13 | [daily_volume_20220613.xlsx](https://www.cmegroup.com/ftp/daily_volume/daily_volume_20220613.xlsx) | `2022-06-14 03:21` (index time zone unstated; approximately 68K listed) | Indexed, bytes not retrieved | Not available; no file to hash |
| 2022-09-12 | [daily_volume_20220912.xlsx](https://www.cmegroup.com/ftp/daily_volume/daily_volume_20220912.xlsx) | `2022-09-13 03:31` (index time zone unstated; approximately 68K listed) | Indexed, bytes not retrieved | Not available; no file to hash |

The [CME archive index](https://www.cmegroup.com/ftp/daily_volume/) displayed these two entries on inspection. The direct `.xlsx` URLs produced a fetch error in the web reader; the in-app browser's file download timed out; a sandboxed shell request could not resolve the host; and a direct shell request returned an HTTP/2 error, then timed out under HTTP/1.1 without bytes. No zero-byte placeholder or alleged workbook hash is preserved. The index does not label its time zone or distinguish original publication from a later file replacement. The [historical Daily Bulletin link](https://www.cmegroup.com/market-data/daily-bulletin.html) routes to CME DataMine; a date-specific 2022 equity-page PDF, access terms, revision, and hash were not obtained. The current bulletin URL is mutable and is evidence about its **current** presentation only.

## Exact roster and retained comparison

The roster below comes from the historically effective [CME May 23, 2022 listing-cycle notice](https://www.cmegroup.com/notices/ser/2022/04/SER-8975.pdf) as reconstructed in the [causal universe audit](nq-causal-contract-universe-audit.md) and its [date-level JSON](../results/nq-causal-contract-universe-audit.json). It is an **expected** roster, not a verified June 13 or September 12 report roster or an as-of security-definition snapshot. The volumes are retained Databento one-minute OHLCV predecessor sums; they are not CME report figures. `?` means unknown, never zero.

| Expected NQ outright | June 13 retained Globex OHLCV | September 12 retained Globex OHLCV |
| --- | ---: | ---: |
| NQM22 | 387,941 | Not in expected September roster |
| NQU22 | **610,767** | 313,361 |
| NQZ22 | 268 | **367,205** |
| NQH23 | ? | 135 |
| NQM23 | ? | ? |
| NQU23 | Not in expected June roster | ? |
| NQZ23 | ? | ? |
| NQZ24 | ? | ? |
| NQZ25 | ? | ? |
| NQZ26 | ? | ? |

Each date has **nine expected outrights, three positive retained predecessor volumes, and six unknown volume cells**. June's known ranking is NQU22 > NQM22 > NQZ22, with a **222,826** margin over the nearest known competitor. September's is NQZ22 > NQU22 > NQH23, with a **53,844** margin. These reproduce the retained-panel June 14 and September 13 rolls. They cannot prove either full-universe winner: no bound has been established on the six unknown cells or on potentially missing trades in the three positive cells. The source report values cannot be compared numerically to Databento because no workbook cells or 2022 bulletin pages were retrieved.

## What the report format can and cannot establish

1. **Nine rows and zeros.** The two dated workbook entries prove file names only. Their sheet layout, NQ granularity, all-nine-row coverage, and zero notation are unverified. The [current CME Equity and Index Futures bulletin page](https://www.cmegroup.com/daily_bulletin/current/Section11_Equity_And_Index_Futures.pdf) says its listings include contracts with price/volume activity or established open interest and that eligible but inactive products do not appear. It also uses `----` in fields; this inspection does not equate that mark with a numeric zero. This current-page note gives an additional reason to avoid treating an absent row as zero, but is not proof of the 2022 reporting rule. A positive 2022 row could resolve a retrospective cell in its stated metric; a missing row requires a contemporaneous explicit-zero rule, actual roster evidence, or another independent bound.
2. **Volume scope.** CME says its [exchange daily volume report](https://www.cmegroup.com/market-data/browse-data/exchange-volume.html) summarizes Globex, ClearPort/PNT, and Open Outcry. The **current** bulletin equity-page legend distinguishes Globex electronic-session (ETH) volume from RTH pit/block/cash-for-futures volume and shows a separate `CLEARED` column. It also cautions that volume or open interest may reflect clearing adjustments. Therefore a generic report `volume` number cannot be assumed equal to Databento's Globex trade-generated OHLCV sum. Which columns the **2022** NQ pages or the two workbooks supplied remains unverified. Any eventual numeric comparison must specify the column and CME trade date, separate electronic from cleared/other activity where possible, and investigate differences rather than force equality. [Current CME bulletin page 11](https://www.cmegroup.com/daily_bulletin/current/Section11_Equity_And_Index_Futures.pdf).
3. **Retrospective use.** A retrieved, hashed, date-specific official bulletin with explicit NQ month rows could independently test retrospective **cleared-volume** ranking. It would resolve missing cells only if it reports a numeric value or explicit zero for each eligible outright, or supplies a defensible upper bound and verifies the entire effective roster. A contract-month report covering fewer than nine rows without a zero rule cannot close the six unknowns. A product-level daily-volume workbook cannot rank contract months even if the product total is accurate. The present public index establishes neither case.
4. **Origin use.** The CME schedule and index timing provide no 5 p.m. ET availability proof for these 2022 totals. Even a later exact match to Databento would be a retrospective check. A causal replay needs contract definitions and volume messages demonstrably received by each 5 p.m. ET cutoff, with completeness and correction evidence, or a separately preregistered later forecast origin and corresponding target window.

## Remaining evidence gap

For June 13 the unknown expected volumes are **NQH23, NQM23, NQZ23, NQZ24, NQZ25, NQZ26**. For September 12 they are **NQM23, NQU23, NQZ23, NQZ24, NQZ25, NQZ26**. Neither actual nine-outright venue book nor any explicit zero has been verified from the inspected reports. Both corresponding full-universe roll rankings and both 5 p.m. ET causal rankings remain unresolved. Within the wider 120-date audit, the [acquisition plan](nq-contract-evidence-acquisition-plan.md) still counts **752 unknown eligible predecessor-volume cells**; this two-date inspection clears none of them.

The practical next evidence step is to obtain readable, date-specific 2022 CME material with the NQ month rows, its historical reporting notes, release/revision trail, and file hashes, then compare its clearly named Globex and/or cleared fields to the retained sums. If public access remains unavailable, the already bounded Databento `definition`/`statistics` quote remains the smallest identified diagnostic. Its result must still be tested against the original as-of cutoff and electronic-volume scope before any roll or research decision changes.
