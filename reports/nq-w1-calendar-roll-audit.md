# NQ W1 calendar and causal roll evidence audit

**Audit date:** 2026-10-14 (America/New_York). **Disposition:** W1 remains blocked. The retained evidence reproduces every reviewed causal winner, but it does not prove the three proposed holiday closures or adjudicate the isolated minute holes. This is an evidence audit; no tier, estimator, or historical source was changed, no HAR was fit, and no paid data was requested.

## Basis and evidence standard

The audit uses the [W1 recovery manifest](../results/nq-recovery-candidate-windows.json), [Phase 3 decisions](../results/databento-nq-full-history/phase3-v3.0.0/certification-by-session.csv), [retained outright OHLCV](../results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet), and the [acceptance selector](../scripts/accept_nq_history.py). The [machine-readable blocker matrix](../results/nq-w1-blocker-matrix.json) records all 15 guards, all 20 incomplete roll decisions plus the boundary predecessor, every candidate-contract retained volume, proposed UTC grids, uncertainty, and run calculations. All intervals below are half-open; the stated timestamp is a minute **start**.

The [CME Globex notice effective for trade date 2021-06-28](https://www.cmegroup.com/notices/electronic-trading/2021/06/20210621.html) establishes 17:00–16:00 CT trading and 16:00–17:00 CT daily maintenance, and removes the 15-minute equity pause. Its [affected-product attachment](https://www.cmegroup.com/content/dam/cmegroup/notices/electronic-trading/2021/06/cme-equity-index-futures-options.pdf) includes NQ. Thus the **ordinary candidate** for a 2022 NQ trade date is prior calendar day 18:00 through trade date 17:00 New York time, or 1,380 minutes, with maintenance 17:00–18:00 ET. During EDT, the corresponding UTC boundaries are 22:00 previous day, 21:00 trade date, and next 22:00 reopen; during EST they are 23:00 previous day, 22:00 trade date, and next 23:00 reopen. The evening reopening belongs to the **next trade date** under this ordinary convention. This regime evidence is not a dated exception schedule.

The [CME archived 2022 Globex holiday index](https://www.cmegroup.com/content/cmegroup/cn-s/tools-information/holiday-calendar.html) points to the dated [Juneteenth](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-juneteenth-holiday-schedule.xls), [Independence Day](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-independence-day-holiday-schedule.xls), and [Labor Day](https://www.cmegroup.com/tools-information/holiday-calendar/files/2022-labor-day-holiday-schedule.xls) product schedules. These are the authoritative *candidate documents*, not verified NQ rows. The web reader returned `400 Unsupported content-type: application/vnd.ms-excel` for all three; the in-app browser blocked the Juneteenth file; direct retrieval failed DNS resolution. Their bytes, product rows, document revisions, and actual NQ close/reopen conventions were not obtained. The index alone, the ClearPort/floor tables on that page, and CME settlement notices do **not** establish NQ Globex hours. The exact holiday exception schedule therefore remains **unverified**.

## Proposed expected-minute grid

For each ordinary or guarded date, the proposal starts from the 1,380-minute ordinary grid above. The 15 guarded dates and per-date UTC start/end, maintenance, observed bars, and uncertainty are enumerated in the JSON matrix. None is certified from the guard label alone. The three exceptional alternatives are:

| Trade date | Ordinary active UTC | Retained selected bars | Proposed holiday grid **if NQ row confirms 13:00 ET close** | Exact unresolved question |
|---|---|---:|---|---|
| 2022-06-20 | Jun 19 22:00–Jun 20 21:00 | 1,140 NQU22 | Active until Jun 20 17:00 UTC; closed 17:00–21:00 UTC; ordinary maintenance 21:00–22:00 UTC; proposed reopen Jun 20 22:00 UTC for Jun 21 trade date | NQ-specific close, reopen, status of 240 minutes, trade-date assignment |
| 2022-07-04 | Jul 3 22:00–Jul 4 21:00 | 1,140 NQU22 | Active until Jul 4 17:00 UTC; closed 17:00–21:00 UTC; ordinary maintenance 21:00–22:00 UTC; proposed reopen Jul 4 22:00 UTC for Jul 5 trade date | Same, from Independence Day NQ row |
| 2022-09-05 | Sep 4 22:00–Sep 5 21:00 | 1,140 NQU22 | Active until Sep 5 17:00 UTC; closed 17:00–21:00 UTC; ordinary maintenance 21:00–22:00 UTC; proposed reopen Sep 5 22:00 UTC for Sep 6 trade date | Same, from Labor Day NQ row |

For all three, 13:00–17:00 EDT is **17:00–21:00 UTC**, exactly the retained 240-minute shortfall. This is a strong pattern, but **not proof** of scheduled closure. Do not subtract the 720 minutes from an authoritative grid until the NQ rows and any revisions are read. The proposed 18:00 EDT reopen is likewise conditional on those rows. If confirmed, each shortened trade date would have 1,140 expected minutes; if the ordinary schedule applied, each would have 1,380 and the 240 minutes would need independent trade/status/completeness evidence.

The other **12 guarded dates** are 2022-06-21/22, 07-05/06, 09-06/07, 10-10/11/12, and 11-09/10/11. Each selected contract has **1,380/1,380** ordinary candidate minutes, with no selected off-grid minute. The first six adjoin the three named holiday windows, while the October and November groups arise from the conservative federal/adjacent-day guard; the CME index does not list those as 2022 Globex holiday schedule windows. Full bars support the ordinary proposal but do not prove absence of a changed NQ open, pause, close, or trade-date rule. Review each against dated CME NQ hours before releasing its guard. The JSON attaches the exact per-date UTC interval and an explicit unresolved evidence state to every row.

Four ordinary candidate gaps remain: Jul 27 03:56–03:57 UTC (`NQU2`), Aug 16 04:43–04:44 UTC (`NQU2`), Aug 18 04:42–04:43 UTC (`NQU2`), and Oct 12 22:48–22:49 UTC for the Oct 13 trade date (`NQZ2`). These are active under the ordinary proposal. OHLCV silence does not distinguish a no-trade minute, delivery loss, or exchange interruption. The boundary predecessor June 6 has a further selected NQM22 gap at **June 5 23:27–23:28 UTC**. Each needs independent minute-status/trade or provider-completeness evidence if the dated grid still expects it.

## Causal contract review

The acceptance rule takes the **previous completed observed trade session's** retained volume for contracts present on the current date, with contract code as tie breaker. I independently summed the retained Parquet by trade date and contract and reapplied this rule for all 20 incomplete W1 decisions and June 6, the predecessor of the June 7 boundary. In all **21/21** comparisons, the recomputed retained winner equals the saved selection; **0/21** are actual contract switches and **0/21** are roll-rule disagreements. This is reproducibility of the retained panel, not proof of complete market volume for each candidate. Thin deferred contracts have fewer bars than the selected contract, so their true complete volume is not established from retained OHLCV alone.

| Decision date | Causal predecessor | Retained winner volume | Next volume | Precise failed predecessor dependency |
|---|---|---:|---:|---|
| Jun 06 boundary review | Jun 03 | NQM22 641,540 | NQU22 1,514 | Full selected grid; ordinary date review remains provisional. |
| Jun 07 | Jun 06 | NQM22 531,252 | NQU22 2,933 | NQM22 missing June 5 23:27 UTC minute, outside W1. |
| Jun 21 | Jun 20 | NQU22 130,346 | NQZ22 87 | Holiday NQ grid; 240 candidate minutes absent. |
| Jun 22 | Jun 21 | NQU22 516,942 | NQZ22 205 | Guarded predecessor; full ordinary grid. |
| Jun 23 | Jun 22 | NQU22 626,659 | NQZ22 366 | Guarded predecessor; full ordinary grid. |
| Jul 05 | Jul 04 | NQU22 79,315 | NQZ22 52 | Holiday NQ grid; 240 candidate minutes absent. |
| Jul 06 | Jul 05 | NQU22 704,544 | NQZ22 398 | Guarded predecessor; full ordinary grid. |
| Jul 07 | Jul 06 | NQU22 641,910 | NQZ22 310 | Guarded predecessor; full ordinary grid. |
| Jul 28 | Jul 27 | NQU22 623,675 | NQZ22 585 | NQU22 has one unexplained minute hole. |
| Aug 17 | Aug 16 | NQU22 550,629 | NQZ22 460 | NQU22 has one unexplained minute hole. |
| Aug 19 | Aug 18 | NQU22 520,545 | NQZ22 557 | NQU22 has one unexplained minute hole. |
| Sep 06 | Sep 05 | NQU22 132,330 | NQZ22 1,280 | Holiday NQ grid; 240 candidate minutes absent. |
| Sep 07 | Sep 06 | NQU22 752,452 | NQZ22 5,076 | Guarded predecessor; full ordinary grid. |
| Sep 08 | Sep 07 | NQU22 667,355 | NQZ22 5,839 | Guarded predecessor; full ordinary grid. |
| Oct 11 | Oct 10 | NQZ22 746,649 | NQH23 382 | Guarded predecessor; full ordinary grid. |
| Oct 12 | Oct 11 | NQZ22 822,278 | NQH23 447 | Guarded predecessor; full ordinary grid. |
| Oct 13 | Oct 12 | NQZ22 722,611 | NQH23 431 | Guarded predecessor; full ordinary grid; current date also has its own minute hole. |
| Oct 14 | Oct 13 | NQZ22 1,033,416 | NQH23 958 | NQZ22 has one unexplained minute hole. |
| Nov 10 | Nov 09 | NQZ22 653,941 | NQH23 682 | Guarded predecessor; full ordinary grid. |
| Nov 11 | Nov 10 | NQZ22 838,935 | NQH23 1,403 | Guarded predecessor; full ordinary grid. |
| Nov 14 | Nov 11 | NQZ22 674,991 | NQH23 1,140 | Guarded predecessor; full ordinary grid. |

The JSON also includes **all** contracts present today, including lower-volume later quarters omitted from the compact table, their prior observed minute counts, and their missing minutes against the ordinary grid. No current or future session volume was used to select a contract. After a predecessor's calendar and selected-minute evidence clears, the retained comparison can clear the corresponding *existing Phase 3 causal gate* offline if the source-integrity assumption remains valid. An independent assertion of complete **all-candidate** market volume would need more source evidence, especially for thin candidates; a large retained margin is reassuring but not a formal completeness bound.

## Recovery decision and 120-session test

**Offline now:** enumerate all dependencies, recompute winners, verify retained hashes and panel membership, generate ordinary/conditional grids, and propagate decisions *after* independent evidence arrives. Nothing in the current panel establishes a holiday closure or resolves an absent active minute.

**External authoritative evidence:** read the dated NQ rows and revisions in the three linked CME workbooks; verify their actual open, close, reopen, maintenance, and trade-date conventions. Review the other 12 guards against dated NQ schedules. To promote ordinary Tier B dates to strict A, the source review must cover their individual dates as well. These are schedule tasks, not reasons to buy trades now.

**Additional data if no other independent source is available:** the four W1 active-minute holes and June 6 boundary hole need trade/status/sequence or provider completeness evidence; any of the 720 holiday-pattern minutes still active under the verified NQ rows would also need it. Retained OHLCV and dataset-day `AVAILABLE` conditions cannot resolve these. Only after the calendar grid is fixed should any Databento scope be priced, and no paid retrieval is authorized by this audit.

The 120 observed W1 rows are 92 B and 28 C, with no unknown intervening weekday. Under the unchanged A/B eligibility rule, the longest current W1 run is **21 sessions** (Sep 9–Oct 7). Hypothetically clearing only the four isolated W1 gaps leaves it **21**; clearing all seven sparse sessions while leaving guard propagation unresolved also leaves **21**; clearing all 15 guards alone yields **24** (Sep 9–Oct 12). Only the extreme hypothetical where **all 28 C rows**, including the June 7 boundary dependency and roll propagation, clear yields **120** (Jun 7–Nov 21). These are upper-bound scenario counts, not recertified sessions.

**Independent 120-session blocker:** the June 7 decision depends on June 6's missing NQM22 minute, which is outside W1. Thus even if all four isolated W1 gaps and all three holiday-pattern shortfalls were resolved, W1 cannot reach 120 without adjudicating that predecessor. The 12 guarded full-grid dates and their downstream roll decisions are additional blockers until their NQ schedules are reviewed. This audit does not classify any of those failures as an actual wrong roll; it classifies them as missing causal evidence.
