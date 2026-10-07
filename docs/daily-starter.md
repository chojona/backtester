# Futures backtester

A Python 3.9+ starter for single-instrument, daily-bar futures research. It uses the standard library, so no third-party packages or API credentials are required.

## Run

```sh
cd ~/Desktop/Projects/backtester
source .venv/bin/activate
python -m backtester
python -m unittest discover -s tests -v
```

The included `data/sample.csv` is deterministic, **synthetic data**, not historical market prices. The example strategy trades a fixed number of contracts: long when the fast simple moving average exceeds the slow one, otherwise flat. It computes a signal after each close and executes it at the next available open.

## Your data and contract settings

Supply CSV with `date,open,close` columns, one row per daily bar, ISO dates (`YYYY-MM-DD`), and strictly increasing dates. Additional columns are ignored. Finite negative prices are supported. Use consistently defined sessions. The daily reader does not accept intraday timestamps.

```sh
python -m backtester --data data/my_futures.csv --fast 20 --slow 50 \
  --cash 100000 --contracts 1 --multiplier 50 --tick-size 0.25 \
  --commission 2.50 --slippage-ticks 1 --margin 15000 \
  --periods-per-year 252 --output results/my-run
```

The default multiplier and tick size match ES outright contracts. For MES use `--multiplier 5 --tick-size 0.25`. Contract references: [CME ES FAQ](https://www.cmegroup.com/trading/equity-index/eminifaq.html) and [CME Micro E-mini FAQ](https://www.cmegroup.com/articles/faqs/micro-e-mini-equity-index-futures-frequently-asked-questions.html). Set the correct multiplier and tick size for any other contract.

**Commission, slippage, and margin defaults are illustrative assumptions.** Commission is dollars per contract per side; slippage is adverse ticks per fill. Set them from your own execution assumptions and broker's requirements. Margin is a fixed configurable threshold, not a current exchange or broker margin schedule.

## Results

Each run writes `summary.json`, `equity.csv`, and `trades.csv` under the output directory. Summary includes return, annualized return, maximum drawdown (negative fraction), a Sharpe ratio with zero risk-free rate, fill count, and any open contracts. A zero-volatility Sharpe ratio is null. Annualization assumes equally spaced trading bars and uses the configured periods per year.

Futures P&L equals price change times contract multiplier times contracts. Equity includes open-position P&L at each close. Positions remain open at the final bar; no artificial final exit or exit cost is added. Margin is reserved capacity, not a purchase cost. The run stops with an error if entry margin is insufficient, close equity breaches the configured margin threshold, or account equity is exhausted. It does not simulate broker liquidations or separate maintenance margin.

## Scope and next steps

This starter models one instrument, fixed contract sizing, and long/flat positions. It does not model short positions, intraday stops, limit orders, market depth, interest, exchange calendars, expirations, settlement mechanics, or automatic contract rolls. Use a single contract within its life or a carefully prepared continuous series; rollover gaps and back-adjustments can distort P&L. Real continuous futures research needs explicit roll handling and costs before drawing conclusions. Historical data downloading and broker connections are not configured.

Edit the signal at the end of `backtester/engine.py` to replace the example strategy. Tests cover next-open execution, future-data isolation, fees and slippage, overnight P&L, margin rejection, flat prices, and invalid input.
