"""Independent arithmetic comparison for one retained strict NQ session."""
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from backtester.data import Bar
from backtester.sessions import SessionCalendar
from backtester.volatility import RealizedVolatility

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/databento-nq-full-history/phase3-v3.0.0/strict-certified.parquet"
LEGACY = ROOT / "results/databento-nq-full-history/volatility-by-session.csv"
OUTPUT = ROOT / "results/nq-strict-numeric-comparison.json"
DAY = date(2026, 9, 14)


def main():
    rows = pq.read_table(SOURCE, filters=[("trading_date", "=", DAY)],
                         columns=["timestamp_utc", "open", "high", "low", "close",
                                  "volume", "contract"]).to_pylist()
    rows.sort(key=lambda row: row["timestamp_utc"])
    if len(rows) != 1380 or {row["contract"] for row in rows} != {"NQU26"}:
        raise ValueError("Retained strict sample changed")
    calendar = SessionCalendar(breaks=[])
    estimator = RealizedVolatility(calendar)
    returns, segments = [], []
    for index, row in enumerate(rows):
        bar = Bar(row["timestamp_utc"], row["open"], row["high"], row["low"],
                  row["close"], row["volume"], row["contract"], "NQ")
        result = estimator.update(bar, as_of=bar.end)
        reference = rows[index - 1]["close"] if index else row["open"]
        returns.append(math.log(row["close"] / reference))
        segments.append(calendar.classify(row["timestamp_utc"]).session)
    if not result.session_complete:
        raise ValueError("Retained strict sample is not a complete session")
    values = {
        "rv_1m": math.fsum(r*r for r in returns),
        "rv_5m": math.fsum(math.fsum(returns[i:i+5])**2 for i in range(0, len(returns), 5)),
        "rv_15m": math.fsum(math.fsum(returns[i:i+15])**2 for i in range(0, len(returns), 15)),
        "rs_positive": math.fsum(r*r for r in returns if r > 0),
        "rs_negative": math.fsum(r*r for r in returns if r < 0),
        "bpv_segment_aware": math.pi/2 * math.fsum(
            abs(returns[i]*returns[i-1]) for i in range(1, len(returns))
            if segments[i] == segments[i-1]),
        "bpv_all_adjacent": math.pi/2 * math.fsum(
            abs(returns[i]*returns[i-1]) for i in range(1, len(returns))),
    }
    measured = {key: getattr(result, "bpv" if key == "bpv_segment_aware" else key)
                for key in values if key != "bpv_all_adjacent"}
    if any(not math.isclose(values[key], measured[key], rel_tol=1e-10, abs_tol=1e-15)
           for key in measured):
        raise ValueError("Independent arithmetic disagrees with streaming estimator")
    with LEGACY.open() as stream:
        prior = next(row for row in csv.DictReader(stream) if row["trading_date"] == DAY.isoformat())
    if not math.isclose(float(prior["bpv"]), values["bpv_all_adjacent"], rel_tol=1e-10):
        raise ValueError("Legacy historical BPV does not follow all-adjacent formula")
    payload = {
        "date": DAY.isoformat(), "bars": len(rows),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "independent": values, "streaming": measured,
        "legacy": {"rv": float(prior["rv"]), "bpv": float(prior["bpv"])},
        "legacy_bpv_minus_streaming": float(prior["bpv"]) - result.bpv,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
