# Futures research backtester

A causal, CSV-first intraday research engine for **NQ, MNQ, ES, MES, GC and MGC**, alongside the preserved daily example backtester. Python 3.12+; the core uses the standard library and Databento acquisition uses the official optional SDK. The objective is trustworthy event distributions, not fitted profitability.

## Project status

The intraday engine supports NQ, MNQ, ES, MES, GC and MGC. The separate
realized-volatility and chart commands currently accept **NQ, ES and GC** and
consume one-minute raw bars. Historical acquisition and the reviewed dated
calendar currently support **NQ only**.

The retained September 14–25, 2026 NQ trial passed an independent offline audit:
ten complete active-contract sessions, 13,800 traded minutes and one volume roll.
This acceptance covers the retained acquisition and measurement pipeline, not
other dates, holiday/DST transitions, trading performance or forecasts. See the
[dated acceptance report](docs/acceptance/databento-2026-10-07.md).

Full-history preparation and approval-gated acquisition scripts are available;
full-history normalization and acceptance remain pending. HAR/GARCH/ML forecasting,
optimization and live trading are not implemented.

## Setup

From the repository root, use Python 3.12 or newer:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
# Optional historical-data SDK and offline chart rendering:
python -m pip install -e ".[databento,charts]"
```

The core has no third-party runtime dependencies. Optional extras pin pytest,
Databento and Matplotlib; equivalent requirements files are included.
`requirements-py312.lock` records the tested macOS Python 3.12 environment;
`requirements-dev.lock` is the historical Python 3.9 baseline, not the current setup.
On the original workstation, `.venv` points to `.venv-py312`; that symlink is local.

## Documentation

| Guide | Contents |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Data, sessions, rolls, causal features, execution, risk and audit assumptions |
| [Databento](docs/DATABENTO.md) | Credentials, cost gates, download, normalization and provider inspection |
| [Realized volatility](docs/VOLATILITY.md) | Estimators, sampling, coverage, causal profiles and charts |
| [NQ history](docs/HISTORY.md) | Metadata preparation, frozen plans, acquisition and outstanding acceptance work |
| [Daily starter](docs/daily-starter.md) | Preserved daily moving-average example and its narrower scope |
| [NQ acceptance](docs/acceptance/databento-2026-10-07.md) | Dated independent evidence and reproducibility commands |

## Commands

```sh
backtester validate-data data/synthetic_NQ_1m.csv --symbol NQ --interval 1
backtester run --strategy weekly-vwap-reaction-v1 --symbol NQ \
  --data data/synthetic_NQ_1m.csv --interval 1 --config config/research.example.json
backtester report RUN_ID
python -m pytest -q
```

Replace `RUN_ID` with the identifier printed by `run`. Commands assume the repository
root as the working directory. `python -m backtester --help` shows the legacy daily
help; use `python -m backtester SUBCOMMAND --help` for each newer command.

`python -m backtester` accepts the same new subcommands if the console entry point is unavailable. The old daily command is preserved as `python -m backtester daily` and its original flags still work without a subcommand. Daily documentation is in `docs/daily-starter.md`.

## Intraday CSV contract

```csv
timestamp,open,high,low,close,volume,contract,symbol
2026-01-05T14:30:00Z,20000,20002,19999,20001,150,NQH26,NQ
```

Timestamps label bar **opens**, must include timezone offsets, and normalize to UTC. Each bar covers the selected 1 or 5 minutes; no intraday bars are synthesized from daily data. Dated contracts are required, either in the CSV or through `--contract NQH26`. Optional trade count, bid/ask volume and point-in-time open interest are accepted.

Use raw constituent-contract prices. Multiple contracts can appear at the same timestamp; provide expiration dates in `roll.expirations` and overlapping old/new contract opens. Pre-adjusted continuous prices are not executable inputs. Fixed, previous-session-volume and previous-session-OI rolls are supported.

The run rejects malformed data, off-tick source prices and missing active intervals by default. Explicit `--allow-off-tick` / `--allow-missing` overrides are audited. No interpolation occurs. Holiday/early-close schedules belong in dated calendar overrides. The weekday template is **not** a certified historical holiday calendar, and its legacy afternoon equity pause is obsolete for current NQ. Use the dated calendar for licensed data.

Weekly warmup starts Sunday 18:00 ET for the Monday trading date. A partial first week yields no default weekly events until a fully observed week begins. `--allow-partial-warmup` explicitly permits partial prefixes and records that assumption.

## Synthetic smoke examples

`data/synthetic_NQ_1m.csv` is generated directly as intraday OHLCV; `synthetic_NQ_5m.csv` aggregates those minute fixtures. They are **not historical market prices** and their distributions are not evidence of an edge.

```sh
backtester run --symbol NQ --data data/synthetic_NQ_1m.csv \
  --config config/research.example.json
backtester run --symbol NQ --interval 5 --data data/synthetic_NQ_5m.csv \
  --config config/research.example.json
```

## Research and audits

Weekly VWAP reaction V1 records the first qualified range touch of the **prior completed bar's** weekly VWAP per trading date. It records market context and submits no trades. Offline labels measure 5/15/30/60-minute forward excursions and configurable first-passage thresholds. Ambiguous paths, incomplete horizons and rolls are reported explicitly.

Each `results/RUN_ID/` contains metadata with data/code/timezone hashes, assumptions, features, event distributions, trades, orders, fills, rolls, data integrity and equity curves. Configured commissions, exchange fees, slippage, margin and thresholds in the example are illustrative; replace them with justified research inputs.

Read `docs/ARCHITECTURE.md` for complete architecture, contract sources, session definitions, roll rules, execution/risk models, research-event definitions, reproducibility, and **Problems found**. The optional Databento adapter has bounded NQ acceptance as described above. Local interactive chart reports are available; there is no live trading, optimization, hosted application or exact candle-derived volume-at-price.

## Realized-volatility research

A separate causal measurement layer supports minute/5m/15m RV, BPV, explicitly
configured basic TBPV, jump proxies, semivariances, quarticity, OHLC range variance,
session decomposition and profiles normalized using prior complete sessions.
Missing prefixes are censored explicitly. Definitions, sampling and acceptance
requirements: [Realized volatility](docs/VOLATILITY.md).

```sh
python -m backtester volatility --data data/synthetic_NQ_1m.csv --symbol NQ
```


## Git and local files

Commit source, tests, configuration templates, calendar references, documentation
and the bundled synthetic fixtures. `.gitignore` excludes `.env` and its variants,
Python environments, caches, build artifacts, generated reports and all other data.
Keep licensed downloads and local research outputs outside Git. Detailed acceptance evidence JSON under
`docs/acceptance/` is also ignored; the review notes and checker scripts remain
publishable.

Copy `.env.example` to `.env` for local credentials and set `chmod 600 .env`.
The adapter reads `DATABENTO_API_KEY` from the process environment; it does not load
`.env` automatically. In a local shell, use `source .env` followed by
`export DATABENTO_API_KEY`. Never put credentials in tracked configuration or docs.

Before committing, review `git status --short` and `git diff --cached --stat`.
The offline validation command is `python -m pytest -q` (live integration tests are
excluded by default).


## Charts from local data

Install the optional plotting dependency with `python -m pip install -e ".[charts]"`.
Then generate an offline report (use a new output directory for each run):

```sh
python -m backtester volatility-charts --symbol NQ \
  --data data/normalized/databento/NQ/ID/bars.csv \
  --config data/normalized/databento/NQ/ID/research-config.json \
  --output results/volatility-charts-ID
```

Replace `ID` with a local acquisition ID; licensed files are not included in Git.
For a bundled-data example, substitute `data/synthetic_NQ_1m.csv` and
`config/research.example.json`.

Open `results/volatility-charts-ID/index.html` in your browser. It compares completed
sessions and lets you select raw 1m/5m/15m OHLC and volume, returns, cumulative
variance and a profile based only on prior completed sessions. Zoom, pan and
synchronized crosshairs are available. PNG and SVG exports are included.
The viewer uses locally bundled TradingView Lightweight Charts 5.1.0, with
candlesticks or OHLC bars, a resizable volume pane, independent chart navigation, drag-to-pan, wheel zoom,
and price-scale controls. Every chart has zoom buttons and Reset view to fit all points. The 1m/5m/15m buttons
replace both price and volume bars; research indicators retain their defined
sampling frequency. Each comparison chart is interactive and displayed separately.

The default All sessions view joins selected active-contract sessions into one
timeline at every timeframe, with contract rolls marked and raw prices unchanged.
Intraday research lines stay separate at session boundaries; cumulative variance
restarts for each session. Individual sessions remain available in the selector.

When an individual session is selected, the 1H, 4H and 1D views use all complete downloaded sessions for the selected
raw contract. Hourly and four-hour bars start at the futures session open; the
scheduled closing tail is included. Daily bars cover one futures session, not
a midnight-to-midnight day. No bar combines contracts or incomplete sessions.

All assets are local; no market data is uploaded. Variance is shown in squared
basis points; volatility is `sqrt(RV) * 100` percent, without annualization.
Incomplete sessions and unsupported coarse-sampling tails are labelled explicitly.
Charts are descriptive measurements and do not establish predictive power or
independent market-data acceptance. `--as-of` restricts input to completed bars at
an aware ISO timestamp. See [estimator definitions](docs/VOLATILITY.md).
