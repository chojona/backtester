"""Metadata-only Databento estimates for the five W1 candidate minute gaps."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "results/nq-w1-120-session-candidate.json"


def credential():
    key = os.environ.get("DATABENTO_API_KEY")
    if key:
        return key
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABENTO_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("No Databento credential available")


def kwargs(schema, symbol, start, end):
    return {"dataset": "GLBX.MDP3", "schema": schema, "symbols": [symbol],
            "stype_in": "raw_symbol", "start": start, "end": end}


def quote(client, request):
    meta = client.metadata
    return {"estimated_cost_usd": str(Decimal(str(meta.get_cost(**request)))),
            "estimated_billable_bytes": int(meta.get_billable_size(**request)),
            "estimated_records": int(meta.get_record_count(**request))}


def main():
    data = json.loads(PATH.read_text())
    client = db.Historical(key=credential())
    requests = []
    comparisons = []
    for gap in data["active_minute_gaps"]:
        symbol = gap["raw_symbol"]
        start, end = gap["start_utc"], gap["end_utc"]
        trade = kwargs("trades", symbol, start, end)
        status = kwargs("status", symbol, gap["session_open_utc"], end)
        for role, request in (("missing_minute_trades", trade), ("session_open_through_gap_status", status)):
            requests.append({"trade_date": gap["trade_date"], "role": role,
                             "request": request, "quote": quote(client, request)})
        stamp = datetime.fromisoformat(start.replace("Z", "+00:00"))
        bucket_start = stamp.replace(minute=stamp.minute // 10 * 10, second=0, microsecond=0)
        bucket_end = bucket_start + timedelta(minutes=10)
        comparison = kwargs("trades", symbol, bucket_start.isoformat().replace("+00:00", "Z"),
                            bucket_end.isoformat().replace("+00:00", "Z"))
        comparisons.append({"trade_date": gap["trade_date"], "request": comparison,
                            "quote": quote(client, comparison)})
    total = sum((Decimal(row["quote"]["estimated_cost_usd"]) for row in requests), Decimal(0))
    data["retrieval"] = {"authorized": False, "performed": False,
                         "estimate_observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                         "provider": "Databento Historical metadata API, authenticated account",
                         "sdk_version": db.__version__, "requests": requests,
                         "trade_ten_minute_bucket_comparisons": comparisons,
                         "account_specific_estimates": {
                             "total_cost_usd": str(total),
                             "total_billable_bytes": sum(r["quote"]["estimated_billable_bytes"] for r in requests),
                             "total_records": sum(r["quote"]["estimated_records"] for r in requests),
                             "cost_is_not_invoice_cap": True}}
    PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data["retrieval"], indent=2))


if __name__ == "__main__":
    main()
