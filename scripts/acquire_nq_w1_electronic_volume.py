"""Acquire only the frozen W1 predecessor cells after an all-request quote gate.

Run --preflight first. Run --acquire with its returned directory only after
inspecting the preflight. Neither mode changes a production selector or tier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "results/nq-w1-targeted-remediation-plan.json"
INVENTORY = ROOT / "results/nq-front-three-selector-feasibility.json"
CANDIDATE = ROOT / "results/nq-w1-120-session-candidate.json"
DEST = ROOT / "data/raw/databento/NQ"
CAP = Decimal("0.01")
SCHEMAS = {"ohlcv-1m", "trades", "status"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path: Path, value: object, *, exclusive: bool = False) -> None:
    mode = "x" if exclusive else "w"
    with path.open(mode) as stream:
        json.dump(value, stream, indent=2, default=str)
        stream.write("\n")


def credential() -> str:
    if os.environ.get("DATABENTO_API_KEY"):
        return os.environ["DATABENTO_API_KEY"]
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABENTO_API_KEY="):
            return line.partition("=")[2].strip().strip('"').strip("'")
    raise RuntimeError("Databento credential unavailable")


def stamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ns(value: str) -> int:
    dt = stamp(value)
    delta = dt - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1000


def request_key(request: dict) -> str:
    return json.dumps(request, sort_keys=True, separators=(",", ":"))


def request_id(request: dict) -> str:
    identity = [request["schema"], request["symbols"][0], request["start"], request["end"]]
    return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()


def append_ledger(path: Path, row: dict) -> None:
    with path.open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def retry_delay(exc: Exception, attempt: int) -> float:
    headers = getattr(exc, "headers", None) or {}
    guidance = next((str(value) for name, value in headers.items() if name.lower() == "retry-after"), None)
    if guidance:
        try:
            seconds = float(guidance)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(guidance) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError):
                seconds = 0
        if seconds > 0:
            return seconds
    return min(2 ** (attempt - 1), 8) + random.uniform(0, 0.5)


def scope_audit(plan: dict, inventory: dict, candidate: dict) -> tuple[list[dict], list[dict], dict]:
    if digest(INVENTORY) != plan["frozen_inventory"]["sha256"]:
        raise ValueError("Frozen inventory hash changed")
    if digest(CANDIDATE) != plan["source_hashes"]["results/nq-w1-120-session-candidate.json"]:
        raise ValueError("Candidate calendar hash changed")
    if inventory["summary"]["coverage_counts"] != plan["frozen_inventory"]["coverage_counts"]:
        raise ValueError("Frozen coverage counts changed")
    if len(inventory["dates"]) != len(candidate["trade_dates"]) != 120:
        raise ValueError("120-date chronology changed")
    candidate_dates = [d["trade_date"] for d in candidate["trade_dates"]]
    if candidate_dates != [d["target_trade_date"] for d in inventory["dates"]]:
        raise ValueError("Candidate and inventory dates differ")
    frozen_cells = {d["target_trade_date"]: d for d in plan["predecessor_cells"]}
    if len(frozen_cells) != 32:
        raise ValueError("Expected exactly 32 frozen unresolved cells")
    expected_initial, expected_fallback = [], []
    classes = Counter()
    segment_count = 0
    holiday_segments = {}
    for index, day in enumerate(inventory["dates"]):
        if not day["unknown_competitors"]:
            if day["target_trade_date"] in frozen_cells:
                raise ValueError("Plan includes a resolved date")
            continue
        if len(day["unknown_competitors"]) != 1 or index == 0:
            raise ValueError("Unexpected unresolved roster or first-date predecessor")
        target = day["target_trade_date"]
        cell = next(c for c in day["cells"] if c["contract"] == day["unknown_competitors"][0])
        frozen = frozen_cells[target]
        predecessor = candidate["trade_dates"][index - 1]
        if predecessor["trade_date"] != day["predecessor_cme_trade_date"]:
            raise ValueError(f"Predecessor chronology mismatch: {target}")
        if candidate["trade_dates"][index]["predecessor_trade_date"] != predecessor["trade_date"]:
            raise ValueError(f"Candidate predecessor mismatch: {target}")
        segments = day["predecessor_active_segments_utc"]
        candidate_segments = predecessor["segments"]
        if len(segments) != len(candidate_segments) or len(segments) != len(frozen["segments"]):
            raise ValueError(f"Segment count mismatch: {target}")
        if (frozen["contract"], frozen["raw_symbol"], frozen["classification"],
                frozen["predecessor_cme_trade_date"]) != (cell["contract"], cell["raw_symbol"],
                    cell["classification"], predecessor["trade_date"]):
            raise ValueError(f"Frozen cell mismatch: {target}")
        classes[cell["classification"]] += 1
        if len(segments) > 1:
            holiday_segments[predecessor["trade_date"]] = len(segments)
        for j, (segment, candidate_segment, frozen_segment) in enumerate(zip(segments, candidate_segments, frozen["segments"])):
            segment_count += 1
            start, end = segment["start_utc"], segment["end_utc"]
            if not stamp(start) < stamp(end):
                raise ValueError(f"Nonpositive bound: {target}/{j}")
            if {"start_utc": start, "end_utc": end} != {"start_utc": frozen_segment["start_utc"],
                                                       "end_utc": frozen_segment["end_utc"]}:
                raise ValueError(f"Frozen segment mismatch: {target}/{j}")
            if (stamp(candidate_segment["start_utc"]), stamp(candidate_segment["end_utc"])) != (stamp(start), stamp(end)):
                raise ValueError(f"Candidate segment mismatch: {target}/{j}")
            if j and stamp(segments[j - 1]["end_utc"]) >= stamp(start):
                raise ValueError(f"Missing scheduled halt: {target}/{j}")
            base = {"dataset": "GLBX.MDP3", "symbols": [cell["raw_symbol"]],
                    "stype_in": "raw_symbol", "start": start, "end": end}
            def row(schema: str, phase: str) -> dict:
                return {"target_trade_date": target, "predecessor_cme_trade_date": predecessor["trade_date"],
                        "phase": phase, "request": dict(base, schema=schema)}
            if cell["classification"] == "not_requested":
                if frozen_segment["existing_ohlcv_requests"]:
                    raise ValueError(f"Unrequested cell has existing request: {target}")
                expected_initial.append(row("ohlcv-1m", "initial"))
                expected_fallback.extend((row("trades", "conditional_no_bar"), row("status", "conditional_no_bar")))
            elif cell["classification"] == "requested_no_retained_bar":
                if not frozen_segment["existing_ohlcv_requests"]:
                    raise ValueError(f"No-bar cell lacks original request: {target}")
                expected_initial.extend((row("trades", "initial"), row("status", "initial")))
            else:
                raise ValueError(f"Unexpected class: {target}")
    if classes != {"not_requested": 11, "requested_no_retained_bar": 21}:
        raise ValueError(f"Class counts differ: {classes}")
    if segment_count != 34 or holiday_segments != {"2022-06-21": 2, "2022-07-05": 2}:
        raise ValueError(f"Active segment or holiday count differs: {segment_count}/{holiday_segments}")
    if len(expected_initial) != 56 or len(expected_fallback) != 24:
        raise ValueError("Request counts differ")
    if plan["query_plan"]["initial_requests"] != [dict(x, estimate=y["estimate"]) for x, y in zip(expected_initial, plan["query_plan"]["initial_requests"])]:
        raise ValueError("Initial plan request or order differs")
    if plan["query_plan"]["conditional_fallback_requests"] != [dict(x, estimate=y["estimate"]) for x, y in zip(expected_fallback, plan["query_plan"]["conditional_fallback_requests"])]:
        raise ValueError("Conditional plan request or order differs")
    all_requests = expected_initial + expected_fallback
    if len({request_key(x["request"]) for x in all_requests}) != 80:
        raise ValueError("Duplicate exact request")
    if any(x["request"]["schema"] not in SCHEMAS or len(x["request"]["symbols"]) != 1 for x in all_requests):
        raise ValueError("Unrelated schema or contract")
    return expected_initial, expected_fallback, {"cells": 32, "segments": segment_count,
                                                  "classes": dict(classes), "holiday_segments": holiday_segments,
                                                  "initial_requests": 56, "conditional_requests": 24,
                                                  "no_target_or_halt_overfetch": True}


def load_checked() -> tuple[bytes, dict, list[dict], list[dict], dict]:
    source = PLAN.read_bytes()
    plan = json.loads(source)
    initial, fallback, audit = scope_audit(plan, json.loads(INVENTORY.read_bytes()), json.loads(CANDIDATE.read_bytes()))
    return source, plan, initial, fallback, audit


def quote_one(row: dict, client, ledger: Path) -> dict | None:
    req = row["request"]
    ident = request_id(req)
    for attempt in range(1, 4):
        started = now()
        values = {"estimated_cost_usd": None, "estimated_billable_bytes": None,
                  "estimated_records": None}
        try:
            values["estimated_cost_usd"] = str(Decimal(str(client.metadata.get_cost(**req))))
            values["estimated_billable_bytes"] = int(client.metadata.get_billable_size(**req))
            values["estimated_records"] = int(client.metadata.get_record_count(**req))
            cost = Decimal(values["estimated_cost_usd"])
            if not cost.is_finite() or cost < 0 or values["estimated_billable_bytes"] < 0 or values["estimated_records"] < 0:
                raise ValueError("Invalid metadata quote")
            outcome = dict(row, request_id=ident, quote_started_at_utc=started,
                           quote_completed_at_utc=now(), attempt=attempt, http_status=200,
                           exception=None, **values)
            append_ledger(ledger, outcome)
            return outcome
        except Exception as exc:
            status = getattr(exc, "http_status", None)
            transient = status in {429, 502, 503, 504}
            delay = retry_delay(exc, attempt) if transient and attempt < 3 else None
            append_ledger(ledger, dict(row, request_id=ident, quote_started_at_utc=started,
                                       quote_completed_at_utc=now(), attempt=attempt, http_status=status,
                                       exception={"type": type(exc).__name__, "message": str(exc)},
                                       provider_request_id=getattr(exc, "request_id", None),
                                       retry_after_seconds=delay, **values))
            if delay is None:
                return None
            time.sleep(delay)
    return None


def preflight() -> Path:
    source, _, initial, fallback, audit = load_checked()
    expected = initial + fallback
    run = DEST / ("w1-electronic-volume-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    run.mkdir(exist_ok=False)
    ledger = run / "quote-ledger.jsonl"
    ledger.touch(exist_ok=False)
    identities = [dict(row, request_id=request_id(row["request"])) for row in expected]
    save(run / "approved-requests.json", {"plan_sha256": hashlib.sha256(source).hexdigest(),
                                             "scope_audit": audit, "requests": identities}, exclusive=True)
    quotes = []
    failure = None
    try:
        client = db.Historical(key=credential())
        for index, row in enumerate(expected, 1):
            quoted = quote_one(row, client, ledger)
            if quoted is None:
                failure = {"reason": "required_authenticated_quote_failed", "index": index,
                           "request_id": request_id(row["request"]), "request": row["request"]}
                break
            quotes.append(quoted)
    except Exception as exc:
        failure = {"reason": "quote_or_credential_exception", "type": type(exc).__name__, "message": str(exc)}
    if failure is not None:
        save(run / "abort-evidence.json", {"decision": "NO-GO", "recorded_at_utc": now(),
             "failure": failure, "successful_quotes": len(quotes), "required_quotes": 80,
             "paid_requests_started": False, "quote_ledger_sha256": digest(ledger) if ledger.exists() else None}, exclusive=True)
        print(json.dumps({"run": str(run), "decision": "NO-GO", "failure": failure}), flush=True)
        return run
    total = sum((Decimal(row["estimated_cost_usd"]) for row in quotes), Decimal(0))
    if len(quotes) != 80 or [q["request_id"] for q in quotes] != [r["request_id"] for r in identities]:
        raise ValueError("Quote ledger does not match approved manifest")
    if not total.is_finite() or total < 0 or total > CAP:
        save(run / "abort-evidence.json", {"decision": "NO-GO", "reason": "cost_gate_failed",
             "all_path_estimated_cost_usd": str(total), "cap_usd": str(CAP),
             "quote_ledger_sha256": digest(ledger), "paid_requests_started": False}, exclusive=True)
        print(json.dumps({"run": str(run), "decision": "NO-GO", "all_path_estimated_cost_usd": str(total)}), flush=True)
        return run
    if PLAN.read_bytes() != source:
        raise ValueError("Plan changed during preflight")
    load_checked()
    evidence = {"purpose": "Frozen 32-cell W1 electronic-volume acquisition", "plan_sha256": hashlib.sha256(source).hexdigest(),
                "inventory_sha256": digest(INVENTORY), "candidate_sha256": digest(CANDIDATE),
                "sdk_version": db.__version__, "scope_audit": audit, "quote_completed_at_utc": now(),
                "cost_gate_usd": str(CAP), "all_path_estimated_cost_usd": str(total),
                "initial_estimated_cost_usd": str(sum((Decimal(x["estimated_cost_usd"]) for x in quotes if x["phase"] == "initial"), Decimal(0))),
                "conditional_estimated_cost_usd": str(sum((Decimal(x["estimated_cost_usd"]) for x in quotes if x["phase"] != "initial"), Decimal(0))),
                "quotes": quotes, "approved_requests_sha256": digest(run / "approved-requests.json"),
                "quote_ledger_sha256": digest(ledger), "paid_requests_started": False}
    save(run / "preflight.json", evidence, exclusive=True)
    print(json.dumps({"run": str(run), "scope_audit": audit, "all_path_estimated_cost_usd": str(total)}), flush=True)
    return run


def response_metadata(meta) -> dict:
    return {name: (str(getattr(meta, name)) if name in {"schema", "stype_in", "stype_out", "encoding"}
                   else json.loads(json.dumps(getattr(meta, name), default=str)))
            for name in ("dataset", "schema", "stype_in", "stype_out", "encoding", "start", "end", "limit",
                         "symbols", "partial", "not_found", "mappings") if hasattr(meta, name)}


def inspect_records(path: Path, request: dict, metadata: dict) -> dict:
    lower, upper = ns(request["start"]), ns(request["end"])
    mappings = metadata.get("mappings") or {}
    symbol = request["symbols"][0]
    mapped_ids = {int(interval["symbol"]) for interval in mappings.get(symbol, [])}
    if set(mappings) - {symbol}:
        raise ValueError("Response includes a mapping for an unrequested symbol")
    count = volume = duplicate_trades = 0
    seen_trades = set()
    first = last = None
    with path.open() as stream:
        for line in stream:
            record = json.loads(line)
            header = record["hd"]
            timestamp = int(header["ts_event"])
            instrument_id = int(header["instrument_id"])
            if not lower <= timestamp < upper:
                raise ValueError("Decoded record lies outside approved UTC bounds")
            if instrument_id not in mapped_ids:
                raise ValueError("Decoded record instrument does not match raw-symbol mapping")
            count += 1
            first = timestamp if first is None else min(first, timestamp)
            last = timestamp if last is None else max(last, timestamp)
            if request["schema"] in {"trades", "ohlcv-1m"}:
                field = "size" if request["schema"] == "trades" else "volume"
                amount = int(record[field])
                if amount < 0:
                    raise ValueError("Negative decoded electronic volume")
                if request["schema"] == "trades":
                    identity = json.dumps(record, sort_keys=True, separators=(",", ":"))
                    if identity in seen_trades:
                        duplicate_trades += 1
                        continue
                    seen_trades.add(identity)
                volume += amount
    return {"record_count": count, "electronic_volume": volume if request["schema"] != "status" else None,
            "first_ts_event_ns": first, "last_ts_event_ns": last,
            "duplicate_trade_records": duplicate_trades,
            "raw_symbol_mapping_present": bool(mapped_ids)}


def acquire(run: Path) -> None:
    run = run.resolve()
    if run.parent != DEST.resolve() or not run.name.startswith("w1-electronic-volume-"):
        raise ValueError("Invalid run directory")
    preflight_path = run / "preflight.json"
    preflight_bytes = preflight_path.read_bytes()
    pre = json.loads(preflight_bytes)
    if (digest(run / "quote-ledger.jsonl") != pre["quote_ledger_sha256"]
            or digest(run / "approved-requests.json") != pre["approved_requests_sha256"]):
        raise ValueError("Quote ledger or approved request manifest changed")
    source, _, initial, fallback, audit = load_checked()
    if (pre["plan_sha256"] != hashlib.sha256(source).hexdigest() or pre["inventory_sha256"] != digest(INVENTORY)
            or pre["candidate_sha256"] != digest(CANDIDATE) or pre["scope_audit"] != audit):
        raise ValueError("Preflight source changed")
    expected = initial + fallback
    if len(pre["quotes"]) != 80 or any({k: q[k] for k in ("target_trade_date", "predecessor_cme_trade_date", "phase", "request")} != x
                                           for q, x in zip(pre["quotes"], expected)):
        raise ValueError("Preflight quotes differ from frozen requests")
    if any(q.get("request_id") != request_id(q["request"]) or q.get("http_status") != 200
           or q.get("exception") is not None or not q.get("quote_completed_at_utc")
           or not isinstance(q.get("estimated_billable_bytes"), int)
           or not isinstance(q.get("estimated_records"), int) for q in pre["quotes"]):
        raise ValueError("Required fresh authenticated metadata quote missing")
    total = sum((Decimal(q["estimated_cost_usd"]) for q in pre["quotes"]), Decimal(0))
    if total > CAP or total != Decimal(pre["all_path_estimated_cost_usd"]):
        raise ValueError("Cost gate failed")
    if any((run / name).exists() for name in ("progress.json", "acquisition-manifest.json")):
        raise ValueError("Run already started")
    if preflight_path.read_bytes() != preflight_bytes:
        raise ValueError("Preflight changed")
    client = db.Historical(key=credential())
    journal = {"preflight_sha256": hashlib.sha256(preflight_bytes).hexdigest(), "started_at_utc": now(),
               "responses": [], "skipped_conditional_requests": [], "completed": False}
    save(run / "progress.json", journal, exclusive=True)
    response_by_key = {}
    def retrieve(index: int, q: dict) -> None:
        request = q["request"]
        stem = f"{index:02d}-{q['target_trade_date']}-{request['schema']}"
        path = run / (stem + ".dbn.zst")
        started = now()
        try:
            store = client.timeseries.get_range(**request, path=path)
            received = now()
            meta = response_metadata(store.metadata)
            export = run / (stem + ".jsonl")
            store.to_json(path=export, pretty_px=False, pretty_ts=False, map_symbols=False, mode="x")
            decoded = inspect_records(export, request, meta)
            records = decoded["record_count"]
            exact = (meta.get("dataset") == request["dataset"] and meta.get("schema") == request["schema"]
                     and meta.get("symbols") == request["symbols"] and meta.get("stype_in") == "raw_symbol"
                     and meta.get("start") == ns(request["start"]) and meta.get("end") == ns(request["end"])
                     and meta.get("limit") is None)
            row = {"quote_index": index, "target_trade_date": q["target_trade_date"],
                   "predecessor_cme_trade_date": q["predecessor_cme_trade_date"], "phase": q["phase"],
                   "request": request, "quote_started_at_utc": q["quote_started_at_utc"],
                   "quote_completed_at_utc": q["quote_completed_at_utc"],
                   "quoted_cost_usd": q["estimated_cost_usd"], "call_started_at_utc": started,
                   "response_received_at_utc": received, "metadata": meta, "metadata_exact_request": exact,
                   "returned_records": records, "decoded": decoded,
                   "dbn_file": path.name, "dbn_bytes": path.stat().st_size,
                   "dbn_sha256": digest(path), "jsonl_file": export.name,
                   "jsonl_bytes": export.stat().st_size, "jsonl_sha256": digest(export)}
            journal["responses"].append(row)
            response_by_key[request_key(request)] = row
            save(run / "progress.json", journal)
            print(json.dumps({"index": index, "target": q["target_trade_date"], "schema": request["schema"],
                              "records": records, "exact": exact, "partial": meta.get("partial"),
                              "not_found": meta.get("not_found")}), flush=True)
            if not exact:
                raise ValueError(f"Response metadata differs from approved request at index {index}")
            reread = db.DBNStore.from_file(path).metadata
            if response_metadata(reread) != meta or digest(path) != row["dbn_sha256"]:
                raise ValueError(f"Raw DBN read-back mismatch at index {index}")
        except BaseException as exc:
            journal["failure"] = {"index": index, "request_id": q["request_id"],
                                  "request": request, "at_utc": now(),
                                  "type": type(exc).__name__, "message": str(exc),
                                  "preserved_files": [{"name": candidate.name, "sha256": digest(candidate),
                                                       "bytes": candidate.stat().st_size}
                                                      for candidate in (path, run / (stem + ".jsonl")) if candidate.exists()]}
            save(run / "progress.json", journal)
            raise
    for index, q in enumerate(pre["quotes"][:56], 1):
        retrieve(index, q)
    for index, q in enumerate(pre["quotes"][56:], 57):
        request = q["request"]
        parent = dict(request, schema="ohlcv-1m")
        source_response = response_by_key.get(request_key(parent))
        if source_response is None:
            raise ValueError("Conditional request lacks its OHLCV parent")
        clean_empty = (source_response["returned_records"] == 0 and source_response["metadata_exact_request"]
                       and source_response["metadata"].get("partial") == []
                       and source_response["metadata"].get("not_found") == [])
        if clean_empty:
            retrieve(index, q)
        else:
            journal["skipped_conditional_requests"].append({"quote_index": index, "request": request,
                                                               "reason": "OHLCV response positive or not cleanly empty"})
            save(run / "progress.json", journal)
    journal["completed"] = True
    journal["completed_at_utc"] = now()
    save(run / "progress.json", journal)
    final = {"purpose": pre["purpose"], "preflight_sha256": hashlib.sha256(preflight_bytes).hexdigest(),
             "plan_sha256": pre["plan_sha256"], "inventory_sha256": pre["inventory_sha256"],
             "candidate_sha256": pre["candidate_sha256"], "scope_audit": audit,
             "sdk_version": pre["sdk_version"], "quote_completed_at_utc": pre["quote_completed_at_utc"],
             "all_path_estimated_cost_usd": pre["all_path_estimated_cost_usd"],
             "executed_quoted_cost_usd": str(sum((Decimal(x["quoted_cost_usd"]) for x in journal["responses"]), Decimal(0))),
             "actual_provider_charge_usd": None, "cost_gate_usd": str(CAP),
             "quotes": pre["quotes"], "responses": journal["responses"],
             "skipped_conditional_requests": journal["skipped_conditional_requests"],
             "completed": True, "completed_at_utc": journal["completed_at_utc"]}
    final_path = run / "acquisition-manifest.json"
    save(final_path, final, exclusive=True)
    (run / "acquisition-manifest.sha256").write_text(digest(final_path) + "  acquisition-manifest.json\n")
    print(json.dumps({"completed": True, "manifest": str(final_path), "responses": len(journal["responses"]),
                      "skipped_conditional": len(journal["skipped_conditional_requests"]),
                      "executed_quoted_cost_usd": final["executed_quoted_cost_usd"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--acquire", type=Path)
    args = parser.parse_args()
    if args.preflight:
        preflight()
    else:
        acquire(args.acquire)
