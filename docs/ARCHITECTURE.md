# Intraday research engine — implementation and validation

The existing `engine.py` daily backtester and its seven tests are preserved. Its original command implementation lives in `daily_cli.py`; `__main__.py` dispatches the new commands and retains the old command behavior.

## Architecture

`data.py` provides an abstract data provider, immutable OHLCV bars, a CSV adapter and integrity checks. `instruments.py` centralizes contract economics. `sessions.py` identifies trading dates and session segments in New York time while storing bar times in UTC. `rolls.py` selects executable constituent contracts and makes causal continuous research prices. `features.py` streams VWAP, ATR and point-in-time levels. `profile.py` defines volume-profile provenance interfaces without estimating exchange volume-at-price from candles.

`strategy.py` defines lifecycle callbacks with frozen, prefix-only history, features, position, account and order snapshots. `execution.py` owns orders and fill assumptions. `risk.py` controls entry eligibility and integer sizing. `portfolio.py` owns futures accounting and excursions. `intraday.py` processes the chronological loop. `research.py` discovers events causally and labels their future outcomes in a separate offline pass. `reports.py` persists inputs, assumptions, metrics and audit artifacts. `cli.py` assembles a reproducible run.

This is a trusted Python research API, not a security sandbox for hostile strategy code. A strategy given external data or using Python introspection could defeat the intended capability boundaries; built-in strategies receive no provider, future list or engine reference.

## Data and timestamps

CSV columns: `timestamp,open,high,low,close,volume`, with optional `contract,symbol,trade_count,bid_volume,ask_volume,open_interest`. A dated constituent contract is mandatory in each row or through `--contract`. Naive timestamps are rejected; timestamps must include an offset. The timestamp labels the **open** of a 1-minute or 5-minute bar. Features and research events become available at the end of that bar.

Validation rejects nonfinite prices/volume, negative volume/optional counts, impossible OHLC, wrong contract roots, duplicate or overlapping bars, descending timestamps, mixed intervals within a contract, timestamps off the interval grid and bars crossing a session boundary or scheduled halt. Negative finite futures prices are allowed. Off-tick prices are flagged; the run rejects them unless explicitly accepted. Provider input must be raw contract prices; preadjusted continuous data is rejected by configuration.

Gaps are counted only in scheduled tradable intervals, not maintenance breaks/weekends/explicit closures. The CLI checks the selected active series separately from inactive-contract coverage. Missing active bars require `--allow-missing`. No bars are interpolated. Research windows with gaps, closures or rolls are censored. Beginning/ending dataset coverage cannot establish complete sessions by inference.

Future tick and subminute adapters can use the provider boundary, but trade/tick events and subminute CSV CLI support are not implemented. No higher-frequency data is made from daily candles.

## Contracts and sources

| Root | Exchange | Tick size | Tick value USD | Point value USD |
|---|---|---:|---:|---:|
| ES | CME | 0.25 | 12.50 | 50 |
| MES | CME | 0.25 | 1.25 | 5 |
| NQ | CME | 0.25 | 5.00 | 20 |
| MNQ | CME | 0.25 | 0.50 | 2 |
| GC | COMEX | 0.10 | 10.00 | 100 |
| MGC | COMEX | 0.10 | 1.00 | 10 |

Outright contracts only. Constants verified against [CME ES FAQ](https://www.cmegroup.com/trading/equity-index/eminifaq.html), [CME Micro E-mini FAQ](https://www.cmegroup.com/articles/faqs/micro-e-mini-equity-index-futures-frequently-asked-questions.html), [CME NQ](https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.html), [CME MNQ](https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html), [CME Gold fact card](https://www.cmegroup.com/content/dam/cmegroup/market-regulation/files/gold-futures-and-options-fact-card.pdf), and [CME Micro Gold overview](https://www.cmegroup.com/education/lessons/micro-gold-and-micro-silver-futures-product-overview). Spread contracts can have different tick rules and are not covered.

## Sessions and trading dates

Default ETH runs from 18:00 ET the preceding calendar day to 17:00 ET on the trading date, Monday–Friday trading dates. Sunday evening belongs to Monday. Friday evening and weekends are closed. Daily 17:00–18:00 maintenance is excluded. Equity templates additionally exclude 16:15–16:30 ET. All clocks use `zoneinfo` New York DST rules, not fixed UTC offsets.

Equity RTH is the requested research window 09:30–16:00 ET. Gold has its own configurable **research RTH convention** of 08:20–13:30 ET, not the equity window or a claim of restricted Globex trading hours. Its Globex ETH template is 18:00–17:00 ET, with no equity afternoon halt. Gold and Micro Gold do not inherit the 24/7 schedule of the separate 1-ounce gold product.

Segments are `OVERNIGHT` (ETH open to RTH open), `RTH`, and `POST_RTH`. `minutes_from_session_open` / `minutes_to_session_close` refer to the whole ETH trading day. Additional `minutes_from_segment_open` / `minutes_to_segment_close` refer to the named segment. All bar offsets describe the bar open.

Calendar configuration is external to strategy logic. Dated overrides support full closures, early ETH/RTH closes and replacement intraday halt lists. The template does **not** bundle a certified historical holiday calendar or unscheduled circuit-breaker halts. Supply the appropriate dated schedule for the research period. Sources: [CME trading-hours and holidays](https://www.cmegroup.com/trading-hours.html) and the instrument pages above. Research runs display the calendar source; missing schedules remain an explicit limitation.

Session-start callbacks occur after the first observed bar closes; no opening print is available before it is observed. End callbacks receive only the last completed context, with `trading_date_end` or `dataset_end` reason. A dataset ending midway through a session is not a complete session.

## VWAP, levels and volatility

VWAP is cumulative `sum(configured_price * volume) / sum(volume)`, with `typical=(H+L+C)/3`, close or OHLC4 basis. Zero-volume bars do not change VWAP; a bucket with no volume returns null. Session VWAP resets at ETH trading-date rollover. RTH VWAP resets at RTH/trading-date boundaries. Overnight VWAP accumulates only the pre-RTH overnight segment and stays frozen afterward. Weekly VWAP resets with the Monday trading date, starting Sunday evening.

These are **bar-derived VWAP approximations**, not exact trade-level VWAP. Complete flags mean the prefix from the relevant start has been observed without a scheduled-bar gap. Default weekly research requires complete weekly warmup; a dataset starting Monday at 09:30 has not observed the Sunday-night start. `--allow-partial-warmup` explicitly relaxes this and is recorded in metadata.

PDH/PDL/PDC default to the immediately preceding trading date's **completed RTH** high/low/last bar close. PDC is not official settlement. Missing or partial prior RTH produces null. Missing an entire trading date does not relabel older levels as yesterday. ONH/ONL are developing during a complete overnight prefix and frozen at RTH open; incomplete overnight coverage produces null. Session and RTH opens require the exact opening bar.

Final IBH/IBL are null until the configurable first RTH window (60 minutes default) is fully observed. Developing IB fields are separately labelled. A missing IB bar leaves final IB null. IB duration must align to the data interval. ATR is a simple rolling average of true range over 14 completed bars by default, with null before warmup. ATR does not fill missing data.

Features are in the **research-series price coordinates**. Orders must be in the active raw contract coordinates; the strategy account snapshot contains the current scale/offset for conversion. Raw execution never uses adjusted feature prices as fills automatically.

## Rolls

Dated contracts and continuous series are distinct. A multi-contract panel must include explicit expiration dates for every constituent. Expiration metadata is supplied externally; equity quarterly expiry and gold delivery/first-notice rules are not guessed.

`fixed` rolls at the first observed bar of the trading date at/after `expiration - days_before_expiration`, using calendar days. `volume` switches to the next expiration when its previous completed trading-session volume exceeds the old contract. `open_interest` compares point-in-time OI snapshots available in the prior completed session. Liquidity rules require complete, matching old/new coverage; they never inspect current-session volume or final volume from the future. Users must ensure OI values reflect their publication time, not retrospectively attached end-of-day information.

Every transition needs paired old/new opens at the same timestamp. Missing paired prices fail explicitly. Records include active old/new contracts, roll timestamp, policy, opens and gap. Contracts cannot change silently. Selection moves forward through expiration order, never rolls backward. An active contract past a supplied expiry fails.

Research transforms are explicitly `forward_additive`, `forward_ratio`, or `unadjusted_reset`. Forward additive accumulates offsets so the new adjusted open equals the old adjusted open at the roll, without modifying any past bar. Forward ratio similarly updates a positive-price scale. Unadjusted mode resets price indicators/levels on a roll. Ratio transforms reject zero/negative roll prices.

`retrospective_back_adjust()` can export classic final additive or ratio-adjusted histories **offline only**. These histories depend on later roll gaps and are not supplied to strategy callbacks or event discovery. There is no silent final-history back-adjustment in a causal run.

Execution defaults to flattening at the paired old-contract open. `reopen` closes old, reopens new and translates stops/targets by the raw gap. Both legs charge configured fees/slippage. Reopening is subject to entry risk/time/margin controls and can be rejected. Roll trades are reported separately and count toward trade metrics/entry limits. Roll fills use assumed synchronous-open liquidity, not volume participation for the old contract; the report records that limitation. Research horizons crossing a roll are censored.

## Orders, fills and accounting

Market, limit and stop orders carry submitted time, side, integer quantity, price, state, fill data, costs and contract. Supported states include pending, filled, partially filled, cancelled, rejected and expired. Strategies submit after bar close; orders cannot fill the bar that generated them. DAY orders expire when the trading date changes; unresolved orders expire at dataset end. GTC protection may cross trading dates.

Market orders fill the next eligible bar's open with adverse configured slippage. Stop orders trigger on a bar range crossing and use the worse of trigger and opening price before slippage; gaps cannot magically fill at the original trigger. Triggered stop remainders remain market orders even when the triggering bar has no remaining fill capacity. Zero-volume bars cannot fill orders.

Default limit fills require one tick of trade-through. `touch` is opt-in. Conservative limit fills occur at the limit with no assumed price improvement or adverse slippage beyond the limit. No queue priority is inferred. Optional volume participation caps total fills per bar and enables partial fills; default null means unlimited simulated capacity on positive-volume bars. This is explicitly a bar model, not an exchange queue or proof of fill liquidity.

OCO stops/targets are attached to filled entries. When both are reachable and neither is resolved by an opening gap, the default is stop first; optimistic/target-first alternatives are recorded. Intrabar limit/stop entries have an additional entry-path ambiguity: conservative mode allows the adverse stop and delays favorable targets; optimistic mode may assume the target occurred after entry. These bars are flagged. This does not invent high/low sequencing.

Partial entry fills cancel the remainder explicitly because scale-in accounting is not implemented. Partial target fills retain a resized stop for residual contracts. Partial triggered stops cancel competing targets and continue to close remaining contracts. No fractional contracts, hedges or silent reversals are allowed.

Commission and exchange fees are separate dollars per contract per side; slippage is whole ticks per instrument. Configuration contains illustrative values, not broker quotations. The engine reports assumptions and supports 0/1/2/4 tick scenarios without optimizing them.

Portfolio balance debits fees, realizes actual-fill P&L at exits, and marks open positions at each close. Gross trade P&L uses reference prices; net P&L equals gross minus fees and separately measured slippage, avoiding double charging. Trades include direction, times, prices, quantity, costs, net/gross P&L, initial risk and R, holding time, entry session/date, instrument, contract, strategy and exit reason.

Trade MFE/MAE use complete bars held throughout plus execution prices. Entry/exit bars with unknown intrabar ordering do not contribute unordered full extremes. These are **observed excursion bounds**, not exact tick-level MFE/MAE. Intrabar fill times use bar-end proxies; holding times consequently have bar resolution. Open positions are not artificially liquidated at the last bar.

## Risk and reporting

Sizing helpers implement fixed integer contracts and `floor(dollar_risk / (stop_distance * point_value + expected_roundtrip_costs))`, capped by maximum contracts. Zero-sized risk budgets are returned as zero and cannot create an order. Entries require a protective stop and valid stop/target sides; an opening gap can invalidate a planned risk budget and reject an entry.

Limits cover per-trade risk, daily loss, daily entry count, maximum contracts, maximum simultaneous positions and entry time window. The initial engine supports one instrument and one net position per run; unsupported higher simultaneous-position limits are rejected. Exits are allowed after cutoff and during a loss lockout.

Daily loss resets on the ETH trading date, using preceding marked equity as the baseline. Once hit, the lockout survives later recovery. It observes fills, opens and closes, and adverse extremes of bars known to have been held throughout; extremes are assessed after the bar closes, without using future bar lows/highs to reject an opening entry. It prevents subsequent entries; it does not pretend to be an intrabar broker liquidation or flatten an existing position automatically. Margin is a fixed configurable entry/close threshold; exhaustion or close breaches stop the simulation rather than fabricate liquidations.

Equity is recorded after completed trades and every bar close, with peak and dollar/percentage drawdown. The reported curve does not claim exact intrabar drawdown. Metrics include wins/losses/breakevens, win rate, sums of positive/negative net trade P&L, cost-free gross P&L, net profit, averages, profit factor, expectancy, average/median R, extremes, holding period and trades per observed trading day. No-loss profit factor is null with a separate flag, rather than invalid JSON infinity. Weekday/hour/session/instrument/direction breakdowns use entry time in New York. Trade-group drawdowns are not reconstructed from segregated hypothetical portfolios.

Run artifacts contain metadata, data/code/timezone-file SHA-256 hashes, resolved parameters/costs/calendar/risk, integrity reports, features, events, rolls, orders, fills, ambiguity records, trades and equity curves. Code/data changing during a run fails. Files are kept in a unique run directory; repeated identical input/config/code runs produce identical deterministic results and distinct run identifiers. This does not verify vendor provenance, licenses, or provider corrections.

## Weekly VWAP reaction V1

This experiment submits **no trades**. It observes the first qualified weekly VWAP interaction per ETH trading date, not the first touch of every swing or one event per week. The level is frozen from the **previous completed bar's** weekly VWAP. A qualifying current bar spans that level in its low/high range, the prior close is on a known side, and the approach has departed by at least the configured minimum. No event is created from a gap that jumped over the level without a range touch. Discovery happens at current bar close, not an invented exact tick of contact.

Each event records approach side, raw/research reference level, signed close distance, session-VWAP relation, PDH/PDL/ONH/ONL, ATR, time/day, maximum pre-touch departure and an explicitly labelled close-to-close approach-path proxy. The latter cannot recover the true intrabar distance traveled before contact.

Forward MFE/MAE starts at the **next bar after detection**, at 5/15/30/60 elapsed minutes by default. It is measured in instrument price points relative to the frozen level, oriented away from the approach (from above: positive/up; from below: negative/down). The detection bar is excluded because its pre/post-touch path is unknown. Missing/unaligned windows, scheduled closures, trading-date boundaries, rolls and dataset end censor the window and return null, not a biased shorter-horizon measurement.

First-passage statistics measure whether each configured away threshold (NQ/MNQ example 5/10/20/30 points) occurs before a configured through-distance on the opposite side, within the largest horizon. Thresholds are instrument-specific in the example config and are **illustrative research definitions**, not optimized strategy parameters. If both barriers occur in one bar, opening gaps resolve ordering where possible; otherwise conservative/optimistic policy and ambiguous-bar counts are recorded. Unresolved, no-passage and censored observations are separately counted. Distribution statistics use complete windows only and include sample counts, mean, median and 10th/90th percentiles.

The same event/label interfaces accept `session_vwap` through Python for the next daily/session experiment. It is not registered as another CLI trading strategy. No ML, optimization, live trading, frontend or additional trading strategies have been added.

## Historical baseline validation

The counts and runtime below describe the original intraday implementation, not
the current suite. The current Python 3.12 offline suite has **235 passing tests**,
with one live integration test excluded. Realized-volatility definitions and
verification are in [VOLATILITY.md](VOLATILITY.md); Databento adapter verification
is in [DATABENTO.md](DATABENTO.md).


The complete pytest suite contains **128 passing tests** on Python 3.9.6 with pytest 8.4.2, including the original seven daily tests. New coverage spans all six contract economics and execution P&L, decimal tick rounding, commission/exchange fees, 0/1/2/4-tick slippage, risk sizing, session boundaries and both DST changes, malformed/duplicate/missing/off-grid candles, VWAP math and resets, PDH/PDL/PDC, overnight levels, IB completion, ATR, immutable strategy contexts, future-data perturbation, next-bar execution, market/limit/stop orders, stop gaps, partial fills, triggered stop persistence, OCO ambiguity policies, partial-target stop retention, risk limits, daily loss recovery lockout, DAY expiry, roll selection/adjustments/cost accounting, forward censoring, MFE/MAE signs, metrics, CLI validation/run/report, and repeated-run deterministic results.

Synthetic fixtures contain 2,730 one-minute bars and 546 aggregated five-minute bars over two full weekday-template trading dates. Each smoke run discovers two events with complete 5/15/30/60-minute horizons and zero trades. These counts verify wiring only; they are not market research findings. Tests exercise the implemented assumptions, not their empirical realism.

The core needs no third-party runtime dependency. The optional Databento adapter uses its SDK. `requirements-dev.txt` pins pytest; `requirements-py312.lock` records the current Python 3.12 environment, while `requirements-dev.lock` retains the historical Python 3.9 baseline.

## Recommended next task

Import a licensed, raw NQ constituent-contract OHLCV export with explicit publication-time conventions, a dated exchange holiday/early-close/halts calendar, expiration/first-notice metadata, and overlapping old/new contract data. Validate a small known period manually against source prints and session/roll behavior. Only after data/session conventions are verified should the first weekly VWAP event distributions be collected and an out-of-sample hypothesis designed.

## Problems found

- Existing foundations were daily-only and could not represent intraday sessions or order paths; they are preserved as legacy examples, not used by the intraday research command.
- Standard OHLCV cannot establish exact intrabar order sequencing, queues, trade-level VWAP, exact MFE/MAE, or volume-at-price. Models and bounds are labelled accordingly.
- Partial target exits originally risked leaving residual contracts without their stop; regression coverage now requires the stop to remain.
- A touched stop with no fill capacity must remain triggered; a regression now covers its later market execution. Zero-volume bars no longer fill market orders.
- Partial/unequal historical liquidity coverage can bias roll selection; liquidity roll rules now require complete matched prior sessions.
- Missing trading dates must not turn older highs/lows into yesterday's levels; those levels now return null.
- A loss observed only at closing equity can miss an intrabar breach; fully held bar extremes now lock out subsequent entries, without pretending to know an intrabar liquidation sequence.
- Holiday/early-close calendars, expirations, first-notice dates and published-as-of OI are supplied metadata, not a bundled certified market database.
- Fees, margin and reaction thresholds are illustrative. Actual broker/exchange requirements and data economics have not been connected.
- Fixed rolls use calendar days and the first observed bar; incomplete session starts may delay a roll. Paired opens and expiry checks prevent silent contract-gap P&L but do not infer missing execution prices.
- Roll execution assumes synchronous-open liquidity; multi-contract order-book capacity is not modeled.
- The engine supports one instrument/position per run and no scale-ins; partial entry remainders are cancelled explicitly.
- Risk lockouts prevent future entries, not automatic forced exits. Margin failures stop a run; broker margin calls and liquidation fees are not modeled.
- Price-level features on adjusted research series require conversion to raw order coordinates. Retrospective back-adjustments are unsuitable for causal discovery and remain offline.
- Event time is known at bar close. Forward horizons exclude the touch bar; results do not measure the exact first five minutes after an unknown intrabar touch.
- Windows ending at dataset/session boundaries, missing data or rolls are censored. This affects sample composition and must be examined alongside distributions.
- Python strategies are trusted code. Immutable contexts discourage accidental leakage, but they cannot sandbox deliberate external access.
- History snapshots are tuple prefixes and full features are retained for audits; large datasets will require a bounded/view-based history and streaming storage before tick-scale research.
- The shipped intraday examples are synthetic fixtures. No empirical edge or market result has been established.

Additional limitation: symbol parsing verifies roots and month/year syntax, not an exchange listing database or intraday expiration cutoff. An individual contract without supplied expiration metadata cannot have its expiry verified.
