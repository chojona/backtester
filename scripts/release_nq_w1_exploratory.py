"""Release the separately versioned, assumption-dependent W1 research series.

This consumes and verifies the frozen NO-GO candidate; it never changes that
candidate, historical certification, or the production selector.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/nq-w1-final-research-dataset"
OUT = ROOT / "results/nq-w1-exploratory-v1.0.0"
VERSION = "nq-w1-exploratory-v1.0.0"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def write(name: str, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return path


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    if OUT.exists():
        raise FileExistsError(f"Immutable version already exists: {OUT}")
    base = read(BASE / "manifest.json")
    assert base["decision"] == "NO-GO" and base["date_count"] == 120
    for name, expected in base["source_sha256"].items():
        assert sha(ROOT / name) == expected, name
    for name, expected in base["output_sha256"].items():
        assert sha(BASE / name) == expected, name
    for line in (BASE / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert sha(BASE / name) == expected, name

    candidate = read(ROOT / "results/nq-w1-120-session-candidate.json")
    old = read(BASE / "daily-estimators-and-decisions.json")["dates"]
    sensitivities = read(BASE / "unresolved-selector-sensitivities.json")
    unknown = {row["target_trade_date"]: row for row in sensitivities}
    assert len(old) == len(candidate["trade_dates"]) == 120 and len(unknown) == 10
    assert len({row["trade_date"] for row in old}) == 120
    guards = set(base["calendar_guards"])
    assert len(guards) == 9
    expected_split = ["warmup"] * 22 + ["train"] * 50 + ["validation"] * 20 + ["test"] * 28
    dates = []
    for i, (row, original) in enumerate(zip(old, candidate["trade_dates"])):
        day = row["trade_date"]
        assert row["ordinal"] == i + 1 and row["split"] == expected_split[i]
        assert day == original["trade_date"] and row["candidate_contract"] == original["selected_contract"]
        assert row["historical_tier_unchanged"] == original["historical_tier"]
        assert row["predecessor_trade_date"] == original["predecessor_trade_date"]
        assert row["active_segments"] == original["segments"]
        assert row["calendar_status"] == ("provisional" if day in guards else "ordinary_rule_or_dated_holiday")
        cutoff = dt(row["observation_cutoff_utc"])
        deadline = dt(row["contract_selection_decision_utc"])
        opening = dt(row["earliest_executable_utc"])
        assert deadline == cutoff + timedelta(minutes=45) and cutoff < deadline < opening
        assert dt(row["assumed_data_finalization_utc"]) == deadline
        assert opening == dt(row["active_segments"][0]["start_utc"])
        if i:
            assert cutoff == dt(old[i - 1]["active_segments"][-1]["end_utc"])
        metrics = row["metrics_conditional_on_candidate_selection_and_calendar"]
        assert row["minute_counts"].get("OBSERVED_TRADE", 0) + row["minute_counts"].get("PROVIDER_OBSERVED_NO_TRADE", 0) == original["expected_minutes"]
        assert metrics["covered_minutes_1m"] == metrics["covered_minutes_5m"] == metrics["covered_minutes_15m"] == original["expected_minutes"]
        assert metrics["unknown_minutes"] == 0
        assert math.isclose(metrics["rv1"], metrics["rs_positive"] + metrics["rs_negative"], abs_tol=1e-15)
        assert all(math.isfinite(metrics[key]) and metrics[key] >= 0 for key in ("rv1", "rv5", "rv15", "rs_positive", "rs_negative", "bpv"))
        uncertainty = unknown.get(day)
        if uncertainty:
            assert original["selected_contract"] == uncertainty["known_leader"]["contract"]
            assert uncertainty["missing_electronic_volume"] is None and uncertainty["independent_upper_bound"] is None
            assert uncertainty["first_unknown_volume_that_changes_winner"] == uncertainty["known_leader"]["volume"] + 1
        dates.append({
            "ordinal": i + 1, "trade_date": day, "split": expected_split[i],
            "predecessor_trade_date": row["predecessor_trade_date"],
            "selected_contract_for_conditional_path": row["candidate_contract"],
            "selected_raw_symbol": original["selected_raw_symbol"],
            "selector_evidence_label": "assumed_existing_path_unresolved_winner" if uncertainty else "provider_supported_retrospective_winner",
            "winner_observed_or_certified": False,
            "unresolved_electronic_volume": ({"contract": uncertainty["unknown_contract"], "value": None,
                                             "first_integer_reversal_volume": uncertainty["first_unknown_volume_that_changes_winner"]} if uncertainty else None),
            "known_ranked_volumes": row["known_ranked_volumes"],
            "calendar_evidence_label": "assumed_ordinary_hours_provisional" if day in guards else "candidate_ordinary_or_dated_holiday",
            "original_calendar_flag": row["calendar_status"],
            "historical_tier_unchanged": row["historical_tier_unchanged"],
            "historical_reason_unchanged": original["historical_reason"],
            "active_segments": row["active_segments"], "minute_counts": row["minute_counts"],
            "daily_estimators": {key: metrics[key] for key in ("rv1", "rv5", "rv15", "rs_positive", "rs_negative", "bpv")},
            "matched_coverage": {key: metrics[key] for key in ("covered_minutes_1m", "covered_minutes_5m", "covered_minutes_15m", "five_minute_blocks", "fifteen_minute_blocks", "bpv_pairs")},
            "observation_cutoff_utc": row["observation_cutoff_utc"],
            "assumed_finalization_utc": row["assumed_data_finalization_utc"],
            "selection_deadline_utc": row["contract_selection_decision_utc"],
            "earliest_execution_utc": row["earliest_executable_utc"],
            "one_session_lag_frozen_selector_usable": False,
        })
    assert sum(d["minute_counts"].get("OBSERVED_TRADE", 0) for d in dates) == 169015
    assert sum(d["minute_counts"].get("PROVIDER_OBSERVED_NO_TRADE", 0) for d in dates) == 5
    assert sum(d["matched_coverage"]["five_minute_blocks"] for d in dates) == 33804
    assert sum(d["matched_coverage"]["fifteen_minute_blocks"] for d in dates) == 11268
    assert sum(d["calendar_evidence_label"] == "assumed_ordinary_hours_provisional" for d in dates) == 9
    assert sum(d["selector_evidence_label"] == "assumed_existing_path_unresolved_winner" for d in dates) == 10

    windows = []
    for end in range(22, 120):
        span = dates[end - 22:end + 1]
        selection_assumptions = [d["trade_date"] for d in span if d["unresolved_electronic_volume"]]
        calendar_assumptions = [d["trade_date"] for d in span if d["calendar_evidence_label"] == "assumed_ordinary_hours_provisional"]
        windows.append({"target_ordinal": end + 1, "target_trade_date": dates[end]["trade_date"],
                        "split": dates[end]["split"], "feature_dates": [d["trade_date"] for d in span[:-1]],
                        "target_date": span[-1]["trade_date"], "assumed_selector_dates": selection_assumptions,
                        "assumed_calendar_dates": calendar_assumptions,
                        "affected_by_ten_selector_assumptions": bool(selection_assumptions)})
    assert len(windows) == 98 and Counter(w["split"] for w in windows) == {"train": 50, "validation": 20, "test": 28}
    assert all(w["feature_dates"] == [d["trade_date"] for d in dates[w["target_ordinal"] - 23:w["target_ordinal"] - 1]] for w in windows)
    affected = [w["target_trade_date"] for w in windows if w["affected_by_ten_selector_assumptions"]]

    # The copied minute ledger is checked row by row before inclusion.
    minute_path = BASE / "minute-classifications.csv.gz"
    counts = Counter()
    minute_dates = Counter()
    with gzip.open(minute_path, "rt", newline="") as stream:
        for item in csv.DictReader(stream):
            counts[item["classification"]] += 1
            minute_dates[item["trade_date"]] += 1
            assert item["classification"] in {"OBSERVED_TRADE", "PROVIDER_OBSERVED_NO_TRADE"}
            if item["classification"] == "PROVIDER_OBSERVED_NO_TRADE":
                assert item["evidence_dbn_sha256"] and float(item["clock_log_return"]) == 0
    assert counts == {"OBSERVED_TRADE": 169015, "PROVIDER_OBSERVED_NO_TRADE": 5}
    assert all(minute_dates[d["trade_date"]] == sum(s["expected_minutes"] for s in d["active_segments"]) for d in dates)

    OUT.mkdir(parents=True)
    write("daily-series.json", {"schema_version": VERSION, "dates": dates})
    write("winner-uncertainty.json", sensitivities)
    write("har-window-impact.json", {"schema_version": VERSION, "window_length_dates": 23,
                                     "windows": windows, "affected_target_dates": affected})
    shutil.copyfile(minute_path, OUT / "minute-classifications.csv.gz")
    source_paths = {**base["source_sha256"],
                    "results/nq-w1-final-research-dataset/manifest.json": sha(BASE / "manifest.json"),
                    "results/nq-w1-final-research-dataset/daily-estimators-and-decisions.json": sha(BASE / "daily-estimators-and-decisions.json"),
                    "results/nq-w1-final-research-dataset/minute-classifications.csv.gz": sha(minute_path),
                    "results/nq-w1-final-research-dataset/unresolved-selector-sensitivities.json": sha(BASE / "unresolved-selector-sensitivities.json"),
                    "scripts/release_nq_w1_exploratory.py": sha(Path(__file__))}
    manifest = {
        "schema_version": VERSION, "decision": "GO_CONDITIONAL_EXPLORATORY_MODEL_DEVELOPMENT",
        "strict_causal_validity": False, "historical_point_in_time_availability_proven": False,
        "har_fitted": False, "historical_certification_changed": False, "production_selector_changed": False,
        "candidate_changed": False, "date_count": 120, "chronology": {"warmup": 22, "train": 50, "validation": 20, "test": 28},
        "retrospective_provider_supported_winners": 110, "unresolved_winner_assumed_paths": 10,
        "unresolved_electronic_volume_cells_remain_unknown": 10, "provisional_calendar_ordinary_hours_assumptions": 9,
        "observed_trade_minutes": 169015, "provider_supported_no_trade_minutes": 5,
        "matched_expected_minutes": 169020, "complete_five_minute_blocks": 33804, "complete_fifteen_minute_blocks": 11268,
        "potential_har_windows": 98, "selector_assumption_affected_har_windows": len(affected),
        "availability_policy": "17:00 ET predecessor close plus assumed 45 minutes; decision 17:45 ET; earliest target execution at target active open; holiday and weekend intervals taken from dated candidate grid",
        "one_completed_session_lag": "FAIL: 120/120 frozen selector decisions miss target opening; no older predecessor substituted",
        "evidence_labels": {"observed": "retained source trade bar", "provider_supported": "bounded source evidence subject to upstream completeness", "assumed": "selected path, provisional ordinary hours, or finalization time", "unresolved": "ten electronic-volume cells and strict causal/calendar certification"},
        "input_sha256": source_paths,
        "output_sha256": {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
    }
    write("manifest.json", manifest)
    (OUT / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.name}\n" for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "SHA256SUMS"))
    print(json.dumps({"decision": manifest["decision"], "dates": len(dates),
                      "affected_windows": len(affected), "manifest_sha256": sha(OUT / "manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
