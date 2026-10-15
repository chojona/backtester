# NQ W1 final calendar evidence and retrieval readiness

**Prepared:** 2026-10-14. **Decision:** **GO to request user authorization for the unchanged five-gap `trades`/`status` batch; NO-GO for recertification or historical HAR fitting.** No paid market data was retrieved. Certification tiers, production estimators, original OHLCV, and historical HAR artifacts were not changed. The non-certifying [120-date candidate](../results/nq-w1-120-session-candidate.json) was updated only to correct the May 31 → June 1 causal boundary and include the recovered Memorial workbook.

## Source register and strength

The [CME 2022 Globex holiday archive](https://www.cmegroup.com/content/cmegroup/cn-s/tools-information/holiday-calendar.html) links the original `.xls` schedules for Memorial Day, Juneteenth, Independence Day, and Labor Day. The preserved files below have OLE/BIFF signatures and unchanged binary hashes. Their visible `A1` update text and OLE last-saved metadata agree on the revision date; the OLE creation time is a reused 2013 template timestamp and is not publication evidence. The workbooks establish their own listed holiday windows, but do not prove a complete earlier/later revision history. CME warns that holiday hours may change.

| Original CME Globex source | Visible update; OLE last saved | SHA-256 | Applicable evidence |
| --- | --- | --- | --- |
| [Memorial Day](evidence/cme-2022/2022-memorial-day-holiday-schedule.xls) ([CME link](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-memorial-day-holiday-schedule.xls)) | `Updated 5/18/2022`; 2022-05-18 17:57:02 | `0d1b1f89a315cae22a5857a7027a514e3086c1cccfee42fddddff3caba0c2230` | `Equity Products` A5; trade-date header D2; G5/H5, O5/S5/T5; note A74 |
| [Juneteenth](evidence/cme-2022/2022-juneteenth-holiday-schedule.xls) ([CME link](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-juneteenth-holiday-schedule.xls)) | `Updated 5/18/2022`; 2022-05-18 16:54:29 | `bc9f2caf26a73a13029f177fcc6468bdc8662899ff935f44329ee1a95c8b667b` | A5; D2; G5/H5, O5/P5/T5; note A76 |
| [Independence Day](evidence/cme-2022/2022-independence-day-holiday-schedule.xls) ([CME link](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-independence-day-holiday-schedule.xls)) | `Updated 6/29/2022`; 2022-06-29 17:46:27 | `1ea0459d8aa0fd7ec5147614855f6d0d43607efefdc3aa9c6b1e18ddbfd54fde` | A5; D2; G5/H5, N5/R5/S5; note A75 |
| [Labor Day](evidence/cme-2022/2022-labor-day-holiday-schedule.xls) ([CME link](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-labor-day-holiday-schedule.xls)) | `Updated 6/29/2022`; 2022-06-29 17:34:49 | `28d533f25d1af74af043e411635f1933fd4ff6359c80c049f87f019d2f1d57d0` | A5; D2; G5/H5, O5/S5/T5; note A74 |

The source files were read through a temporary `.xlsx` conversion for cell inspection; the preserved `.xls` bytes were not converted or rewritten. The `Equity Products` A5 row applies to plain NQ futures; A8's TACO E-mini Nasdaq exception is a different product. CME's [2021 equity-hours notice](https://www.cmegroup.com/notices/electronic-trading/2021/06/20210621.html) identifies NQ among affected products and sets ordinary Sunday–Friday trading **17:00–16:00 Central**, with **16:00–17:00 Central maintenance** and the former 15-minute pause removed. The preserved workbooks override that ordinary rule only where their product row supplies holiday events.

The archive's 2022 **Globex** list contains Memorial, Juneteenth, Independence Day, Labor Day and other named holiday windows, but no Columbus Day or Veterans Day Globex workbook. Contemporaneous CME [Columbus Day clearing advisory](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-columbus-day-advisory.pdf), [Veterans Day clearing advisory](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-veterans-day-advisory.pdf), and [Columbus settlement notice](https://www.cmegroup.com/tools-information/holiday-calendar/files/columbus-day-holiday-settlement-times-2022.pdf) refer to clearing/settlement processing and the holiday calendar; they do **not** state NQ Globex opens, closes, or trade-date labels. Direct binary access to those PDFs was blocked (CME returned HTTP 403 or timed out), so no local PDF bytes, hashes, or revision metadata are asserted. The current archive's other tabs also expose stale 2021 PDF links under 2022 headings; they were not treated as 2022 trading schedules. A dated NQ-specific October/November schedule or CME historical reference-data response remains outstanding.

## Verified holiday boundaries and UTC conversion

The four original workbooks use **Central Time**. For these dates Central is CDT (UTC−5), and New York is EDT (UTC−4). `Pre-opening` permits orders but is not an active trading minute. All intervals below are half-open UTC minute starts; the 17:00–22:00 UTC Monday window is the workbook's five-hour halt/pre-open, not an ordinary maintenance interval.

| Official CME trade date | First active UTC segment | Monday halt/pre-open UTC | Second active UTC segment | Selected bars / expected |
| --- | --- | --- | --- | ---: |
| Tue **May 31** | May 29 22:00–May 30 17:00 | May 30 17:00–22:00 | May 30 22:00–May 31 21:00 | NQM22 **2,520/2,520** |
| Tue **Jun 21** | Jun 19 22:00–Jun 20 17:00 | Jun 20 17:00–22:00 | Jun 20 22:00–Jun 21 21:00 | NQU22 **2,520/2,520** |
| Tue **Jul 5** | Jul 3 22:00–Jul 4 17:00 | Jul 4 17:00–22:00 | Jul 4 22:00–Jul 5 21:00 | NQU22 **2,520/2,520** |
| Tue **Sep 6** | Sep 4 22:00–Sep 5 17:00 | Sep 5 17:00–22:00 | Sep 5 22:00–Sep 6 21:00 | NQU22 **2,520/2,520** |

Each trade-date header D2 and its day-order note assign the Sunday/Monday activity to the **Tuesday** trade date. Memorial's May 30 retained label is therefore remapped to May 31 for this research audit. There are zero missing, duplicate, or off-grid selected bars in its two segments. Its A75 note calls June 1 “Tuesday,” although June 1, 2022 was Wednesday; D2 and A74 unambiguously identify the May 31 holiday trade date, and the note's weekday is not used as a boundary rule. The analogous Juneteenth note typo about June 22 was already documented in the [original-workbook review](nq-2022-cme-holiday-evidence.md).

## Remaining guarded dates versus candidate grids

The holiday workbooks stop on their named Tuesdays. For their following Wednesdays, the candidate applies CME's ordinary NQ rule: previous date 17:00 CT (22:00 UTC in daylight time) through current date 16:00 CT (21:00 UTC), with the 16:00–17:00 CT maintenance hour between trade dates. The October dates use the same daylight-time conversion. November 9–11 are after the DST change, so 17:00–16:00 CST converts to **23:00–22:00 UTC**, with maintenance **22:00–23:00 UTC**. Each ordinary session is 1,380 minutes and has no ordinary intraday halt under the 2021 NQ notice.

| Date(s) | Candidate active UTC intervals | Retained selected bars | Source-level assessment |
| --- | --- | --- | --- |
| Jun 22 | Jun 21 22:00–Jun 22 21:00 | NQU22 1,380/1,380 | Follows Jun 21's documented regular close; ordinary-rule continuation, no separate dated Jun 22 NQ sheet |
| Jul 6 | Jul 5 22:00–Jul 6 21:00 | NQU22 1,380/1,380 | Follows Jul 5 holiday sheet; ordinary-rule continuation, no separate dated Jul 6 NQ sheet |
| Sep 7 | Sep 6 22:00–Sep 7 21:00 | NQU22 1,380/1,380 | Follows Sep 6 documented regular close; ordinary-rule continuation, no separate dated Sep 7 NQ sheet |
| Oct 10–12 | Oct 9 22:00–Oct 10 21:00; Oct 10 22:00–Oct 11 21:00; Oct 11 22:00–Oct 12 21:00 | NQZ22 1,380/1,380 each | No 2022 Globex exception workbook in archive; clearing/settlement notices are not NQ hours evidence |
| Nov 9–11 | Nov 8 23:00–Nov 9 22:00; Nov 9 23:00–Nov 10 22:00; Nov 10 23:00–Nov 11 22:00 | NQZ22 1,380/1,380 each | No 2022 Globex exception workbook in archive; clearing notice is not NQ hours evidence |

The retained timestamps support every proposed ordinary interval with zero new missing, duplicate, or off-grid selected bars. They cannot independently prove that no unarchived or revised date-specific NQ exception applied. Therefore the nine dates remain **calendar-provisional** for recertification. No newly introduced active-minute gap or changed trade-date identity was found under the sourced ordinary-plus-holiday candidate rule; this is a conditional finding for October and November.

## Date count and corrected causal chain

From June 2 through November 21 inclusive there are **123 civil weekdays**. The Juneteenth, Independence Day, and Labor Day workbooks remove three separate Monday trade-date identities (June 20, July 4, September 5), leaving **120 candidate CME trade-date identities** with no unobserved intervening weekday. Memorial removes May 30 outside the interval, so the 120 count and the June 2 first date do not change. The nine still-guarded identities cannot be called fully official-confirmed until their date-specific evidence gate is cleared.

The causal predecessor for June 1 is now the **combined May 31** CME trade date. Retained May 30 + May 31 volume for contracts present June 1 is **NQM22 821,154**, **NQU22 1,785**, **NQZ22 39**. The prior candidate used May 31's calendar-labeled portion alone (**694,323 / 1,225 / 26**), so those predecessor totals were incomplete even though the winner was the same. June 1 selected NQM22 has **1,380/1,380** ordinary candidate bars and volume **672,372**; it wins June 2 against NQU22 **1,922** and NQZ22 **15**. Thereafter June 2 → June 3 → June 6 → June 7 and all 120 internal decisions use the prior completed corrected date. A direct replay found **zero changed selected winners**; the roll switches remain June 14 to NQU22 and September 13 to NQZ22. Every date's ranking is retained in the updated candidate JSON. The May 31 source-volume total and June 1 grid are now supported by the Memorial workbook, but complete exchange volume for every candidate contract is a separate gate.

## Five-gap retrieval readiness

The active-minute comparison still finds exactly these five one-minute holes: **June 5 23:27–23:28 UTC (`NQM2`, June 6 trade date); July 27 03:56–03:57 (`NQU2`); August 16 04:43–04:44 (`NQU2`); August 18 04:42–04:43 (`NQU2`); October 12 22:48–22:49 (`NQZ2`, October 13 trade date).** The raw symbol, inclusive-start/exclusive-end `trades` minute, and session-open-through-gap `status` interval in the candidate JSON are **unchanged**. Memorial's remapping changes only the external June 1 volume boundary, not any of these five request scopes. Under the user's condition to requote **if a scope changes**, no new quote was required. The existing authenticated metadata-only batch quote, obtained 2026-10-14 20:38:02 UTC, is **$0.000777244568 estimated** for ten requests (31,520 estimated billable bytes, 665 estimated records). The one-minute `trades` estimates equaled their aligned ten-minute estimates; actual billing follows delivered bytes and the quote is not an invoice cap. [Databento Historical cost method](https://databento.com/docs/api-reference-historical).

The proposed `status` windows start at each candidate session open, allowing a preceding halt/pause update to be seen. If October 12's still-provisional boundary were later contradicted by a dated schedule, the October 13 status start would need review and the batch re-quoted before any paid call. A zero-trade response plus active status would explain a missing OHLCV bar within Databento's stream, but would not alone certify exchange-level completeness.

## Separate gates and recommendation

**Calendar:** Four original holiday workbooks prove their Tuesday assignments, active segments, halts and reopens; May 31 now repairs the external predecessor. The nine guarded ordinary dates still lack direct date-specific NQ schedule or historical CME reference-data confirmation. The 2022 archive's omission is useful but not a substitute for a positive exchange record or an auditable rule-plus-exception inventory. Calendar certification remains **NO-GO**.

**Minute coverage:** The candidate has **169,015/169,020** selected active bars, with only the five isolated gaps above. The ten bounded `trades`/`status` requests are a controlled way to investigate them. If the returned streams are incomplete, request venue-sequence or independent-provider corroboration rather than imputing bars. Minute-coverage recertification remains **NO-GO until evidence is reviewed**.

**Causal source volume:** Independently verify that retained predecessor volume totals represent complete eligible outright contract volume for every contract in the current-day candidate universe, especially the May 31 boundary, holiday-combined dates, June 14 and September 13 roll decisions, and successors of sparse days. The five-gap request batch is not designed to prove all-session volume completeness or all thin-contract absence. Retained-panel margins show stable winners, but this gate remains **separately open**.

**Authorization recommendation: GO to ask the user to authorize only the ten exact, bounded paid requests already listed in the candidate JSON, using the $0.000777244568 estimate as a planning figure.** The scopes remain valid under the current documented grid and produce useful evidence even while the October/November calendar and source-volume gates remain open. This recommendation is **not authorization to execute**. A recertification decision and any historical HAR fit remain **NO-GO** until all three gates are resolved, a new versioned review is made, and the preregistered uninterrupted 120-session requirement is met.

## Checks

The updated offline builder revalidated all 120 candidate grids, five exact gaps, corrected May 31/June 1 volumes, 120 selected winners, and the preserved quote scopes. The prior holiday-candidate suite passed **8 tests**. No paid `timeseries.get_range` call, tier promotion, production-estimator edit, or HAR fit was performed.
