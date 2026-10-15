"""Read-only verification of the frozen W1 acquisition and twelve-cell replay."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/raw/databento/NQ/w1-electronic-volume-20261015T113810546399Z"
OUT = ROOT / "results/nq-w1-twelve-gap-reconciliation.json"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ns(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()) * 1_000_000_000 + int(iso.split(".")[1][:9]) if "." in iso else int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()) * 1_000_000_000


def utc(nanos):
    return datetime.fromtimestamp(nanos // 1_000_000_000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos % 1_000_000_000:09d}Z"


def key(request):
    return json.dumps(request, sort_keys=True, separators=(",", ":"))


def records(response):
    return [json.loads(line) for line in (RUN / response["jsonl_file"]).read_text().splitlines()]


def main():
    manifest = read(RUN / "acquisition-manifest.json")
    approved = read(RUN / "approved-requests.json")
    seal = read(RUN / "run-seal.json")
    replay = read(ROOT / "results/nq-w1-front-three-acquisition-replay.json")
    plan = read(ROOT / "results/nq-w1-targeted-remediation-plan.json")
    base = read(ROOT / "results/nq-front-three-selector-feasibility.json")
    definition = read(ROOT / "results/nq-definition-statistics-evidence.json")
    assert manifest["completed"] and len(manifest["responses"]) == 74
    assert len(manifest["quotes"]) == len(approved["requests"]) == 80
    assert len(manifest["skipped_conditional_requests"]) == 6
    assert manifest["plan_sha256"] == approved["plan_sha256"] == sha(ROOT / "results/nq-w1-targeted-remediation-plan.json")
    assert manifest["inventory_sha256"] == sha(ROOT / "results/nq-front-three-selector-feasibility.json")
    assert manifest["candidate_sha256"] == sha(ROOT / "results/nq-w1-120-session-candidate.json")
    assert replay["acquisition_manifest_sha256"] == sha(RUN / "acquisition-manifest.json")
    assert sha(RUN / "acquisition-manifest.json") == (RUN / "acquisition-manifest.sha256").read_text().split()[0]
    assert seal["file_count"] == len(seal["files"]) == 154
    for item in seal["files"]:
        path = RUN / item["name"]
        assert path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], path
    assert len({x["name"] for x in seal["files"]}) == 154
    quoted = {q["request_id"]: q for q in approved["requests"]}
    assert len(quoted) == 80
    assert [q["request_id"] for q in manifest["quotes"]] == list(quoted)
    for q in approved["requests"]:
        req = q["request"]
        identity = [req["schema"], req["symbols"][0], req["start"], req["end"]]
        assert q["request_id"] == hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()
    by_request = {}
    schema_counts = Counter()
    for response in manifest["responses"]:
        request = response["request"]
        assert response["metadata_exact_request"]
        q = approved["requests"][response["quote_index"] - 1]
        assert response["target_trade_date"] == q["target_trade_date"]
        assert response["predecessor_cme_trade_date"] == q["predecessor_cme_trade_date"]
        assert request == q["request"] and response["phase"] == q["phase"]
        assert response["quoted_cost_usd"] == manifest["quotes"][response["quote_index"] - 1]["estimated_cost_usd"]
        assert key(request) not in by_request
        by_request[key(request)] = response
        meta = response["metadata"]
        assert meta["dataset"] == request["dataset"] == "GLBX.MDP3"
        assert meta["schema"] == request["schema"]
        assert meta["symbols"] == request["symbols"] and meta["stype_in"] == "raw_symbol"
        assert meta["start"] == ns(request["start"]) and meta["end"] == ns(request["end"])
        assert meta["limit"] is None and meta["partial"] == meta["not_found"] == []
        assert set(meta["mappings"]) == set(request["symbols"])
        for field, size, digest in (("dbn_file", "dbn_bytes", "dbn_sha256"), ("jsonl_file", "jsonl_bytes", "jsonl_sha256")):
            path = RUN / response[field]
            assert path.stat().st_size == response[size] and sha(path) == response[digest]
        raw = db.DBNStore.from_file(RUN / response["dbn_file"])
        assert raw.metadata.schema == meta["schema"] and raw.metadata.start == meta["start"] and raw.metadata.end == meta["end"]
        assert raw.metadata.symbols == meta["symbols"] and raw.metadata.partial == meta["partial"] and raw.metadata.not_found == meta["not_found"]
        rows = records(response)
        assert len(rows) == response["returned_records"] == sum(1 for _ in raw)
        sizes = []
        for row in rows:
            h = row["hd"]
            assert meta["start"] <= int(h["ts_event"]) < meta["end"]
            assert str(h["instrument_id"]) in {m["symbol"] for m in meta["mappings"][request["symbols"][0]]}
            if request["schema"] in ("trades", "ohlcv-1m"):
                sizes.append(int(row["size"] if request["schema"] == "trades" else row["volume"]))
        if sizes:
            assert sum(sizes) == response["decoded"]["electronic_volume"]
        else:
            assert response["decoded"]["electronic_volume"] in (0, None)
        schema_counts[request["schema"]] += 1
    assert len(by_request) == 74
    assert len({x["quote_index"] for x in manifest["responses"] + manifest["skipped_conditional_requests"]}) == 80
    assert all(x["request"] == approved["requests"][x["quote_index"] - 1]["request"] for x in manifest["skipped_conditional_requests"])
    assert definition["source"]["volume_stream_sha256"] == sha(ROOT / "results/nq-cleared-volume-stream.jsonl")
    assert definition["source"]["definition_dbn_sha256"] == sha(ROOT / "data/raw/databento/NQ/definition-statistics-20261014T223138Z/01-definition.dbn.zst")
    assert definition["source"]["statistics_dbn_sha256"] == sha(ROOT / "data/raw/databento/NQ/definition-statistics-20261014T223138Z/02-statistics.dbn.zst")
    raw_definition = list(db.DBNStore.from_file(ROOT / "data/raw/databento/NQ/definition-statistics-20261014T223138Z/01-definition.dbn.zst"))
    assert len(raw_definition) == definition["record_counts"]["definition"]
    cleared_stream = [json.loads(line) for line in (ROOT / "results/nq-cleared-volume-stream.jsonl").read_text().splitlines()]
    relevant_instruments = {definition["identities"][x["raw_symbol"]]["instrument_id"] for x in replay["cells"] if x["classification"] == "provider_gap"}
    relevant_trade_dates = {x["predecessor_cme_trade_date"] for x in plan["predecessor_cells"] if any(g["target_trade_date"] == x["target_trade_date"] for g in replay["cells"] if g["classification"] == "provider_gap")}
    raw_cleared = []
    for msg in db.DBNStore.from_file(ROOT / "data/raw/databento/NQ/definition-statistics-20261014T223138Z/02-statistics.dbn.zst"):
        if msg.stat_type == 6 and msg.instrument_id in relevant_instruments and datetime.fromtimestamp(msg.ts_ref // 1_000_000_000, timezone.utc).date().isoformat() in relevant_trade_dates:
            raw_cleared.append((msg.instrument_id, msg.ts_ref, msg.ts_recv, msg.quantity))
    stream_cleared = [(x["instrument_id"], x["ts_ref_ns"], x["ts_recv_ns"], x["quantity"]) for x in cleared_stream if x["instrument_id"] in relevant_instruments and datetime.fromtimestamp(x["ts_ref_ns"] // 1_000_000_000, timezone.utc).date().isoformat() in relevant_trade_dates]
    assert raw_cleared == stream_cleared
    plan_by_day = {x["target_trade_date"]: x for x in plan["predecessor_cells"]}
    base_by_day = {x["target_trade_date"]: x for x in base["dates"]}
    def_cells = {(x["target_trade_date"], x["contract"]): x for x in definition["cells"]}
    gaps = [x for x in replay["cells"] if x["classification"] == "provider_gap"]
    assert len(gaps) == 12
    output = []
    for gap in gaps:
        day, symbol, contract = gap["target_trade_date"], gap["raw_symbol"], gap["contract"]
        planned, date = plan_by_day[day], base_by_day[day]
        assert symbol == planned["raw_symbol"] and contract == planned["contract"]
        assert [dict(start_utc=x["start_utc"], end_utc=x["end_utc"]) for x in gap["segments"]] == [dict(start_utc=x["start_utc"], end_utc=x["end_utc"]) for x in planned["segments"]]
        ident = definition["identities"][symbol]
        dc = def_cells[(day, contract)]
        origin = ns(planned["decision_origin_utc"])
        assert dc["predecessor_trade_date"] == planned["predecessor_cme_trade_date"]
        assert dc["definition_identity_valid_at_origin"] and dc["instrument_id"] == ident["instrument_id"]
        assert ident["first_definition_received_ns"] <= origin and ident["activation_ns"] <= origin < ident["expiration_ns"]
        assert (ident["exchange"], ident["group"], ident["asset"], ident["security_type"], ident["instrument_class"], ident["leg_count"]) == ("XCME", "NQ", "NQ", "FUT", "F", 0)
        effective = [x for x in raw_definition if x.instrument_id == ident["instrument_id"] and x.ts_recv <= origin]
        assert effective
        latest = effective[-1]
        assert latest.raw_symbol == symbol and latest.activation <= origin < latest.expiration
        assert (latest.activation, latest.expiration) == (ident["activation_ns"], ident["expiration_ns"])
        assert (latest.exchange, latest.group, latest.asset, latest.security_type, latest.instrument_class, latest.leg_count) == ("XCME", "NQ", "NQ", "FUT", "F", 0)
        stats = [x for x in cleared_stream if x["instrument_id"] == ident["instrument_id"] and datetime.fromtimestamp(x["ts_ref_ns"] // 1_000_000_000, timezone.utc).date().isoformat() == planned["predecessor_cme_trade_date"]]
        assert all(x["raw_symbol"] == symbol and x["stat_type"] == 6 for x in stats)
        assert len(stats) == dc["cleared_message_count"]
        assert (stats[-1]["quantity"] if stats else None) == dc["latest_in_window_quantity"] == gap["later_cleared_volume_diagnostic_only"]
        assert all(x["ts_recv_ns"] > origin for x in stats)
        segments = []
        status_timeline = []
        total_trades = total_quantity = total_bars = total_bar_quantity = 0
        for segment in planned["segments"]:
            req = dict(dataset="GLBX.MDP3", symbols=[symbol], stype_in="raw_symbol", start=segment["start_utc"], end=segment["end_utc"])
            current = {}
            for schema in ("trades", "ohlcv-1m", "status"):
                response = by_request.get(key(dict(req, schema=schema)))
                if response:
                    rows = records(response)
                    volume = sum(int(x["size"] if schema == "trades" else x["volume"]) for x in rows) if schema != "status" else None
                    current[schema] = dict(records=len(rows), volume=volume, quote_index=response["quote_index"], dbn_sha256=response["dbn_sha256"], metadata_exact=True, partial=response["metadata"]["partial"], mapped_instrument_ids=sorted({int(m["symbol"]) for m in response["metadata"]["mappings"][symbol]}))
                    assert current[schema]["mapped_instrument_ids"] == [ident["instrument_id"]]
                    if schema == "status":
                        for row in rows:
                            status_timeline.append(dict(ts_event_utc=utc(int(row["hd"]["ts_event"])), ts_recv_utc=utc(int(row["ts_recv"])), action=row["action"], reason=row["reason"], is_trading=row["is_trading"], is_quoting=row["is_quoting"], instrument_id=row["hd"]["instrument_id"]))
                    if schema == "trades": total_trades += len(rows); total_quantity += volume
                    if schema == "ohlcv-1m": total_bars += len(rows); total_bar_quantity += volume
            segments.append(dict(start_utc=segment["start_utc"], end_utc=segment["end_utc"], responses=current))
        assert total_trades == total_quantity == total_bars == total_bar_quantity == 0
        assert planned["retained_bar_count"] == 0 and planned["retained_electronic_volume"] is None
        acquired_ohlcv = any("ohlcv-1m" in x["responses"] for x in segments)
        assert status_timeline and status_timeline[0]["is_trading"] == "Y" and status_timeline[-1]["is_trading"] == "Y"
        nontrading = [x for x in status_timeline if x["is_trading"] == "N"]
        later_cleared = bool(stats and stats[-1]["quantity"] > 0)
        classification = "provider_gap_cleared_discrepancy" if later_cleared else "provider_observed_zero_transient_status"
        ranked = replay["dates"][[x["target_trade_date"] for x in replay["dates"]].index(day)]["ranked_volumes"]
        assert len(ranked) == 2 and ranked[0][1] > ranked[1][1]
        leader, runner = ranked
        assert date["legacy_selected_contract"] == leader[0]
        threshold = leader[1] + (0 if contract > leader[0] else 1)
        assert contract < leader[0]
        output.append(dict(target_trade_date=day, predecessor_cme_trade_date=planned["predecessor_cme_trade_date"], decision_origin_utc=planned["decision_origin_utc"], contract=contract, raw_symbol=symbol, active_segments=segments, retained_bar_count=planned["retained_bar_count"], retained_electronic_volume=planned["retained_electronic_volume"], acquired_ohlcv_record_count=total_bars if acquired_ohlcv else None, acquired_ohlcv_volume=total_bar_quantity if acquired_ohlcv else None, definition_identity=ident, status_timeline=status_timeline, nontrading_event_count=len(nontrading), status_interpretation="temporary N followed by Y; not a full-session inactive contract" if nontrading else "Y in bounded status response", trade_record_count=total_trades, trade_quantity=total_quantity, later_cleared=dict(quantity=stats[-1]["quantity"] if stats else None, ts_ref_trade_date=planned["predecessor_cme_trade_date"], records=stats, first_provider_receipt_utc=utc(stats[0]["ts_recv_ns"]) if stats else None, available_at_origin=any(x["ts_recv_ns"] <= origin for x in stats)), evidence_classification=classification, supported_electronic_volume=0 if not later_cleared else None, independent_electronic_upper_bound=None, known_leader=dict(contract=leader[0], volume=leader[1]), known_runner_up=dict(contract=runner[0], volume=runner[1]), known_margin=leader[1]-runner[1], counterfactual_min_missing_volume_to_change_winner=threshold, counterfactual_tie_at_leader_volume_winner=leader[0], missing_evidence=["independent venue-complete electronic trade or bar coverage for this exact symbol and predecessor session", "record-level reconciliation of cleared and electronic metrics", "independent electronic-volume upper bound below the leader"] if later_cleared else ["point-in-time provider availability and independent venue completeness", "independent as-of venue roster if causal certification is sought"]))
    assert Counter(x["evidence_classification"] for x in output) == {"provider_gap_cleared_discrepancy": 10, "provider_observed_zero_transient_status": 2}
    unresolved = {x["target_trade_date"] for x in output if x["supported_electronic_volume"] is None}
    chronology = replay["har_chronology"]["rows"]
    rows_with_unresolved = sum(bool(set(x["unresolved_selector_dates"]) & unresolved) for x in chronology)
    rows_fully_supported = sum(not set(x["unresolved_selector_dates"]) & unresolved and not x["retained_selected_bar_gap_dates"] for x in chronology)
    assert rows_with_unresolved == 73 and rows_fully_supported == 0
    result = dict(schema_version="nq-w1-twelve-gap-reconciliation-v1", sources=dict(acquisition_manifest_sha256=sha(RUN / "acquisition-manifest.json"), run_seal_sha256=sha(RUN / "run-seal.json"), replay_sha256=sha(ROOT / "results/nq-w1-front-three-acquisition-replay.json"), definition_evidence_sha256=sha(ROOT / "results/nq-definition-statistics-evidence.json")), verification=dict(sealed_files=154, authenticated_responses=74, approved_requests=80, skipped_conditional=6, schema_counts=dict(schema_counts), all_hashes_and_metadata_valid=True), cells=output, retrospective_front_three=dict(prior_supported_winners=108, newly_supported_provider_stream_winners=2, now_supported_winners=110, remaining_indeterminate=10, unresolved_target_dates=sorted(unresolved), total_dates=120, exchange_wide_certified_dates=0, har_rows_with_unresolved_selector_window=rows_with_unresolved, har_rows_supported_without_dropping_dates=rows_fully_supported), recommendation="NO-GO for complete 120-date front-three release or HAR; GO for read-only, independent venue electronic-feed completeness and cleared-to-trade reconciliation targeted to ten remaining cells")
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(OUT), "verified_responses": len(by_request), "classifications": dict(Counter(x["evidence_classification"] for x in output)), "retrospective_supported_winners": 110}))


if __name__ == "__main__":
    main()
