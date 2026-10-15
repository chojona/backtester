"""Rebuild the retained full-grid historical BPV under the streaming convention.

Reads the immutable consolidated bars and legacy derived CSV. Writes only to a
new version directory; never changes the original historical output.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from backtester.volatility import (
    BPV_ESTIMATOR_VERSION, LEGACY_HISTORICAL_BPV_VERSION,
    segmented_bipower_variation,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/databento-nq-full-history"
SOURCE = BASE / "nq_outright_ohlcv_1m.parquet"
LEGACY = BASE / "volatility-by-session.csv"
OUT = BASE / BPV_ESTIMATOR_VERSION
NY = ZoneInfo("America/New_York")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def segment(stamp) -> str:
    clock = stamp.astimezone(NY).time()
    return "OVERNIGHT" if clock < time(9, 30) or clock >= time(18) else (
        "RTH" if clock < time(16) else "POST_RTH")


def measures(rows: list[dict]) -> tuple[float, float, float]:
    rows.sort(key=lambda row: row["timestamp_utc"])
    returns = [math.log(row["close"] / (rows[i - 1]["close"] if i else row["open"]))
               for i, row in enumerate(rows)]
    labels = [segment(row["timestamp_utc"]) for row in rows]
    legacy = math.pi / 2 * math.fsum(abs(a * b) for a, b in zip(returns, returns[1:]))
    versioned = segmented_bipower_variation(returns, labels)
    if versioned is None:
        raise ValueError("No within-segment BPV pair")
    return legacy, versioned, math.fsum(r * r for r in returns)


def main() -> None:
    with LEGACY.open(newline="") as stream:
        prior = list(csv.DictReader(stream))
    keys = {(row["trading_date"], row["contract"]) for row in prior}
    if len(keys) != len(prior):
        raise ValueError("Duplicate legacy date and contract")
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    parquet = pq.ParquetFile(SOURCE)
    columns = ["trading_date", "contract", "timestamp_utc", "open", "close"]
    for batch in parquet.iter_batches(batch_size=100_000, columns=columns):
        arrays = [batch.column(i).to_pylist() for i in range(len(columns))]
        for day, contract, stamp, opened, closed in zip(*arrays):
            key = (day.isoformat(), contract)
            if key in keys:
                groups[key].append({"timestamp_utc": stamp, "open": opened, "close": closed})
    if set(groups) != keys:
        raise ValueError("Missing consolidated bar groups for legacy measures")
    output = []
    changed = 0
    for row in prior:
        key = row["trading_date"], row["contract"]
        bars = groups[key]
        if len(bars) != int(row["n"]):
            raise ValueError(f"Bar count changed for {key}")
        old_bpv, new_bpv, rv = measures(bars)
        if not math.isclose(old_bpv, float(row["bpv"]), rel_tol=1e-10, abs_tol=1e-15):
            raise ValueError(f"Legacy BPV failed reproduction for {key}")
        if not math.isclose(rv, float(row["rv"]), rel_tol=1e-10, abs_tol=1e-15):
            raise ValueError(f"Legacy RV failed reproduction for {key}")
        revised = dict(row)
        revised["bpv"] = repr(new_bpv)
        revised["jump"] = repr(max(float(row["rv"]) - new_bpv, 0.0))
        revised["bpv_estimator_version"] = BPV_ESTIMATOR_VERSION
        revised["source_bpv_estimator_version"] = LEGACY_HISTORICAL_BPV_VERSION
        output.append(revised)
        changed += not math.isclose(new_bpv, old_bpv, rel_tol=0, abs_tol=1e-18)
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "volatility-by-session.csv"
    with target.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    manifest = {
        "version": BPV_ESTIMATOR_VERSION,
        "legacy_version": LEGACY_HISTORICAL_BPV_VERSION,
        "source_parquet_sha256": digest(SOURCE),
        "legacy_csv_sha256": digest(LEGACY),
        "output_csv_sha256": digest(target),
        "session_count": len(output),
        "bpv_changed_count": changed,
        "definition": "(pi/2) sum |r_i r_(i-1)| only for adjacent one-minute returns in the same Overnight, RTH or Post-RTH calendar segment; no finite-sample correction",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
