"""Freeze the W1 evidence ledger without promoting unresolved dates or fitting HAR."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pyarrow.dataset as ds

from backtester.nq_clock_returns_v2 import measure_clock_v2
from scripts.validate_nq_clock_returns_v2 import active_grid, make_minutes
from scripts.validate_nq_w1_five_gap_clock import CANDIDATE, LEDGER, ROOT, RUN, SOURCE, verify_evidence

OUT = ROOT / "results/nq-w1-final-research-dataset"
RECON = ROOT / "results/nq-w1-twelve-gap-reconciliation.json"
REPLAY = ROOT / "results/nq-w1-front-three-acquisition-replay.json"
ACQUISITION = ROOT / "data/raw/databento/NQ/w1-electronic-volume-20261015T113810546399Z/acquisition-manifest.json"
SEAL = ACQUISITION.parent / "run-seal.json"
CALENDAR = ROOT / "reports/nq-w1-final-calendar-readiness.md"
POLICY = "nq-w1-exploratory-clock-and-availability-v1.1.0-draft"
GUARDS = {"2022-06-22", "2022-07-06", "2022-09-07", "2022-10-10", "2022-10-11",
          "2022-10-12", "2022-11-09", "2022-11-10", "2022-11-11"}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return path


def rv15(rows, returns):
    total, blocks, covered = [], 0, 0
    group, prior = [], None
    for row, ret in zip(rows, returns):
        key = (row.active_id, row.research_segment)
        if key != prior:
            for i in range(0, len(group) - 14, 15):
                total.append(math.fsum(group[i:i + 15]) ** 2)
                blocks += 1
                covered += 15
            group = []
        assert ret is not None
        group.append(ret)
        prior = key
    for i in range(0, len(group) - 14, 15):
        total.append(math.fsum(group[i:i + 15]) ** 2)
        blocks += 1
        covered += 15
    return math.fsum(total), blocks, covered


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    candidate = json.loads(CANDIDATE.read_text())
    replay = json.loads(REPLAY.read_text())
    recon = json.loads(RECON.read_text())
    prior_clock = json.loads((ROOT / "results/nq-clock-returns-v2.0.0/daily-series.json").read_text())
    evidence = verify_evidence(json.loads((RUN / "manifest.json").read_text()), candidate)
    assert len(candidate["trade_dates"]) == len(replay["dates"]) == len(prior_clock["dates"]) == 120
    assert len(recon["cells"]) == 12
    assert sha(ACQUISITION) == replay["acquisition_manifest_sha256"]
    seal = json.loads(SEAL.read_text())
    assert seal["file_count"] == len(seal["files"]) == 154
    for item in seal["files"]:
        path = SEAL.parent / item["name"]
        assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"]
    unknown = {c["target_trade_date"]: c for c in recon["cells"] if c["supported_electronic_volume"] is None}
    assert len(unknown) == 10
    # Recheck every retained acquisition file without altering the raw run.
    first = candidate["trade_dates"][0]["segments"][0]["start_utc"]
    last = candidate["trade_dates"][-1]["segments"][-1]["end_utc"]
    from scripts.validate_nq_clock_returns_v2 import utc
    table = ds.dataset(SOURCE, format="parquet").to_table(
        columns=["timestamp_utc", "raw_symbol", "contract", "open", "high", "low", "close", "volume"],
        filter=(ds.field("timestamp_utc") >= utc(first)) & (ds.field("timestamp_utc") < utc(last)))
    bars = {}
    for bar in table.to_pylist():
        key = (bar["raw_symbol"], bar["timestamp_utc"])
        assert key not in bars
        bars[key] = bar
    dates, total_minutes = [], 0
    csv_path = OUT / "minute-classifications.csv.gz"
    with csv_path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            import io
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["trade_date", "minute_utc", "contract", "active_id", "research_segment",
                                 "classification", "source_close_or_carried_price", "clock_log_return", "evidence_dbn_sha256"])
                for ordinal, (day, selected) in enumerate(zip(candidate["trade_dates"], replay["dates"]), 1):
                    assert day["trade_date"] == selected["target_trade_date"]
                    rows = make_minutes(day, bars, evidence)
                    measured = measure_clock_v2(rows)
                    assert measured["complete"]
                    metrics = dict(measured["metrics"])
                    metrics["rv15"], metrics["fifteen_minute_blocks"], metrics["covered_minutes_15m"] = rv15(rows, measured["returns"])
                    metrics["covered_minutes_1m"] = len(rows)
                    metrics["covered_minutes_5m"] = 5 * metrics["five_minute_blocks"]
                    assert abs(metrics["rv1"] - metrics["rs_positive"] - metrics["rs_negative"]) < 1e-15
                    assert metrics["covered_minutes_1m"] == metrics["covered_minutes_5m"] == metrics["covered_minutes_15m"] == day["expected_minutes"]
                    assert len(rows) == day["expected_minutes"]
                    prior = prior_clock["dates"][ordinal - 1]
                    assert prior["trade_date"] == day["trade_date"]
                    for field in ("rv1", "rv5", "rs_positive", "rs_negative", "bpv"):
                        assert math.isclose(metrics[field], prior["metrics"][field], rel_tol=0, abs_tol=2e-15)
                    assert all(math.isfinite(metrics[field]) and metrics[field] >= 0 for field in
                               ("rv1", "rv5", "rv15", "rs_positive", "rs_negative", "bpv"))
                    for row, price, ret, cls in zip(rows, measured["prices"], measured["returns"], measured["sources"]):
                        writer.writerow([day["trade_date"], row.start.isoformat().replace("+00:00", "Z"),
                                         row.contract, row.active_id, row.research_segment, cls,
                                         format(price, ".12g"), format(ret, ".17g"),
                                         row.evidence.trade_response_sha256 if row.evidence else ""])
                    total_minutes += len(rows)
                    predecessor_end = utc(candidate["trade_dates"][ordinal - 2]["segments"][-1]["end_utc"]) if ordinal > 1 else utc("2022-06-01T21:00:00Z")
                    target_open = utc(day["segments"][0]["start_utc"])
                    decision = predecessor_end + timedelta(minutes=45)
                    assert predecessor_end < decision < target_open
                    status = "unresolved" if day["trade_date"] in unknown else "provider_stream_assumption"
                    dates.append({"ordinal": ordinal, "trade_date": day["trade_date"],
                                  "split": "warmup" if ordinal <= 22 else "train" if ordinal <= 72 else "validation" if ordinal <= 92 else "test",
                                  "predecessor_trade_date": day["predecessor_trade_date"],
                                  "candidate_contract": day["selected_contract"],
                                  "selector_status": status, "known_ranked_volumes": selected["ranked_volumes"],
                                  "unknown_competitors": [c["contract"]] if (c := unknown.get(day["trade_date"])) else [],
                                  "calendar_status": "provisional" if day["trade_date"] in GUARDS else "ordinary_rule_or_dated_holiday",
                                  "active_segments": day["segments"], "minute_counts": dict(Counter(measured["sources"])),
                                  "metrics_conditional_on_candidate_selection_and_calendar": metrics,
                                  "observation_cutoff_utc": predecessor_end.isoformat().replace("+00:00", "Z"),
                                  "assumed_data_finalization_utc": decision.isoformat().replace("+00:00", "Z"),
                                  "contract_selection_decision_utc": decision.isoformat().replace("+00:00", "Z"),
                                  "earliest_executable_utc": target_open.isoformat().replace("+00:00", "Z"),
                                  "one_session_lag_selector_usable": False,
                                  "historical_tier_unchanged": day["historical_tier"],
                                  "research_ready": False})
    assert total_minutes == 169020 and Counter(d["split"] for d in dates) == {"warmup": 22, "train": 50, "validation": 20, "test": 28}
    assert sum(d["minute_counts"].get("PROVIDER_OBSERVED_NO_TRADE", 0) for d in dates) == 5
    assert sum(d["minute_counts"].get("OBSERVED_TRADE", 0) for d in dates) == 169015
    assert sum(d["metrics_conditional_on_candidate_selection_and_calendar"]["five_minute_blocks"] for d in dates) == 33804
    assert sum(d["metrics_conditional_on_candidate_selection_and_calendar"]["fifteen_minute_blocks"] for d in dates) == 11268
    write_json("daily-estimators-and-decisions.json", {"policy_version": POLICY, "status": "NO-GO", "dates": dates})
    sensitivity = [{"target_trade_date": c["target_trade_date"], "predecessor_trade_date": c["predecessor_cme_trade_date"],
                    "unknown_contract": c["contract"], "known_leader": c["known_leader"],
                    "later_cleared_diagnostic_only": c["later_cleared"]["quantity"],
                    "missing_electronic_volume": None, "independent_upper_bound": None,
                    "tie_at_leader_volume_winner": c["counterfactual_tie_at_leader_volume_winner"],
                    "first_unknown_volume_that_changes_winner": c["counterfactual_min_missing_volume_to_change_winner"],
                    "scenario_0_to_leader_inclusive": "known leader remains winner under frozen tie rule; assumption only",
                    "scenario_above_leader": "unknown contract wins; recompute selected minute path and all affected 23-date windows",
                    "status": "unresolved"} for c in unknown.values()]
    write_json("unresolved-selector-sensitivities.json", sensitivity)
    sources = [CANDIDATE, REPLAY, RECON, ACQUISITION, SEAL, RUN / "manifest.json", SOURCE, LEDGER, CALENDAR,
               ROOT / "results/nq-clock-returns-v2.0.0/daily-series.json",
               ROOT / "scripts/build_nq_w1_final_research_dataset.py",
               ROOT / "backtester/nq_clock_returns_v2.py",
               ROOT / "scripts/validate_nq_clock_returns_v2.py"]
    sources += sorted((ROOT / "reports/evidence/cme-2022").glob("*.xls"))
    manifest = {"schema_version": "nq-w1-final-research-dataset-v1.0.0", "decision": "NO-GO",
                "research_ready": False, "har_fitted": False, "production_selector_changed": False,
                "policy_version": POLICY, "calendar_guards": sorted(GUARDS),
                "unresolved_selector_dates": sorted(unknown), "date_count": 120,
                "minute_count": total_minutes, "selected_bar_count": 169015, "provider_no_trade_count": 5,
                "chronology": {"warmup": 22, "train": 50, "validation": 20, "test": 28},
                "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources},
                "output_sha256": {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.name not in {"manifest.json", "SHA256SUMS"} and p.is_file()},
                "one_session_lag_result": "120/120 frozen predecessor decisions unusable if completed predecessor data arrive only after next session; no older-predecessor substitution"}
    write_json("manifest.json", manifest)
    (OUT / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.name}\n" for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "SHA256SUMS"))
    print(json.dumps({"decision": "NO-GO", "dates": len(dates), "minutes": total_minutes,
                      "unknown_selector_dates": len(unknown), "calendar_guards": len(GUARDS),
                      "manifest_sha256": sha(OUT / "manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
