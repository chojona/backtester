"""Count pre-2012 rows affected by the exchange's prior trade-date rule."""
import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from backtester.nq_historical_calendar import ordinary_nq_trade_date

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"
OUTPUT = ROOT / "reports/nq-certification-blockers/pre2012-mapping.json"


def main():
    count = Counter()
    examples = []
    parquet = pq.ParquetFile(SOURCE)
    for batch in parquet.iter_batches(batch_size=100_000,
                                      columns=["timestamp_utc", "trading_date"]):
        stamps, stored = (batch.column(i).to_pylist() for i in range(2))
        for stamp, old in zip(stamps, stored):
            if old.year > 2012 or (old.year == 2012 and old.month == 11 and old.day > 19):
                continue
            try:
                corrected = ordinary_nq_trade_date(stamp)
            except ValueError:
                continue
            count["pre2012_rows"] += 1
            if corrected is None:
                count["outside_ordinary_hours_requires_review"] += 1
            elif corrected != old:
                count["trade_date_mismatch"] += 1
                if len(examples) < 12:
                    examples.append({"timestamp_utc": stamp.isoformat(),
                                     "stored_date": old.isoformat(),
                                     "ordinary_cme_date": corrected.isoformat()})
    payload = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_rule": "CME equity index trading-hours change effective trade date 2012-11-19",
        "counts": dict(count), "examples": examples,
        "disposition": "Original parquet unchanged; remap must be versioned with selected-contract and session recertification.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
