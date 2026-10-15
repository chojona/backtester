"""Read-only diagnostic of Phase 3 decisions and all unobserved weekdays."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/databento-nq-full-history"
PHASE = BASE / "phase3-v3.0.0"
OUT = ROOT / "reports/nq-certification-blockers"


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    decisions = read_csv(PHASE / "certification-by-session.csv")
    missing = read_csv(PHASE / "missing-date-candidates.csv")
    coverage = {x["trading_date"]: x for x in read_csv(BASE / "coverage-by-session.csv")}
    provider = json.loads((BASE / "acceptance-report.json").read_text())
    degraded = provider["degraded_provider_conditions"]
    inspected = []
    for row in missing:
        day = date.fromisoformat(row["trading_date"])
        neighbors = [day - timedelta(days=1), day, day + timedelta(days=1)]
        condition = {d.isoformat(): degraded[d.isoformat()] for d in neighbors
                     if d.isoformat() in degraded}
        observed = {d.isoformat(): coverage[d.isoformat()]["observed_minute_bars"]
                    for d in neighbors if d.isoformat() in coverage}
        inspected.append({
            "trading_date": row["trading_date"],
            "calendar_state": row["calendar_state"],
            "candidate_reason": row["reason_code"],
            "nearby_provider_degradation": ";".join(f"{d}:{','.join(v)}" for d, v in condition.items()),
            "neighbor_observed_bars": ";".join(f"{d}:{v}" for d, v in observed.items()),
            "authoritative_exchange_status": "UNVERIFIED",
            "provider_data_status": "DEGRADED_WINDOW" if condition else "NO_RETAINED_TRADE_BARS",
            "strict_disposition": "UNRESOLVED_NOT_PROMOTED",
            "missing_evidence": "dated CME NQ open/close/holiday event evidence; independent trade or provider completeness evidence",
        })
    if len(inspected) != 56 or len([r for r in inspected if r["candidate_reason"] == "POTENTIAL_PROVIDER_GAP"]) != 5:
        raise ValueError("Baseline candidate counts changed")
    blockers = {
        "B_REGULAR_REGIME_FULL_ACTIVE_GRID": "individual dated CME schedule and exception review; full grid alone is not exchange certification",
        "C_PRE2012_TRADE_DATE_REMAP_REQUIRED": "versioned pre-2012 trade-date rebuild and revalidation against dated CME sessions",
        "C_HOLIDAY_OR_EARLY_CLOSE_UNVERIFIED": "dated CME holiday, early-close, and reopening event evidence",
        "C_CME_HOLIDAY_HOURS_NOT_CAPTURED": "dated CME holiday hours and trade-date convention",
        "C_CAUSAL_CONTRACT_EVIDENCE_INCOMPLETE": "complete prior-session contract-volume evidence or reviewed causal-roll exception",
        "C_SPARSE_OR_OFF_SCHEDULE_TRADE_BARS": "independent evidence to distinguish no trade, provider loss, halt, and calendar exception",
        "C_PROVIDER_DEGRADED_OR_METADATA_MISSING": "provider integrity and minute-level completeness evidence",
        "D_NO_PRIOR_SESSION_ROLL_BUFFER": "earlier source history for causal initial-contract selection",
        "D_NONSESSION_PREOPEN_BAR": "dated CME trade-date mapping and preopen event evidence",
    }
    detail = []
    for row in decisions:
        reason = row["reason_code"]
        if row["tier"] == "A":
            continue
        gates = []
        if row["calendar_validity"] != "REVIEWED_REGULAR":
            gates.append(f"CALENDAR:{row['calendar_validity']}")
        if row["provider_integrity"] not in ("AVAILABLE", "REVISED_AVAILABLE"):
            gates.append(f"PROVIDER:{row['provider_integrity']}")
        if row["contract_selection"] != "PRIOR_VOLUME_PRESENT":
            gates.append(f"CONTRACT:{row['contract_selection']}")
        if row["observed_coverage"] != "FULL_ACTIVE_GRID":
            gates.append(f"COVERAGE:{row['observed_coverage']}")
        detail.append({
            "trading_date": row["trading_date"], "tier": row["tier"],
            "reason_code": reason, "calendar_validity": row["calendar_validity"],
            "provider_integrity": row["provider_integrity"],
            "contract_selection": row["contract_selection"],
            "observed_coverage": row["observed_coverage"],
            "all_failed_strict_gates": ";".join(gates),
            "missing_evidence": blockers[reason],
            "strict_disposition": "EXCLUDED_PENDING_EVIDENCE",
        })
    counts = Counter(row["tier"] for row in decisions)
    by_segment = defaultdict(list)
    for row in decisions:
        if row["tier"] == "A":
            by_segment[row["strict_segment_id"]].append(row["trading_date"])
    longest = max(by_segment.values(), key=len)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("all-56-unobserved-weekdays.csv", inspected),
                       ("all-excluded-and-provisional-sessions.csv", detail)):
        with (OUT / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    report = {
        "baseline_version": "nq-history-v3.0.0",
        "decision_csv_sha256": sha(PHASE / "certification-by-session.csv"),
        "missing_candidates_csv_sha256": sha(PHASE / "missing-date-candidates.csv"),
        "tier_counts_before": dict(counts),
        "tier_counts_after": dict(counts),
        "strict_promotions": 0,
        "longest_strict_segment_sessions": len(longest),
        "longest_strict_segment_dates": [longest[0], longest[-1]],
        "reason_counts": dict(Counter(row["reason_code"] for row in decisions)),
        "unobserved_weekdays_inspected": len(inspected),
        "five_provider_gap_candidates": [r["trading_date"] for r in inspected
                                         if r["candidate_reason"] == "POTENTIAL_PROVIDER_GAP"],
        "interpretation": "This is an evidence audit, not a recertification. No absent OHLCV interval is classified as an exchange closure or provider loss solely from silence.",
    }
    (OUT / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
