# Calendar source review — 2026-10-05

This is an authored review note, not an archived copy of the exchange documents.
Direct file downloads returned HTTP 403; sources were read through the web reader.

CME SER-8788 (June 11, 2021), section 3, removes the 15-minute afternoon
pause for affected equity index products from trade date June 28, 2021.
Source: https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2021/06/SER-8788.pdf
The electronic trading notice identifies the affected products:
https://www.cmegroup.com/notices/electronic-trading/2021/06/20210621.html

CME's 2026 holiday index places Labor Day schedules on September 6–8,
and Columbus Day on October 12. The September 14–25 validation trading dates
are outside those holiday windows. This bounded schedule uses ordinary Globex
hours, 18:00–17:00 America/New_York, and cash-session RTH 09:30–16:00.
No scheduled intraday pause is included. The daily 17:00–18:00 maintenance
closure and weekends are explicit engine conventions. Unscheduled emergency
halts are not independently certified by this review.
Source: https://www.cmegroup.com/trading-hours.html

The NQ product page confirms $20 per index point and minimum tick 0.25,
therefore $5 per tick. This cross-check does not replace contract definitions.
Source: https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.contractSpecs.html
