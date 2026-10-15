"""Read-only, independent NQ selector evidence register for the 2022 W1 run.

Rebuilds electronic totals from retained minute bars. It never feeds a result
back to acceptance, certification, or HAR. Run from any directory with python3.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"
CANDIDATE = ROOT / "results/nq-w1-120-session-candidate.json"
CLEARED = ROOT / "results/nq-definition-statistics-evidence.json"
ACQUISITION = ROOT / "data/raw/databento/NQ/definition-statistics-20261014T223138Z/acquisition.json"
OUTPUT = ROOT / "results/nq-causal-contract-selection-register.json"
MONTH_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ns(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()) * 1_000_000_000


def iso(n: int) -> str:
    seconds, nanos = divmod(n, 1_000_000_000)
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


def third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


def rule_roster(target: str) -> list[str]:
    day = date.fromisoformat(target)
    quarters = [(year, month) for year in range(day.year, day.year + 7)
                for month in MONTH_CODE if third_friday(year, month) >= day][:5]
    last_year, last_month = quarters[-1]
    decembers = [(year, 12) for year in range(day.year, day.year + 8)
                 if (year, 12) > (last_year, last_month)][:4]
    return [f"NQ{MONTH_CODE[month]}{year % 100:02d}" for year, month in quarters + decembers]


def build_register() -> dict:
    candidate = json.loads(CANDIDATE.read_text())
    cleared = json.loads(CLEARED.read_text())
    acquisition = json.loads(ACQUISITION.read_text())
    assert sha(PARQUET) == candidate["sources_sha256"]["parquet"]
    assert acquisition["completed"] and len(acquisition["responses"]) == 2
    for response in acquisition["responses"]:
        assert sha(ACQUISITION.parent / response["dbn_file"]) == response["dbn_sha256"]
    assert cleared["source"]["acquisition_sha256"] == sha(ACQUISITION)
    assert cleared["source"]["definition_dbn_sha256"] == acquisition["responses"][0]["dbn_sha256"]
    assert cleared["source"]["statistics_dbn_sha256"] == acquisition["responses"][1]["dbn_sha256"]

    manifests = []
    manifest_root = ROOT / "data/raw/databento/NQ/full-history/8c2dcea828fa59a0"
    for path in sorted(manifest_root.glob("*/manifest.json")):
        item = json.loads(path.read_text())
        request = item["request"]
        assert item["download_complete"] and request["dataset"] == "GLBX.MDP3"
        assert request["schema"] == "ohlcv-1m"
        manifests.append((path, ns(request["start"]), ns(request["end"]), set(request["symbols"])))
    assert len(manifests) == 67

    entries = [candidate["predecessor_boundary_june_1"], *candidate["trade_dates"]]
    assert len(entries) == 121
    segments = {e["trade_date"]: [(ns(s["start_utc"]), ns(s["end_utc"])) for s in e["segments"]]
                for e in entries}
    for e in entries:
        assert all(a < b for a, b in segments[e["trade_date"]])
    lower = min(a for rows in segments.values() for a, _ in rows)
    upper = max(b for rows in segments.values() for _, b in rows)
    bars = defaultdict(lambda: {"volume": 0, "count": 0, "last_bar_start_ns": None})
    seen = set()
    pf = pq.ParquetFile(PARQUET)
    for batch in pf.iter_batches(columns=["ts_event_ns", "contract", "volume"]):
        columns = batch.to_pydict()
        for t, contract, volume in zip(columns["ts_event_ns"], columns["contract"], columns["volume"]):
            if not lower <= t < upper:
                continue
            for day, active in segments.items():
                if any(a <= t < b for a, b in active):
                    key = (day, contract, t)
                    if key in seen:
                        raise ValueError(f"Duplicate retained bar: {key}")
                    seen.add(key)
                    row = bars[(day, contract)]
                    row["volume"] += volume
                    row["count"] += 1
                    row["last_bar_start_ns"] = max(t, row["last_bar_start_ns"] or t)
                    break
    del seen

    cleared_cells = {(r["target_trade_date"], r["contract"]): r for r in cleared["cells"]}
    identities = {r["contract"]: r for r in cleared["identities"].values()}
    register = []
    for entry in candidate["trade_dates"]:
        target, predecessor = entry["trade_date"], entry["predecessor_trade_date"]
        origin = max(b for _, b in segments[predecessor])
        assert origin == ns(next(r for r in cleared["dates"] if r["target_trade_date"] == target)["origin_utc"])
        roster = rule_roster(target)
        assert roster == next(r for r in cleared["dates"] if r["target_trade_date"] == target)["expected_roster"]
        candidates = []
        for contract in roster:
            row = bars.get((predecessor, contract))
            later = cleared_cells[(target, contract)]
            definition = identities.get(contract)
            # Historical definitions are retrospective messages, not a full
            # contemporaneous security-definition book or feed certificate.
            definition_valid = bool(definition and later["definition_identity_valid_at_origin"])
            first_cleared = later["first_cleared_ts_recv_ns"]
            raw_symbol = later["raw_symbol"]
            # A request can cover a segmented CME trade date across chunks.
            segment_requests = [[str(path.relative_to(ROOT)) for path, a, b, symbols in manifests
                                 if raw_symbol in symbols and a <= start and end <= b]
                                for start, end in segments[predecessor]]
            fully_requested = all(segment_requests)
            candidates.append({
                "contract": contract,
                "rule_eligible": True,
                "definition_identity_valid_at_origin": definition_valid,
                "definition_first_provider_receipt_utc": definition["first_definition_received_utc"] if definition else None,
                "definition_activation_utc": definition["activation_utc"] if definition else None,
                "definition_expiration_utc": definition["expiration_utc"] if definition else None,
                "raw_symbol": raw_symbol,
                "electronic_source_segment_requests": segment_requests,
                "electronic_source_requested_all_segments": fully_requested,
                "retained_electronic_volume": row["volume"] if row else None,
                "retained_bar_count": row["count"] if row else 0,
                "last_bar_start_utc": iso(row["last_bar_start_ns"]) if row else None,
                "last_observed_bar_completion_utc": iso(row["last_bar_start_ns"] + 60_000_000_000) if row else None,
                "electronic_volume_coverage": "observed_lower_bound_feed_completeness_unverified" if row else
                                              ("requested_no_bar_zero_unproven" if fully_requested else "not_requested_all_segments"),
                "electronic_volume_provider_available_utc": None,
                "electronic_volume_available_by_origin": None,
                "later_cleared_volume": later["latest_in_window_quantity"],
                "later_cleared_first_event_utc": iso(later["first_cleared_ts_event_ns"]) if later["first_cleared_ts_event_ns"] else None,
                "later_cleared_first_provider_receipt_utc": iso(first_cleared) if first_cleared else None,
                "later_cleared_available_by_origin": bool(first_cleared and first_cleared <= origin),
                "later_cleared_message_count": later["valid_cleared_message_count"],
                "later_cleared_explicit_zero": later["explicit_zero"],
            })
            assert (row["volume"] if row else None) == later["retained_globex_ohlcv_volume"]
        known = sorted((c for c in candidates if c["retained_electronic_volume"] is not None),
                       key=lambda c: (c["retained_electronic_volume"], c["contract"]), reverse=True)
        later_known = sorted((c for c in candidates if c["later_cleared_volume"] is not None),
                             key=lambda c: (c["later_cleared_volume"], c["contract"]), reverse=True)
        current = {contract for (day, contract), row in bars.items() if day == target and row["count"]}
        replay = max(current, key=lambda c: (bars.get((predecessor, c), {}).get("volume", 0), c))
        assert replay == entry["historical_selected_contract"]
        historical = entry["historical_selected_contract"]
        known_winner = known[0]["contract"] if known else None
        unknown = [c["contract"] for c in candidates if c["retained_electronic_volume"] is None]
        reasons = []
        if len(candidates) != 9 or not all(c["definition_identity_valid_at_origin"] for c in candidates):
            reasons.append("rule_or_retrieved_definition_identity_incomplete")
        reasons.append("complete_asof_venue_definition_book_unverified")
        if unknown:
            reasons.append("eligible_predecessor_electronic_volumes_unknown:" + ",".join(unknown))
        reasons.append("retained_electronic_request_did_not_certify_all_candidate_feed_coverage")
        reasons.append("electronic_volume_provider_availability_at_origin_unrecorded")
        if known_winner != historical:
            status = "contradicted"
            reasons.append("known_electronic_volume_leader_differs_from_historical_winner")
        else:
            status = "unresolved"
            reasons.append("known_subset_supports_historical_winner_but_full_causal_rank_unestablished")
        register.append({
            "target_trade_date": target, "predecessor_cme_trade_date": predecessor,
            "predecessor_active_segments_utc": [{"start_utc": iso(a), "end_utc": iso(b)} for a, b in segments[predecessor]],
            "predecessor_observation_complete_utc": iso(origin),
            "decision_origin_utc": iso(origin),
            "roster_rule_effective_trade_date": "2022-05-23",
            "rule_derived_roster": roster,
            "asof_venue_roster_complete": False,
            "electronic_volume_coverage_complete": False,
            "electronic_volume_available_at_origin": False,
            "candidates": candidates,
            "known_electronic_rank": [{"contract": c["contract"], "volume": c["retained_electronic_volume"]} for c in known],
            "unknown_electronic_volume_contracts": unknown,
            "historical_selector_replay": replay,
            "historical_selected_contract": historical,
            "known_subset_winner": known_winner,
            "later_observed_cleared_rank": [{"contract": c["contract"], "volume": c["later_cleared_volume"]} for c in later_known],
            "later_cleared_rank_complete": len(later_known) == len(roster),
            "status": status, "causally_validated": False, "reasons": reasons,
        })
    result = {
        "schema_version": 1,
        "scope": "2022-06-02 through 2022-11-21 W1 target CME trade dates",
        "rule": "Five consecutive March-cycle quarters and four further Decembers, effective 2022-05-23; max(volume, contract code) tie break",
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (PARQUET, CANDIDATE, CLEARED, ACQUISITION)},
        "electronic_request_manifest_sha256": {str(path.relative_to(ROOT)): sha(path) for path, _, _, _ in manifests},
        "source_role": {"parquet": "retained electronic OHLCV observation, not complete venue volume",
                        "definition_and_statistics": "retrospective identity and later cleared-volume comparison",
                        "candidate": "corrected trade-date segments and retained historical decisions"},
        "summary": {"dates": len(register),
                    "historical_replay_matches": sum(r["historical_selector_replay"] == r["historical_selected_contract"] for r in register),
                    "unknown_electronic_cells": sum(len(r["unknown_electronic_volume_contracts"]) for r in register),
                    "causally_validated": sum(r["causally_validated"] for r in register),
                    "status_counts": {s: sum(r["status"] == s for r in register) for s in ("independently_established", "provisionally_supported", "contradicted", "unresolved")}},
        "dates": register,
    }
    return result


def main() -> None:
    result = build_register()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
