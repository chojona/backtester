"""Execute only the ten preserved W1 gap requests after a fresh cost gate."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "results/nq-w1-120-session-candidate.json"
SOURCE = ROOT / "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"
LEDGER = ROOT / "results/databento-nq-full-history/phase3-v3.0.0/certification-by-session.csv"
EVIDENCE_ROOT = ROOT / "data/raw/databento/NQ"
CAP = Decimal("0.01")

# Independent fixed copy of the five authorized identities, not derived from
# the manifest being checked. All timestamps denote half-open UTC intervals.
GAPS = [
    ("2022-06-06", "NQM2", "2022-06-05T22:00:00Z", "2022-06-05T23:27:00Z", "2022-06-05T23:28:00Z"),
    ("2022-07-27", "NQU2", "2022-07-26T22:00:00Z", "2022-07-27T03:56:00Z", "2022-07-27T03:57:00Z"),
    ("2022-08-16", "NQU2", "2022-08-15T22:00:00Z", "2022-08-16T04:43:00Z", "2022-08-16T04:44:00Z"),
    ("2022-08-18", "NQU2", "2022-08-17T22:00:00Z", "2022-08-18T04:42:00Z", "2022-08-18T04:43:00Z"),
    ("2022-10-13", "NQZ2", "2022-10-12T22:00:00Z", "2022-10-12T22:48:00Z", "2022-10-12T22:49:00Z"),
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


def credential() -> str:
    key = os.environ.get("DATABENTO_API_KEY")
    if key:
        return key
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABENTO_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("No Databento credential")


def expected_requests() -> list[dict]:
    result = []
    for day, symbol, opened, start, end in GAPS:
        for role, schema, lower in (("missing_minute_trades", "trades", start),
                                    ("session_open_through_gap_status", "status", opened)):
            result.append({"trade_date": day, "role": role, "request": {
                "dataset": "GLBX.MDP3", "schema": schema, "symbols": [symbol],
                "stype_in": "raw_symbol", "start": lower, "end": end}})
    return result


def check_manifest(candidate: dict) -> list[dict]:
    expected = expected_requests()
    gaps = [{"trade_date": day, "raw_symbol": symbol, "session_open_utc": opened,
             "start_utc": start, "end_utc": end} for day, symbol, opened, start, end in GAPS]
    actual_gaps = [{key: row[key] for key in gaps[0]} for row in candidate["active_minute_gaps"]]
    if actual_gaps != gaps:
        raise ValueError("Candidate active gaps differ from the fixed five-gap authorization")
    actual = [{key: row[key] for key in ("trade_date", "role", "request")}
              for row in candidate["retrieval"]["requests"]]
    if len(actual) != 10 or actual != expected:
        raise ValueError("Candidate request scopes differ from the fixed ten-request authorization")
    if candidate["retrieval"]["performed"] or candidate["retrieval"]["authorized"]:
        raise ValueError("Candidate retrieval state unexpectedly changed")
    if digest(SOURCE) != candidate["sources_sha256"]["parquet"]:
        raise ValueError("Retained OHLCV hash changed")
    if digest(LEDGER) != candidate["sources_sha256"]["phase3_ledger"]:
        raise ValueError("Retained certification ledger hash changed")
    return expected


def main() -> None:
    candidate_bytes = CANDIDATE.read_bytes()
    candidate = json.loads(candidate_bytes)
    requests = check_manifest(candidate)
    client = db.Historical(key=credential())
    quotes = []
    for row in requests:
        req = row["request"]
        quotes.append({"trade_date": row["trade_date"], "role": row["role"],
                       "request": req, "estimated_cost_usd": str(Decimal(str(client.metadata.get_cost(**req)))),
                       "estimated_billable_bytes": int(client.metadata.get_billable_size(**req)),
                       "estimated_records": int(client.metadata.get_record_count(**req))})
    total = sum((Decimal(r["estimated_cost_usd"]) for r in quotes), Decimal(0))
    quoted_at = now()
    if not total.is_finite() or total < 0 or total > CAP:
        raise ValueError(f"Fresh combined estimate {total} exceeds authorized $0.01 gate")
    if CANDIDATE.read_bytes() != candidate_bytes or check_manifest(json.loads(CANDIDATE.read_bytes())) != requests:
        raise ValueError("Candidate manifest changed during quote")
    run = EVIDENCE_ROOT / ("w1-five-gap-investigation-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    run.mkdir(exist_ok=False)
    manifest = {"purpose": "Five exact W1 missing-minute investigations", "candidate_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
                "source_parquet_sha256": digest(SOURCE), "phase3_ledger_sha256": digest(LEDGER),
                "sdk_version": db.__version__, "quoted_at_utc": quoted_at,
                "combined_estimated_cost_usd": str(total), "cost_gate_usd": str(CAP),
                "estimated_billable_bytes": sum(r["estimated_billable_bytes"] for r in quotes),
                "estimated_records": sum(r["estimated_records"] for r in quotes),
                "actual_reported_cost_usd": None, "actual_cost_note": "No settled cost supplied by metadata quotes; check responses for reported actual cost.",
                "requests": quotes, "responses": [], "completed": False}
    save(run / "manifest.json", manifest)
    print(json.dumps({"run": str(run), "fresh_combined_estimated_cost_usd": str(total),
                      "request_count": len(requests)}), flush=True)
    for index, row in enumerate(quotes, 1):
        stem = f"{index:02d}-{row['trade_date']}-{row['request']['schema']}"
        path = run / (stem + ".dbn.zst")
        try:
            store = client.timeseries.get_range(**row["request"], path=path)
            meta = store.metadata
            start_ns = int(datetime.fromisoformat(row["request"]["start"].replace("Z", "+00:00")).timestamp() * 1_000_000_000)
            end_ns = int(datetime.fromisoformat(row["request"]["end"].replace("Z", "+00:00")).timestamp() * 1_000_000_000)
            metadata = {"dataset": meta.dataset, "schema": str(meta.schema), "symbols": list(meta.symbols),
                        "stype_in": str(meta.stype_in), "start_ns": meta.start, "end_ns": meta.end,
                        "limit": meta.limit, "partial": list(meta.partial), "not_found": list(meta.not_found),
                        "mappings": str(meta.mappings)}
            # A partial response is retained and reported; never silently retried.
            export = run / (stem + ".jsonl")
            store.to_json(path=export, pretty_px=False, pretty_ts=False, map_symbols=False, mode="x")
            records = sum(1 for _ in export.open("rb"))
            response = {"index": index, "trade_date": row["trade_date"], "role": row["role"],
                        "request": row["request"], "metadata": metadata,
                        "bounds_cover_request": meta.start <= start_ns and meta.end is not None and meta.end >= end_ns,
                        "returned_records": records,
                        "dbn_file": path.name, "dbn_bytes": path.stat().st_size, "dbn_sha256": digest(path),
                        "jsonl_file": export.name, "jsonl_bytes": export.stat().st_size,
                        "jsonl_sha256": digest(export), "actual_reported_cost_usd": None}
            manifest["responses"].append(response)
            save(run / "manifest.json", manifest)
            print(json.dumps({"index": index, "records": records, "partial": metadata["partial"],
                              "not_found": metadata["not_found"]}), flush=True)
        except BaseException as exc:
            manifest["failure"] = {"index": index, "type": type(exc).__name__, "message": str(exc), "at_utc": now()}
            save(run / "manifest.json", manifest)
            raise
    manifest["completed"] = True
    manifest["completed_at_utc"] = now()
    save(run / "manifest.json", manifest)
    print(json.dumps({"completed": True, "run": str(run)}), flush=True)


if __name__ == "__main__":
    main()
