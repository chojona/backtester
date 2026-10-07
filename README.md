# Intraday futures quantitative research

A causal, CSV-first intraday research engine for **NQ, MNQ, ES, MES, GC and MGC**, alongside the preserved daily example backtester. Python 3.12+; the core uses the standard library and Databento acquisition uses the official optional SDK. The objective is trustworthy event distributions, not fitted profitability.

## Databento historical NQ

The constituent-contract adapter, cost-gated download, deterministic normalization and dated trial calendar are implemented. Live validation remains pending an environment API key; no real event count is available. See [Databento setup and acceptance workflow](docs/DATABENTO.md).

## Commands

```sh
cd ~/Desktop/Projects/backtester
source .venv/bin/activate
backtester validate-data data/NQ.csv --symbol NQ --interval 1
backtester run --strategy weekly-vwap-reaction-v1 --symbol NQ \
  --data data/NQ.csv --interval 1 --config config/research.example.json
backtester report RUN_ID
python -m pytest -q
```

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

Read `docs/ARCHITECTURE.md` for complete architecture, contract sources, session definitions, roll rules, execution/risk models, research-event definitions, reproducibility, and **Problems found**. The optional Databento historical adapter is implemented; real-data acceptance is pending. The engine includes no live trading, optimization, frontend or exact candle-derived volume-at-price.

## Installing on another machine

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install -r requirements-dev.txt
```

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
Keep licensed downloads and local research outputs outside Git.

Copy `.env.example` to `.env` for local credentials and set `chmod 600 .env`.
The adapter reads `DATABENTO_API_KEY` from the process environment; it does not load
`.env` automatically. In a local shell, use `source .env` followed by
`export DATABENTO_API_KEY`. Never put credentials in tracked configuration or docs.

Before committing, review `git status --short` and `git diff --cached --stat`.
The offline validation command is `python -m pytest -q` (live integration tests are
excluded by default).
