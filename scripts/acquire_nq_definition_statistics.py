"""Acquire the two explicitly approved NQ requests after a fresh six-call quote gate."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "results/nq-contract-evidence-acquisition-plan.json"
DEST = ROOT / "data/raw/databento/NQ"
SYMBOLS = ["NQM2", "NQU2", "NQZ2", "NQH3", "NQM3", "NQU3", "NQZ3", "NQZ4", "NQZ5", "NQZ6", "NQZ7"]
REQUESTS = [
    dict(dataset="GLBX.MDP3", symbols=SYMBOLS, stype_in="raw_symbol", schema="definition",
         start="2022-05-23T00:00:00Z", end="2022-11-22T00:00:00Z"),
    dict(dataset="GLBX.MDP3", symbols=SYMBOLS, stype_in="raw_symbol", schema="statistics",
         start="2022-05-29T00:00:00Z", end="2022-11-23T00:00:00Z"),
]
CAP = Decimal("0.10")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def key() -> str:
    if os.getenv("DATABENTO_API_KEY"):
        return os.environ["DATABENTO_API_KEY"]
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABENTO_API_KEY="):
            return line.partition("=")[2].strip().strip('"').strip("'")
    raise RuntimeError("Databento credential unavailable")


def check_plan(source: bytes) -> None:
    manifest = json.loads(source)["request_manifest"]["databento"]
    assert manifest["definition_full"]["request"] == REQUESTS[0]
    old = dict(REQUESTS[1], end="2022-11-20T00:00:00Z")
    assert manifest["statistics_full"]["request"] == old
    assert len(REQUESTS) == 2 and all(set(r) == {"dataset", "symbols", "stype_in", "schema", "start", "end"} for r in REQUESTS)


def response_metadata(meta) -> dict:
    return {name: (str(getattr(meta, name)) if name in ("schema", "stype_in", "stype_out", "encoding") else getattr(meta, name))
            for name in ("dataset", "schema", "stype_in", "stype_out", "encoding", "start", "end", "limit", "symbols", "partial", "not_found", "mappings")
            if hasattr(meta, name)}


def main() -> None:
    source = PLAN.read_bytes()
    check_plan(source)
    client = db.Historical(key=key())
    quotes = []
    for request in REQUESTS:
        begun = now()
        cost = Decimal(str(client.metadata.get_cost(**request)))
        size = int(client.metadata.get_billable_size(**request))
        count = int(client.metadata.get_record_count(**request))
        if not cost.is_finite() or cost < 0 or size < 0 or count < 0:
            raise ValueError("Invalid quote; no download made")
        quotes.append(dict(request=request, quote_started_at_utc=begun, quote_completed_at_utc=now(),
                           estimated_cost_usd=str(cost), estimated_billable_bytes=size, estimated_records=count))
    total = sum((Decimal(q["estimated_cost_usd"]) for q in quotes), Decimal(0))
    if total > CAP or PLAN.read_bytes() != source:
        raise ValueError(f"Quote gate failed ({total} USD) or plan changed; no download made")
    check_plan(PLAN.read_bytes())
    run = DEST / ("definition-statistics-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    run.mkdir(parents=True, exist_ok=False)
    evidence = dict(preflight="reports/nq-definition-statistics-final-acquisition-preflight.md",
                    plan_sha256=hashlib.sha256(source).hexdigest(), sdk_version=db.__version__,
                    quoted_at_utc=now(), combined_estimated_cost_usd=str(total), cost_gate_usd=str(CAP),
                    quotes=quotes, responses=[], actual_charge_usd=None, completed=False)
    save(run / "acquisition.json", evidence)
    print(json.dumps(dict(run=str(run), combined_estimated_cost_usd=str(total), quotes=quotes)), flush=True)
    for index, request in enumerate(REQUESTS):
        path = run / f"{index+1:02d}-{request['schema']}.dbn.zst"
        begun = now()
        try:
            store = client.timeseries.get_range(**request, path=path)
            received = now()
            metadata = response_metadata(store.metadata)
            start_ns = int(datetime.fromisoformat(request["start"].replace("Z", "+00:00")).timestamp() * 1_000_000_000)
            end_ns = int(datetime.fromisoformat(request["end"].replace("Z", "+00:00")).timestamp() * 1_000_000_000)
            if (metadata.get("dataset") != request["dataset"] or metadata.get("symbols") != request["symbols"]
                    or metadata.get("stype_in") != "raw_symbol" or metadata.get("schema") != request["schema"]
                    or metadata.get("start") != start_ns or metadata.get("end") != end_ns
                    or metadata.get("limit") is not None):
                raise ValueError("Response metadata differs from approved request")
            row = dict(request=request, call_started_at_utc=begun, response_received_at_utc=received,
                       dbn_file=path.name, dbn_bytes=path.stat().st_size, dbn_sha256=sha(path),
                       metadata=metadata, actual_charge_usd=None)
            evidence["responses"].append(row)
            save(run / "acquisition.json", evidence)
            print(json.dumps(dict(schema=request["schema"], bytes=row["dbn_bytes"], sha256=row["dbn_sha256"],
                                  partial=metadata.get("partial"), not_found=metadata.get("not_found")), default=str), flush=True)
            # The previously documented early symbol mappings are expected. All
            # other missing or partial symbols require investigation before buying more.
            unexpected = set(metadata.get("not_found") or []) | (set(metadata.get("partial") or []) - {"NQU3", "NQZ7"})
            if unexpected:
                raise ValueError(f"Unexpected response coverage: {sorted(unexpected)}")
            reread = db.DBNStore.from_file(path).metadata
            if response_metadata(reread) != metadata or sha(path) != row["dbn_sha256"]:
                raise ValueError("Raw DBN read-back mismatch")
        except BaseException as exc:
            evidence["failure"] = dict(at_utc=now(), schema=request["schema"], type=type(exc).__name__, message=str(exc))
            save(run / "acquisition.json", evidence)
            raise
    evidence["completed"] = True
    evidence["completed_at_utc"] = now()
    save(run / "acquisition.json", evidence)


if __name__ == "__main__":
    main()
