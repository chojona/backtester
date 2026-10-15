"""Build a non-certifying, read-only audit of the 120-date NQ W1 extension.

The only output is a new research JSON. Source bars and certification remain intact.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"
LEDGER = ROOT / "results/databento-nq-full-history/phase3-v3.0.0/certification-by-session.csv"
OUTPUT = ROOT / "results/nq-w1-120-session-candidate.json"
ET = ZoneInfo("America/New_York")
UTC = timezone.utc
FIRST, LAST = date(2022, 6, 2), date(2022, 11, 21)
HOLIDAY_TRADE_DATES = {
    date(2022, 5, 31): date(2022, 5, 30),
    date(2022, 6, 21): date(2022, 6, 20),
    date(2022, 7, 5): date(2022, 7, 4),
    date(2022, 9, 6): date(2022, 9, 5),
}
REMAPPED = {monday: tuesday for tuesday, monday in HOLIDAY_TRADE_DATES.items()}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc(day, hour):
    return datetime.combine(day, time(hour), ET).astimezone(UTC)


def active_parts(day):
    if day in HOLIDAY_TRADE_DATES:
        monday = HOLIDAY_TRADE_DATES[day]
        return [(utc(monday - timedelta(days=1), 18), utc(monday, 13)),
                (utc(monday, 18), utc(day, 17))]
    return [(utc(day - timedelta(days=1), 18), utc(day, 17))]


def iso(stamp):
    return stamp.isoformat().replace("+00:00", "Z")


def main():
    ledger = {date.fromisoformat(r["trading_date"]): r for r in csv.DictReader(LEDGER.open())}
    # Independent civil-date enumeration; the three CME workbook trade-date
    # headers remove the Monday identities while retaining their active bars.
    civil = [FIRST + timedelta(days=i) for i in range((LAST - FIRST).days + 1)]
    weekdays = [d for d in civil if d.weekday() < 5]
    dates = [d for d in weekdays if d not in REMAPPED]
    assert len(weekdays) == 123 and len(dates) == 120
    assert dates[0] == FIRST and dates[-1] == LAST
    assert all(d in ledger for d in weekdays)
    assert [d.isoformat() for d in dates] == sorted(d.isoformat() for d in dates)
    predecessor_dates = [date(2022, 5, 31), date(2022, 6, 1)] + dates

    table = pq.read_table(SOURCE, columns=["trading_date", "timestamp_utc", "contract", "raw_symbol", "volume"],
                          filters=[("trading_date", ">=", date(2022, 5, 30)),
                                   ("trading_date", "<=", LAST)])
    groups = defaultdict(list)
    for labeled, stamp, contract, raw, volume in zip(*(table[c].to_pylist() for c in table.column_names)):
        corrected = REMAPPED.get(labeled, labeled)
        groups[(corrected, contract)].append((stamp, raw, volume, labeled))
    volumes = {key: sum(r[2] for r in bars) for key, bars in groups.items()}

    def audit(day, prior):
        contracts = sorted(c for d, c in groups if d == day)
        if not contracts:
            raise AssertionError(f"No contracts on {day}")
        ranks = sorted(({"contract": c, "predecessor_volume": volumes.get((prior, c), 0),
                         "current_volume": volumes[(day, c)]} for c in contracts),
                       key=lambda row: (-row["predecessor_volume"], row["contract"]))
        winner = max(contracts, key=lambda c: (volumes.get((prior, c), 0), c))
        selected = groups[(day, winner)]
        raws = sorted({r[1] for r in selected})
        assert len(raws) == 1, (day, raws)
        parts = active_parts(day)
        segments = []
        for start, end in parts:
            grid = {start + timedelta(minutes=i) for i in range(int((end-start).total_seconds() / 60))}
            stamps = [r[0] for r in selected if start <= r[0] < end]
            segments.append({"start_utc": iso(start), "end_utc": iso(end),
                             "expected_minutes": len(grid), "observed_bars": len(stamps),
                             "missing_minutes_utc": [iso(s) for s in sorted(grid - set(stamps))],
                             "duplicate_bars": len(stamps) - len(set(stamps))})
        extra = sorted(r[0] for r in selected if not any(a <= r[0] < b for a, b in parts))
        return {"trade_date": day.isoformat(), "predecessor_trade_date": prior.isoformat(),
                "selected_contract": winner, "selected_raw_symbol": raws[0],
                "historical_selected_contract": ledger[day]["selected_contract"],
                "winner_changed": winner != ledger[day]["selected_contract"],
                "historical_tier": ledger[day]["tier"], "historical_reason": ledger[day]["reason_code"],
                "candidate_volume_rank": ranks, "segments": segments,
                "expected_minutes": sum(s["expected_minutes"] for s in segments),
                "observed_bars": sum(s["observed_bars"] for s in segments),
                "off_grid_selected_bars_utc": [iso(s) for s in extra],
                "coverage_complete_against_candidate_grid": not extra and all(
                    not s["missing_minutes_utc"] and not s["duplicate_bars"] for s in segments)}

    boundary = audit(date(2022, 6, 1), date(2022, 5, 31))
    rows = [audit(day, predecessor_dates[predecessor_dates.index(day)-1]) for day in dates]
    assert all(not r["winner_changed"] for r in rows)
    missing = []
    for row in rows:
        for segment in row["segments"]:
            for stamp in segment["missing_minutes_utc"]:
                missing.append({"trade_date": row["trade_date"], "start_utc": stamp,
                                "end_utc": iso(datetime.fromisoformat(stamp.replace("Z", "+00:00")) + timedelta(minutes=1)),
                                "contract": row["selected_contract"], "raw_symbol": row["selected_raw_symbol"],
                                "session_open_utc": row["segments"][0]["start_utc"]})
    assert len(missing) == 5, missing
    assert {m["trade_date"] for m in missing} == {"2022-06-06", "2022-07-27", "2022-08-16", "2022-08-18", "2022-10-13"}
    assert all(not r["off_grid_selected_bars_utc"] for r in rows)
    assert all(all(s["duplicate_bars"] == 0 for s in r["segments"]) for r in rows)
    prior_candidate = json.loads((ROOT / "calendars/nq-2022-holiday-candidate-v1.json").read_text())
    workbooks = dict(prior_candidate["cme_workbooks"])
    memorial_path = ROOT / "reports/evidence/cme-2022/2022-memorial-day-holiday-schedule.xls"
    workbooks["2022-05-31"] = {"path": str(memorial_path.relative_to(ROOT)),
                               "sha256": "0d1b1f89a315cae22a5857a7027a514e3086c1cccfee42fddddff3caba0c2230",
                               "equity_product_cells": "D2; G5/H5; O5/S5/T5; A74"}
    for evidence in workbooks.values():
        assert digest(ROOT / evidence["path"]) == evidence["sha256"]
    memorial_parts = active_parts(date(2022, 5, 31))
    memorial_bars = groups[(date(2022, 5, 31), "NQM22")]
    memorial_segments = []
    for start, end in memorial_parts:
        grid = {start + timedelta(minutes=i) for i in range(int((end-start).total_seconds()/60))}
        stamps = [r[0] for r in memorial_bars if start <= r[0] < end]
        memorial_segments.append({"start_utc": iso(start), "end_utc": iso(end),
                                  "expected_minutes": len(grid), "observed_bars": len(stamps),
                                  "missing_minutes_utc": [iso(s) for s in sorted(grid-set(stamps))]})
    assert [s["expected_minutes"] for s in memorial_segments] == [1140, 1380]
    assert all(s["expected_minutes"] == s["observed_bars"] and not s["missing_minutes_utc"] for s in memorial_segments)

    har = []
    for i in range(22, 120):
        origin = rows[i-1]
        target = rows[i]
        split = "train" if i < 72 else "validation" if i < 92 else "test"
        origin_end = origin["segments"][-1]["end_utc"]
        target_start = target["segments"][0]["start_utc"]
        target_end = target["segments"][-1]["end_utc"]
        assert origin_end < target_start < target_end
        har.append({"target_ordinal": i+1, "target_trade_date": target["trade_date"],
                    "split": split, "forecast_origin_trade_date": origin["trade_date"],
                    "forecast_origin_after_utc": origin_end,
                    "feature_22_first_trade_date": rows[i-22]["trade_date"],
                    "feature_5_first_trade_date": rows[i-5]["trade_date"],
                    "target_session_start_utc": target_start,
                    "target_available_after_utc": target_end})
    assert Counter(r["split"] for r in har) == {"train": 50, "validation": 20, "test": 28}
    gapped_dates = {gap["trade_date"] for gap in missing}
    contaminated = Counter()
    for i, row in enumerate(har, start=22):
        if any(r["trade_date"] in gapped_dates for r in rows[i-22:i+1]):
            contaminated[row["split"]] += 1

    out = {"schema_version": "1.0", "status": "RESEARCH_CANDIDATE_NOT_CERTIFIED",
           "scope": {"first_trade_date": FIRST.isoformat(), "last_trade_date": LAST.isoformat(),
                     "trade_date_count": len(rows), "civil_weekdays": len(weekdays),
                     "removed_monday_labels": [d.isoformat() for d in sorted(REMAPPED)],
                     "unknown_intervening_weekdays": [d.isoformat() for d in weekdays if d not in ledger]},
           "sources_sha256": {"parquet": digest(SOURCE), "phase3_ledger": digest(LEDGER)},
           "cme_workbooks": workbooks,
           "calendar_basis": "2022 ordinary CME NQ Globex 18:00-17:00 America/New_York; four preserved CME holiday workbooks assign Sunday-Tuesday sessions to Tuesday trade date",
           "memorial_boundary_may_31": {"trade_date": "2022-05-31", "selected_contract": "NQM22",
                                        "segments": memorial_segments,
                                        "corrected_volume_by_contract": {c: volumes[(date(2022, 5, 31), c)]
                                                                         for d, c in groups if d == date(2022, 5, 31)}},
           "predecessor_boundary_june_1": boundary,
           "trade_dates": rows, "active_minute_gaps": missing,
           "coverage": {"complete_dates": sum(r["coverage_complete_against_candidate_grid"] for r in rows),
                        "gapped_dates": [r["trade_date"] for r in rows if not r["coverage_complete_against_candidate_grid"]],
                        "expected_minutes": sum(r["expected_minutes"] for r in rows),
                        "observed_selected_bars": sum(r["observed_bars"] for r in rows),
                        "new_gaps_from_extension": [m for m in missing if m["trade_date"] < "2022-06-07"]},
           "causal_selection": {"changed_winners": [r["trade_date"] for r in rows if r["winner_changed"]],
                                "predecessor_count": len(rows),
                                "retained_panel_volume_completeness_proven": False},
           "remaining_blockers": {
               "official_calendar_guard_dates": ["2022-06-22", "2022-07-06", "2022-09-07",
                                                 "2022-10-10", "2022-10-11", "2022-10-12",
                                                 "2022-11-09", "2022-11-10", "2022-11-11"],
               "external_causal_boundary_calendar": [],
               "active_minute_gap_dates": [gap["trade_date"] for gap in missing],
               "retained_volume_completeness_unverified": True,
               "historical_c_tier_count_unchanged": sum(r["historical_tier"] == "C" for r in rows)},
           "har": {"feature_warmup_sessions": 22, "potential_target_rows": len(har),
                   "split_counts": dict(Counter(r["split"] for r in har)),
                   "rows_touching_unresolved_gaps": {"total": sum(contaminated.values()),
                                                      "by_split": dict(contaminated)},
                   "target_and_origin_rows": har,
                   "availability_limit": "Session-end timestamps are earliest possible RV availability; historical vendor publication latency is unverified."},
           "retrieval": {"authorized": False, "performed": False,
                         "requests": [], "account_specific_estimates": None},
           "preservation": {"source_ohlcv_modified": False, "certification_tiers_modified": False,
                            "production_estimators_modified": False, "historical_har_artifacts_modified": False}}
    if OUTPUT.exists():
        previous = json.loads(OUTPUT.read_text())
        if previous.get("active_minute_gaps") == missing and previous.get("sources_sha256") == out["sources_sha256"]:
            out["retrieval"] = previous.get("retrieval", out["retrieval"])
    OUTPUT.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"dates": len(rows), "expected": out["coverage"]["expected_minutes"],
                      "observed": out["coverage"]["observed_selected_bars"],
                      "gaps": missing, "boundary": {k: boundary[k] for k in (
                          "selected_contract", "historical_tier", "historical_reason", "coverage_complete_against_candidate_grid")},
                      "splits": out["har"]["split_counts"]}, indent=2))


if __name__ == "__main__":
    main()
