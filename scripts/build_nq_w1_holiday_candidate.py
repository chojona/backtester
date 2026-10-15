"""Offline, non-certifying CME holiday trade-date candidate for NQ W1."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"
LEDGER = ROOT / "results/databento-nq-full-history/phase3-v3.0.0/certification-by-session.csv"
OUT = ROOT / "calendars/nq-2022-holiday-candidate-v1.json"
NY = ZoneInfo("America/New_York")
HOLIDAYS = {
    date(2022, 6, 21): ("juneteenth", "2022-06-20", "bc9f2caf26a73a13029f177fcc6468bdc8662899ff935f44329ee1a95c8b667b", "G5/H5; O5/P5/T5; D2; A76"),
    date(2022, 7, 5): ("independence-day", "2022-07-04", "1ea0459d8aa0fd7ec5147614855f6d0d43607efefdc3aa9c6b1e18ddbfd54fde", "G5/H5; N5/R5/S5; D2; A75"),
    date(2022, 9, 6): ("labor-day", "2022-09-05", "28d533f25d1af74af043e411635f1933fd4ff6359c80c049f87f019d2f1d57d0", "G5/H5; O5/S5/T5; D2; A74"),
}
MONDAY_TO_TUESDAY = {date.fromisoformat(v[1]): k for k, v in HOLIDAYS.items()}


def utc_et(day, hour):
    return datetime.combine(day, time(hour), NY).astimezone(timezone.utc)


def segments(day):
    if day in HOLIDAYS:
        monday = date.fromisoformat(HOLIDAYS[day][1])
        return [(utc_et(monday - timedelta(days=1), 18), utc_et(monday, 13)),
                (utc_et(monday, 18), utc_et(day, 17))]
    return [(utc_et(day - timedelta(days=1), 18), utc_et(day, 17))]


def expected_minutes(parts):
    return sum(int((end - start).total_seconds() // 60) for start, end in parts)


def hash_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def candidate():
    old = {date.fromisoformat(r["trading_date"]): r for r in csv.DictReader(LEDGER.open())}
    dates = sorted(d for d in old if date(2022, 6, 6) <= d <= date(2022, 11, 25)
                   and d not in MONDAY_TO_TUESDAY)
    table = pq.read_table(PARQUET, columns=["trading_date", "timestamp_utc", "contract", "open", "close", "volume"],
                          filters=[("trading_date", ">=", date(2022, 6, 1)),
                                   ("trading_date", "<=", date(2022, 11, 25))])
    by_date_contract = defaultdict(list)
    for labeled, stamp, contract, op, cl, vol in zip(*(table[c].to_pylist() for c in table.column_names)):
        day = MONDAY_TO_TUESDAY.get(labeled, labeled)
        if day in old:
            by_date_contract[(day, contract)].append((stamp, op, cl, vol, labeled))
    volumes = {key: sum(r[3] for r in rows) for key, rows in by_date_contract.items()}
    output = []
    for day in dates:
        if day < date(2022, 6, 7):
            continue
        prior = max(x for x in dates if x < day)
        contracts = sorted(c for d, c in by_date_contract if d == day)
        winner = max(contracts, key=lambda c: (volumes.get((prior, c), 0), c))
        parts = segments(day)
        selected = by_date_contract[(day, winner)]
        observed = []
        for start, end in parts:
            bars = sorted((r for r in selected if start <= r[0] < end), key=lambda r: r[0])
            times = [r[0] for r in bars]
            grid = {start + timedelta(minutes=i) for i in range(int((end-start).total_seconds()//60))}
            missing = sorted(grid - set(times))
            complete = not missing and len(times) == len(grid) and len(times) == len(set(times))
            returns = ([math.log(bars[0][2] / bars[0][1])] +
                       [math.log(b[2] / a[2]) for a, b in zip(bars, bars[1:])]
                       if bars and complete else [])
            def research_segment(stamp):
                clock = stamp.astimezone(NY).time()
                return "OVERNIGHT" if clock < time(9, 30) or clock >= time(18) else (
                    "RTH" if clock < time(16) else "POST_RTH")
            bpv_pairs = [abs(returns[i-1] * returns[i]) for i in range(1, len(returns))
                         if research_segment(bars[i-1][0]) == research_segment(bars[i][0])]
            # Coarse samples start at each documented active-segment opening.
            complete_blocks = []
            for i in range(0, len(bars) - 4, 5) if complete else ():
                block = bars[i:i+5]
                if len(block) == 5 and block[0][0] == start + timedelta(minutes=i) and all(
                    b[0] - a[0] == timedelta(minutes=1) for a, b in zip(block, block[1:])
                ):
                    complete_blocks.append(math.fsum(returns[i:i+5]))
            observed.append({"start_utc": start.isoformat(), "end_utc": end.isoformat(),
                             "expected_minutes": len(grid), "observed_bars": len(bars),
                             "missing_minutes_utc": [x.isoformat() for x in missing],
                             "duplicate_bars": len(times) - len(set(times)),
                             "rv_1m": math.fsum(r*r for r in returns) if complete else None,
                             "bpv_within_segment": math.pi/2 * math.fsum(bpv_pairs) if complete else None,
                             "five_minute_complete_blocks": len(complete_blocks),
                             "rv_5m_segment_anchored": math.fsum(x*x for x in complete_blocks) if complete else None})
        volume_rank = [{"contract": c, "predecessor_volume": volumes.get((prior, c), 0),
                        "current_trade_date_volume": volumes[(day, c)]}
                       for c in sorted(contracts, key=lambda c: (-volumes.get((prior, c), 0), c))]
        row = {"trade_date": day.isoformat(), "predecessor_trade_date": prior.isoformat(),
               "segments": observed, "expected_minutes": expected_minutes(parts),
               "selected_contract": winner, "historical_selected_contract": old[day]["selected_contract"],
               "winner_changed": winner != old[day]["selected_contract"],
               "candidate_volume_rank": volume_rank,
               "historical_tier": old[day]["tier"],
               "historical_reason": old[day]["reason_code"],
               "coverage_complete_against_candidate_grid": sum(x["observed_bars"] for x in observed) == expected_minutes(parts)
                   and all(not x["missing_minutes_utc"] and not x["duplicate_bars"] for x in observed)}
        row["off_grid_selected_bars"] = sum(not any(a <= r[0] < b for a, b in parts) for r in selected)
        row["coverage_complete_against_candidate_grid"] &= row["off_grid_selected_bars"] == 0
        if day in HOLIDAYS:
            row["nontrading_halt_preopen_utc"] = {"start": parts[0][1].isoformat(), "end": parts[1][0].isoformat()}
            row["combined_rv_1m"] = math.fsum(x["rv_1m"] for x in observed)
            row["combined_bpv_no_cross_halt_pair"] = math.fsum(x["bpv_within_segment"] for x in observed)
        output.append(row)
    files = {}
    for day, (name, _, expected, cells) in HOLIDAYS.items():
        path = ROOT / f"reports/evidence/cme-2022/2022-{name}-holiday-schedule.xls"
        actual = hash_file(path)
        if actual != expected:
            raise ValueError(f"CME workbook hash changed: {path}")
        files[day.isoformat()] = {"path": str(path.relative_to(ROOT)), "sha256": actual,
                                  "equity_product_cells": cells}
    w1 = [r for r in output if r["trade_date"] <= "2022-11-21"]
    dependencies = []
    for tuesday, (_, monday, _, _) in HOLIDAYS.items():
        following = next(r["trade_date"] for r in w1 if r["predecessor_trade_date"] == tuesday.isoformat())
        dependencies.append({"removed_historical_monday_label": monday,
                             "official_tuesday_trade_date": tuesday.isoformat(),
                             "causal_selection_recomputed_on": [tuesday.isoformat(), following],
                             "variation_recomputed_on": tuesday.isoformat(),
                             "downstream": ["trade_date_ordinals", "5_session_HAR_windows",
                                            "22_session_HAR_windows", "forecast_origins_and_targets"]})
    return {"schema_version": "1.0", "candidate_version": "nq-2022-holiday-candidate-v1",
            "status": "RESEARCH_CANDIDATE_NOT_CERTIFIED", "scope": {"first": "2022-06-07", "last": "2022-11-21"},
            "source_sha256": {"parquet": hash_file(PARQUET), "phase3_ledger": hash_file(LEDGER)},
            "cme_workbooks": files,
            "convention": {"time_zone": "America/New_York", "intervals": "half-open UTC minute starts",
                           "returns": "first bar log(close/open), later bars log(close/previous close), reset at each active-segment opening",
                           "bpv": "(pi/2) sum of adjacent absolute return products within each active interval and the same OVERNIGHT/RTH/POST_RTH research segment only",
                           "selection": "current contract universe ranked by previous completed CME trade-date retained volume; contract code breaks ties"},
            "changed_winners": [r["trade_date"] for r in w1 if r["winner_changed"]],
            "remapping_dependencies": dependencies,
            "trade_dates": w1,
            "extension_preview": [r for r in output if r["trade_date"] > "2022-11-21"]}


if __name__ == "__main__":
    data = candidate()
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote {OUT}: {len(data['trade_dates'])} W1 dates")
