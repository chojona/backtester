"""Conservative, reproducible audit of the retained NQ history.

This does not infer a trade from an absent OHLCV record, nor does it promote an
unsourced weekday template to an authoritative CME holiday schedule.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/databento-nq-full-history"
NY = ZoneInfo("America/New_York")
FIRST = date(2010, 6, 7)
LAST = date(2026, 10, 6)
REVIEWED = {date(2026, 9, 14) + timedelta(days=i) for i in range(12)
            if (date(2026, 9, 14) + timedelta(days=i)).weekday() < 5}
REVIEWED.add(date(2026, 10, 6))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def regime(day: date) -> tuple[str, str, str, str]:
    # Base hours are source-backed; historical holiday/incident exceptions are not.
    if day < date(2012, 11, 19):
        return "PRE_2012_EXTENSION", "16:30 prior weekday;18:00 Sunday", "16:15", "16:15-16:30;17:30-18:00"
    if day < date(2015, 9, 21):
        return "2012_EXTENSION_WITH_PAUSE", "18:00 prior date", "17:15", "16:15-16:30;17:15-18:00"
    if day < date(2021, 6, 28):
        return "2015_CLOSE_CHANGE_WITH_PAUSE", "18:00 prior date", "17:00", "16:15-16:30;17:00-18:00"
    return "POST_2021_PAUSE_REMOVAL", "18:00 prior date", "17:00", "17:00-18:00"


def main() -> None:
    old = list(csv.DictReader((OUT / "coverage-by-session.csv").open()))
    assert len(old) == 4207 and len({r["trading_date"] for r in old}) == len(old)
    old_by_date = {date.fromisoformat(r["trading_date"]): r for r in old}
    previous = json.loads((OUT / "acceptance-report.json").read_text())
    mismatches = previous["source_condition_inconsistencies"]
    assert len(mismatches) == 1 and mismatches[0]["date"] == "2026-10-06"
    latest_manifest = next(p for p in (ROOT / "data/raw/databento/NQ/full-history/8c2dcea828fa59a0").glob("*/manifest.json")
                           if any(c["date"] == "2026-10-06" for c in json.loads(p.read_text()).get("conditions", [])))
    oct_manifest = json.loads(latest_manifest.read_text())
    oct_condition = next(c for c in oct_manifest["conditions"] if c["date"] == "2026-10-06")
    assert oct_condition == {"date": "2026-10-06", "condition": "available", "last_modified_date": "2026-10-08"}
    assert not oct_manifest["dbn_metadata"]["ohlcv-1m"]["partial"]
    assert not oct_manifest["dbn_metadata"]["ohlcv-1m"]["not_found"]

    calendar = []
    sessions = []
    day = FIRST
    while day <= LAST:
        legacy = old_by_date.get(day)
        name, opened, close, breaks = regime(day)
        reviewed = day in REVIEWED
        calendar.append(dict(trading_date=day.isoformat(), weekday=day.strftime("%A"),
                             weekday_candidate=day.weekday() < 5, regime=name,
                             regular_open_et=opened, regular_close_et=close,
                             regular_breaks_et=breaks, exception_status="REVIEWED_NO_EXCEPTION" if reviewed else
                             "UNVERIFIED_HOLIDAY_EARLY_CLOSE_OR_INCIDENT",
                             observed=bool(legacy), source_ids="CME_2026_HOURS,CME_2021_CHANGE" if reviewed else
                             "CME_2012_CHANGE,CME_2015_CHANGE,CME_2021_CHANGE;EXCEPTIONS_UNVERIFIED"))
        if legacy:
            if day.weekday() >= 5:
                verdict, reason = "REJECT", "NONSESSION_PREOPEN_BAR"
            elif day == FIRST:
                verdict, reason = "REJECT", "NO_PRIOR_SESSION_ROLL_BUFFER"
            elif legacy["provider_condition"] != "available_for_session_utc_days":
                verdict, reason = "UNRESOLVED", "PROVIDER_DEGRADED_OR_METADATA_MISSING"
            elif day < date(2012, 11, 19):
                verdict, reason = "UNRESOLVED", "LEGACY_TRADE_DATE_MAPPING_AND_CME_EXCEPTIONS"
            elif reviewed and legacy["full_nominal_grid"] == "yes":
                verdict, reason = "ACCEPT", "CME_DATE_AND_PROVIDER_REVIEWED"
            elif reviewed:
                verdict, reason = "UNRESOLVED", "REVIEWED_DATE_SPARSE_OHLCV"
            else:
                verdict, reason = "UNRESOLVED", "CME_EXCEPTION_SCHEDULE_NOT_VERIFIED"
            # The final 2026-10-06 condition is available after a 2026-10-08 revision.
            if day == LAST and verdict == "ACCEPT":
                reason = "CME_DATE_AND_REVISED_PROVIDER_AVAILABLE"
            sessions.append(dict(trading_date=day.isoformat(), classification=verdict,
                                 reason_code=reason, selected_contract=legacy["selected_contract"],
                                 observed_trade_bars=legacy["observed_minute_bars"],
                                 prior_grid_result=legacy["full_nominal_grid"],
                                 provider_condition=legacy["provider_condition"],
                                 calendar_exception_status=calendar[-1]["exception_status"]))
        day += timedelta(days=1)

    flagged = [r for r in sessions if r["provider_condition"] != "available_for_session_utc_days"]
    assert len(flagged) == 35
    investigations = []
    panel = pq.read_table(OUT / "nq_outright_ohlcv_1m.parquet",
                          columns=["timestamp_utc", "trading_date", "contract"])
    flagged_dates = {date.fromisoformat(r["trading_date"]) for r in flagged}
    flagged_panel = panel.filter(pc.is_in(panel["trading_date"], value_set=__import__("pyarrow").array(sorted(flagged_dates))))
    traded_by_day_contract = defaultdict(list)
    for bar in flagged_panel.to_pylist():
        traded_by_day_contract[(bar["trading_date"], bar["contract"])].append(bar["timestamp_utc"])
    for r in flagged:
        d = date.fromisoformat(r["trading_date"])
        adjacent = [x for x in old if abs((date.fromisoformat(x["trading_date"]) - d).days) <= 1]
        traded = sorted(traded_by_day_contract[(d, r["selected_contract"])])
        gaps = [(b-a).total_seconds() / 60 - 1 for a,b in zip(traded, traded[1:]) if (b-a).total_seconds() > 60]
        investigations.append(dict(**r, adjacent_observed_trade_bars={x["trading_date"]: int(x["observed_minute_bars"]) for x in adjacent},
                                   selected_first_bar_utc=traded[0].isoformat() if traded else None,
                                   selected_last_bar_utc=traded[-1].isoformat() if traded else None,
                                   interior_no_bar_runs=len(gaps), longest_interior_no_bar_run_minutes=max(gaps, default=0),
                                   finding="Outside scheduled session" if r["reason_code"] == "NONSESSION_PREOPEN_BAR" else
                                   "Provider day flagged; exact missing intervals cannot be proved from OHLCV alone",
                                   required_evidence="CME dated exception plus independent trades/status or Databento repair record"))
    missing_degraded_utc_dates = sorted(set(previous["degraded_provider_dates"]) -
                                        {d for r in flagged for d in r["provider_condition"].replace(";", ":").split(":") if len(d) == 10 and d[4] == "-"} -
                                        {"2026-10-06"})
    for missing_day in missing_degraded_utc_dates:
        investigations.append(dict(utc_date=missing_day, finding="Provider flagged this UTC date; no matching old coverage row cited it. The original manifests retain the condition.",
                                   condition=previous["degraded_provider_conditions"][missing_day],
                                   required_evidence="CME schedule and independent trade/status coverage"))
    # Include the source-revision dispute separately: it is absent from the 35 old flagged rows.
    investigations.append(dict(trading_date="2026-10-06", classification=next(r["classification"] for r in sessions if r["trading_date"] == "2026-10-06"),
                               finding="Discovery condition degraded on 2026-10-06; final manifest condition available, last modified 2026-10-08; full 1380 traded-minute grid",
                               discovery_condition="degraded", final_condition=oct_condition,
                               final_manifest=str(latest_manifest.relative_to(ROOT)),
                               interpretation="Provider revision between snapshots; later available condition applies to retained final download"))
    by_year = defaultdict(lambda: Counter())
    for r in sessions:
        by_year[r["trading_date"][:4]][r["classification"]] += 1
    for r in calendar:
        if r["weekday_candidate"]:
            by_year[r["trading_date"][:4]]["weekday_candidates"] += 1
        if r["weekday_candidate"] and not r["observed"]:
            by_year[r["trading_date"][:4]]["unobserved_weekday_candidates"] += 1
    counts = Counter(r["classification"] for r in sessions)
    reasons = Counter(r["reason_code"] for r in sessions)
    accepted = [r["trading_date"] for r in sessions if r["classification"] == "ACCEPT"]
    provisional_missing = [r["trading_date"] for r in calendar if r["weekday_candidate"] and not r["observed"]]
    unexpected = [r["trading_date"] for r in sessions if date.fromisoformat(r["trading_date"]).weekday() >= 5]
    report = dict(status="PARTIAL_CERTIFICATION_HISTORICAL_CME_EXCEPTIONS_PENDING",
                  scope=[FIRST.isoformat(), LAST.isoformat()], observed_trading_dates=len(sessions),
                  expected_sessions=None, expected_sessions_note="No authoritative day-by-day CME NQ exception archive was obtained; weekday template is not a certified expected-session count.",
                  provisional_weekday_candidates=sum(r["weekday_candidate"] for r in calendar),
                  accepted_sessions=counts["ACCEPT"], rejected_sessions=counts["REJECT"], unresolved_sessions=counts["UNRESOLVED"],
                  missing_expected_sessions=None, provisional_unobserved_weekday_candidates=provisional_missing,
                  unexpected_sessions=unexpected, coverage_by_year={y: dict(c) for y, c in sorted(by_year.items())},
                  reason_code_counts=dict(sorted(reasons.items())), accepted_dates=accepted,
                  exact_usable_research_date_range="2026-09-14 through 2026-09-25 only as one contiguous block; 2026-10-06 separately accepted. No certified contiguous full-history range.",
                  first_session_excluded="2010-06-07: no prior completed session volume buffer",
                  input_sha256={str((OUT / "coverage-by-session.csv").relative_to(ROOT)): sha(OUT / "coverage-by-session.csv"),
                                str((OUT / "acceptance-report.json").relative_to(ROOT)): sha(OUT / "acceptance-report.json"),
                                str((OUT / "nq_outright_ohlcv_1m.parquet").relative_to(ROOT)): sha(OUT / "nq_outright_ohlcv_1m.parquet"),
                                str(latest_manifest.relative_to(ROOT)): sha(latest_manifest)},
                  prior_grid_rule_retired=True, flagged_observed_session_count=35,
                  degraded_inconsistent_investigation_count=len(investigations),
                  evidence_limit="An absent trade-generated OHLCV record is ambiguous. Dataset condition is UTC-day and dataset-wide; DBN completeness proves request delivery, not every active market minute.",
                  source_urls={"CME_2012_CHANGE":"https://www.cmegroup.com/content/dam/cmegroup/education/files/eq-trading-hours.pdf",
                               "CME_2015_CHANGE":"https://www.cmegroup.com/tools-information/lookups/advisories/electronic-trading/20150824.html",
                               "CME_2021_CHANGE":"https://www.cmegroup.com/notices/electronic-trading/2021/06/20210621.html",
                               "CME_2026_HOURS":"https://www.cmegroup.com/trading-hours.html",
                               "DATABENTO_OHLCV":"https://databento.com/docs/knowledge-base",
                               "DATABENTO_CONDITION":"https://databento.com/docs/api-reference-historical/metadata/metadata-get-dataset-condition"})
    for filename, rows in (("certification-calendar-by-date.csv", calendar), ("certification-by-session.csv", sessions)):
        with (OUT / filename).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with (OUT / "accepted-sessions.csv").open("w", newline="") as f:
        accepted_rows = [r for r in sessions if r["classification"] == "ACCEPT"]
        w = csv.DictWriter(f, fieldnames=list(sessions[0])); w.writeheader(); w.writerows(accepted_rows)
    (OUT / "degraded-session-investigation.json").write_text(json.dumps(investigations, indent=2) + "\n")
    (OUT / "certification-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "observed_trading_dates", "provisional_weekday_candidates", "accepted_sessions", "rejected_sessions", "unresolved_sessions", "reason_code_counts")}, indent=2))


if __name__ == "__main__":
    main()
