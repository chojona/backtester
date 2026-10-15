"""Replay the frozen front-three feasibility from a completed W1 acquisition."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "results/nq-w1-targeted-remediation-plan.json"
BASE = ROOT / "results/nq-front-three-selector-feasibility.json"
CANDIDATE = ROOT / "results/nq-w1-120-session-candidate.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(request: dict) -> str:
    return json.dumps(request, sort_keys=True, separators=(",", ":"))


def clean(response: dict | None, run: Path, symbol: str) -> bool:
    if not response or not response.get("metadata_exact_request"):
        return False
    meta = response["metadata"]
    if meta.get("partial") != [] or meta.get("not_found") != []:
        return False
    if not response.get("decoded", {}).get("raw_symbol_mapping_present"):
        return False
    if set(meta.get("mappings", {})) != {symbol}:
        return False
    for name, hash_name in (("dbn_file", "dbn_sha256"), ("jsonl_file", "jsonl_sha256")):
        path = run / response[name]
        if not path.is_file() or digest(path) != response[hash_name]:
            return False
    return True


def status_active(response: dict, run: Path) -> bool:
    events = [json.loads(line) for line in (run / response["jsonl_file"]).read_text().splitlines()]
    return bool(events) and any(x.get("is_trading") == "Y" for x in events) and all(
        x.get("is_trading") in {"Y", "~"} for x in events
    )


def main(run: Path) -> None:
    run = run.resolve()
    manifest_path = run / "acquisition-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads(PLAN.read_text())
    base = json.loads(BASE.read_text())
    candidate = json.loads(CANDIDATE.read_text())
    if not manifest["completed"] or manifest["plan_sha256"] != digest(PLAN) or manifest["inventory_sha256"] != digest(BASE):
        raise ValueError("Acquisition is incomplete or source hashes changed")
    if manifest["candidate_sha256"] != digest(CANDIDATE) or len(manifest["quotes"]) != 80:
        raise ValueError("Acquisition does not match the frozen 80-request scope")
    by_request = {key(r["request"]): r for r in manifest["responses"]}
    if len(by_request) != len(manifest["responses"]):
        raise ValueError("Duplicate acquired response")
    for response in manifest["responses"]:
        path = run / response["jsonl_file"]
        records = [json.loads(line) for line in path.read_text().splitlines()]
        if len(records) != response["returned_records"]:
            raise ValueError("Decoded record count differs from preserved response")
        schema = response["request"]["schema"]
        if schema in {"trades", "ohlcv-1m"}:
            seen = set()
            volume = 0
            for record in records:
                identity = json.dumps(record, sort_keys=True, separators=(",", ":"))
                if schema == "trades" and identity in seen:
                    continue
                seen.add(identity)
                volume += int(record["size" if schema == "trades" else "volume"])
            if volume != response["decoded"]["electronic_volume"]:
                raise ValueError("Recomputed electronic volume differs from preserved response")
    cells = {}
    for cell in plan["predecessor_cells"]:
        symbol = cell["raw_symbol"]
        segment_evidence = []
        for segment in cell["segments"]:
            base_request = {"dataset": "GLBX.MDP3", "symbols": [symbol], "stype_in": "raw_symbol",
                            "start": segment["start_utc"], "end": segment["end_utc"]}
            response = lambda schema: by_request.get(key(dict(base_request, schema=schema)))
            bar, trades, status = response("ohlcv-1m"), response("trades"), response("status")
            if cell["classification"] == "not_requested" and clean(bar, run, symbol) and bar["returned_records"] > 0:
                item = {"classification": "positive_volume", "volume": bar["decoded"]["electronic_volume"],
                        "source_dbn_sha256": bar["dbn_sha256"], "schema": "ohlcv-1m"}
                if item["volume"] <= 0:
                    item["classification"] = "provider_gap"
            elif cell["classification"] == "not_requested" and not clean(bar, run, symbol):
                item = {"classification": "provider_gap", "reason": "OHLCV response missing or unclean"}
            elif not clean(trades, run, symbol) or not clean(status, run, symbol):
                item = {"classification": "provider_gap", "reason": "trade or status response missing or unclean"}
            elif trades["returned_records"] > 0 and trades["decoded"]["electronic_volume"] > 0:
                item = {"classification": "positive_volume", "volume": trades["decoded"]["electronic_volume"],
                        "source_dbn_sha256": trades["dbn_sha256"], "schema": "trades"}
            elif trades["returned_records"] == 0 and status_active(status, run):
                item = {"classification": "provider_observed_zero", "volume": 0,
                        "trade_dbn_sha256": trades["dbn_sha256"], "status_dbn_sha256": status["dbn_sha256"]}
            else:
                item = {"classification": "provider_gap", "reason": "ambiguous trade or active-status evidence"}
            item["start_utc"], item["end_utc"] = segment["start_utc"], segment["end_utc"]
            segment_evidence.append(item)
        kinds = {x["classification"] for x in segment_evidence}
        if "provider_gap" in kinds:
            classification, volume = "provider_gap", None
        elif kinds <= {"positive_volume", "provider_observed_zero"}:
            volume = sum(x["volume"] for x in segment_evidence)
            classification = "positive_volume" if volume > 0 else "provider_observed_zero"
        else:
            classification, volume = "unresolved", None
        contradiction = classification == "provider_observed_zero" and cell["later_cleared_volume_diagnostic_only"] > 0
        if contradiction:
            classification = "provider_gap"
            volume = None
        cells[cell["target_trade_date"]] = {"target_trade_date": cell["target_trade_date"],
            "contract": cell["contract"], "raw_symbol": symbol, "classification": classification,
            "electronic_volume": volume, "segments": segment_evidence,
            "later_cleared_volume_diagnostic_only": cell["later_cleared_volume_diagnostic_only"],
            "contradictory_later_cleared_diagnostic": contradiction,
            "provider_stream_completeness": "bounded authenticated DBN only; venue completeness unverified",
            "exchange_wide_certified": False}
    dates = []
    for original in base["dates"]:
        target = original["target_trade_date"]
        resolved = cells.get(target)
        volumes = {c["contract"]: c["predecessor_electronic_volume"] for c in original["cells"]
                   if c["classification"] == "requested_observed_volume"}
        if resolved and resolved["classification"] in {"positive_volume", "provider_observed_zero"}:
            volumes[resolved["contract"]] = resolved["electronic_volume"]
        unknown = [c["contract"] for c in original["cells"] if c["contract"] not in volumes]
        winner = max(volumes, key=lambda c: (volumes[c], c)) if len(volumes) == 3 else None
        dates.append({"target_trade_date": target, "winner": winner, "legacy_winner": original["legacy_selected_contract"],
                      "disagrees_with_legacy": winner is not None and winner != original["legacy_selected_contract"],
                      "unknown_competitors": unknown, "ranked_volumes": sorted(volumes.items(), key=lambda x: (x[1], x[0]), reverse=True)})
    by_date = {d["target_trade_date"]: d for d in dates}
    chronology = []
    for row in base["har_chronology"]:
        unresolved = [day for day in row["selector_window_trade_dates"] if by_date[day]["winner"] is None]
        chronology.append({"target_trade_date": row["target_trade_date"], "split": row["split"],
                           "unresolved_selector_dates": unresolved, "selector_window_complete": not unresolved,
                           "retained_selected_bar_gap_dates": row["retained_selected_bar_gap_dates"],
                           "full_row_supported_without_dropping_dates": not unresolved and not row["retained_selected_bar_gap_dates"]})
    counts = Counter(x["classification"] for x in cells.values())
    result = {"schema_version": "nq-w1-front-three-replay-v1", "acquisition_manifest_sha256": digest(manifest_path),
              "plan_sha256": digest(PLAN), "inventory_sha256": digest(BASE), "candidate_sha256": digest(CANDIDATE),
              "provider_stream_completeness_assumption": "An authenticated, exact, unpartial Databento response with valid raw-symbol mapping covers the provider stream over its bounded interval; this retrospective assumption is not an exchange-wide or point-in-time certification.",
              "classification_counts": dict(counts), "cells": list(cells.values()), "dates": dates,
              "selector_replay": {"dates": 120, "resolved_winners": sum(x["winner"] is not None for x in dates),
                                  "indeterminate_winners": sum(x["winner"] is None for x in dates),
                                  "legacy_disagreements": [x["target_trade_date"] for x in dates if x["disagrees_with_legacy"]],
                                  "exchange_wide_certified_dates": 0},
              "har_chronology": {"warmup": 22, "train": 50, "validation": 20, "test": 28,
                                  "potential_rows": 98, "rows_with_unresolved_selector_window": sum(
                                      bool(x["unresolved_selector_dates"]) for x in chronology),
                                  "rows_with_retained_selected_bar_gap": sum(bool(x["retained_selected_bar_gap_dates"]) for x in chronology),
                                  "rows_supported_without_dropping_dates": sum(x["full_row_supported_without_dropping_dates"] for x in chronology),
                                  "rows": chronology}}
    out = ROOT / "results/nq-w1-front-three-acquisition-replay.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"result": str(out), "classifications": dict(counts), "selector": result["selector_replay"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    main(parser.parse_args().run)
