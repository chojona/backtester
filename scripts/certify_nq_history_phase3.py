"""Phase 3 NQ history audit. Outputs are isolated under ignored results/.

Only CME-sourced regular-hour regimes are asserted. A conservative holiday
guard withholds Tier B; it is never used as evidence of a CME closure.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq
from backtester.nq_research import validate_strict_metadata
from dateutil.easter import easter
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/databento-nq-full-history/phase3-v3.0.0"
OLD = ROOT / "results/databento-nq-full-history"
REGISTRY = ROOT / "calendars/nq-history-v3.json"
EVIDENCE = ROOT / "calendars/sources/nq-history-v3-evidence.json"
NY = ZoneInfo("America/New_York")
VERSION = "nq-history-v3.0.0"
UTC = timezone.utc


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_registry() -> dict:
    registry = json.loads(REGISTRY.read_text())
    evidence = json.loads(EVIDENCE.read_text())
    assert registry["version"] == evidence["version"] == VERSION
    ids = {row["id"] for row in evidence["evidence"]}
    for regime in registry["regimes"]:
        assert set(regime["source_ids"]) <= ids
    return registry


def regime_for(day: date, registry: dict) -> dict:
    matches = [r for r in registry["regimes"] if r["first"] <= day.isoformat() <= r["last"]]
    if len(matches) != 1:
        raise ValueError(f"Missing or overlapping regime for {day}")
    return matches[0]


def date_evidence(day: date, registry: dict) -> dict | None:
    matches = [x for x in registry["date_evidence"] if x["first"] <= day.isoformat() <= x["last"]]
    if len(matches) > 1:
        raise ValueError(f"Overlapping date evidence for {day}")
    return matches[0] if matches else None


def holiday_guard(first: date, last: date, registry: dict) -> set[date]:
    """Conservative exclusion only; dates here are not declared CME closed."""
    holidays = set(USFederalHolidayCalendar().holidays(
        start=f"{first.year}-01-01", end=f"{last.year}-12-31").date)
    for year in range(first.year, last.year + 1):
        holidays.update({easter(year) - timedelta(days=2), date(year, 12, 24), date(year, 12, 31)})
        thanksgiving = date(year, 11, 1)
        thanksgiving += timedelta(days=(3 - thanksgiving.weekday()) % 7 + 21)
        holidays.add(thanksgiving + timedelta(days=1))
    holidays.update(date.fromisoformat(x) for x in registry["provisional_exception_guard"]["additional_review_dates"])
    radius = registry["provisional_exception_guard"]["guard_days_each_side"]
    return {holiday + timedelta(days=offset) for holiday in holidays for offset in range(-radius, radius + 1)}


def schedule_minutes(day: date, regime: dict) -> tuple[int, int, set[int]] | None:
    """UTC minute grid for post-2012 ordinary sessions, excluding the CME pause."""
    if regime["id"] == "R1_PRE_2012_TRADE_DATE_CHANGE":
        return None  # Old parquet's date assignment must be rebuilt first.
    opened = datetime.combine(day - timedelta(days=1), time(18), NY).astimezone(UTC)
    close_hour, close_minute = map(int, regime["close_et"].split(":"))
    closed = datetime.combine(day, time(close_hour, close_minute), NY).astimezone(UTC)
    first = int(opened.timestamp() // 60)
    end = int(closed.timestamp() // 60)
    expected = set(range(first, end))
    if regime.get("pause_et"):
        pause_start, pause_end = regime["pause_et"].split("-")
        a = datetime.combine(day, time.fromisoformat(pause_start), NY).astimezone(UTC)
        b = datetime.combine(day, time.fromisoformat(pause_end), NY).astimezone(UTC)
        expected.difference_update(range(int(a.timestamp() // 60), int(b.timestamp() // 60)))
    return first, end, expected


def classify(*, day: date, calendar_state: str, provider_state: str,
             contract_state: str, coverage_state: str) -> tuple[str, str]:
    if calendar_state == "NONSESSION_PREOPEN":
        return "D", "D_NONSESSION_PREOPEN_BAR"
    if contract_state == "NO_PRIOR_SESSION_BUFFER":
        return "D", "D_NO_PRIOR_SESSION_ROLL_BUFFER"
    if calendar_state == "REVIEWED_REGULAR" and provider_state in ("AVAILABLE", "REVISED_AVAILABLE") and coverage_state == "FULL_ACTIVE_GRID" and contract_state == "PRIOR_VOLUME_PRESENT":
        return "A", "A_SOURCE_REVIEWED_COMPLETE"
    if provider_state != "AVAILABLE" and provider_state != "REVISED_AVAILABLE":
        return "C", "C_PROVIDER_DEGRADED_OR_METADATA_MISSING"
    if calendar_state == "PRE2012_MAPPING_UNRESOLVED":
        return "C", "C_PRE2012_TRADE_DATE_REMAP_REQUIRED"
    if calendar_state == "CME_HOLIDAY_WINDOW_HOURS_UNRESOLVED":
        return "C", "C_CME_HOLIDAY_HOURS_NOT_CAPTURED"
    if calendar_state == "HOLIDAY_EXCEPTION_GUARD":
        return "C", "C_HOLIDAY_OR_EARLY_CLOSE_UNVERIFIED"
    if contract_state != "PRIOR_VOLUME_PRESENT":
        return "C", "C_CAUSAL_CONTRACT_EVIDENCE_INCOMPLETE"
    if coverage_state != "FULL_ACTIVE_GRID":
        return "C", "C_SPARSE_OR_OFF_SCHEDULE_TRADE_BARS"
    if calendar_state == "REGIME_PROVISIONAL":
        return "B", "B_REGULAR_REGIME_FULL_ACTIVE_GRID"
    return "C", "C_CALENDAR_EVIDENCE_INCOMPLETE"


def selected_bar_evidence(selected: dict[date, str]) -> tuple[dict[date, set[int]], dict[tuple[date, str], int], Counter]:
    """One streaming pass; keep only selected-contract minute sets and daily volumes."""
    minutes: dict[date, set[int]] = defaultdict(set)
    volume: dict[tuple[date, str], int] = defaultdict(int)
    duplicates = Counter()
    source = pq.ParquetFile(OLD / "nq_outright_ohlcv_1m.parquet")
    for batch in source.iter_batches(batch_size=100_000, columns=["ts_event_ns", "trading_date", "contract", "volume"]):
        stamps, days, contracts, sizes = (batch.column(i).to_pylist() for i in range(4))
        for stamp, day, contract, size in zip(stamps, days, contracts, sizes):
            volume[(day, contract)] += size
            if selected.get(day) == contract:
                minute = stamp // 60_000_000_000
                if minute in minutes[day]:
                    duplicates[day] += 1
                minutes[day].add(minute)
    return minutes, volume, duplicates


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def segments_for(allowed: set[date], observed_order: list[date]) -> dict[date, int]:
    """Break a segment at every excluded observed date or four-day calendar gap."""
    result = {}
    segment = 0
    previous_observed = None
    for day in observed_order:
        if day in allowed:
            if previous_observed not in allowed or (day - previous_observed).days > 3:
                segment += 1
            result[day] = segment
        previous_observed = day
    return result


def write_research_dataset(path: Path, allowed: dict[date, str], tiers: dict[date, str], segments: dict[date, int], *, strict=False) -> int:
    if strict and any(tiers.get(day) != "A" for day in allowed):
        raise ValueError("Strict dataset selection contains a non-Tier A session")
    source = pq.ParquetFile(OLD / "nq_outright_ohlcv_1m.parquet")
    writer = None
    count = 0
    for batch in source.iter_batches(batch_size=100_000):
        table = pa.Table.from_batches([batch])
        days = table["trading_date"].to_pylist()
        contracts = table["contract"].to_pylist()
        positions = [i for i, (day, contract) in enumerate(zip(days, contracts)) if allowed.get(day) == contract]
        if not positions:
            continue
        chosen = table.take(pa.array(positions, type=pa.int64()))
        chosen_days = [days[i] for i in positions]
        chosen = chosen.append_column("quality_tier", pa.array([tiers[d] for d in chosen_days], type=pa.string()))
        chosen = chosen.append_column("certification_version", pa.array([VERSION] * len(positions), type=pa.string()))
        chosen = chosen.append_column("research_segment_id", pa.array([segments[d] for d in chosen_days], type=pa.int32()))
        if writer is None:
            writer = pq.ParquetWriter(path, chosen.schema, compression="zstd")
        writer.write_table(chosen)
        count += len(positions)
    if writer is None:
        raise ValueError("Empty research dataset")
    writer.close()
    if strict:
        allowlist = {day: (contract, "A", VERSION, segments[day]) for day, contract in allowed.items()}
        def metadata_rows():
            parquet = pq.ParquetFile(path)
            columns = ["trading_date", "contract", "quality_tier", "certification_version", "research_segment_id"]
            for batch in parquet.iter_batches(batch_size=100_000, columns=columns):
                yield from zip(*(batch.column(i).to_pylist() for i in range(len(columns))))
        if validate_strict_metadata(metadata_rows(), allowlist, certification_version=VERSION) != count:
            raise ValueError("Strict dataset row count changed during readback")
    return count


def main() -> None:
    registry = load_registry()
    OUT.mkdir(parents=True, exist_ok=True)
    old = list(csv.DictReader((OLD / "coverage-by-session.csv").open()))
    if len(old) != 4207:
        raise ValueError("Expected 4,207 prior observed dates")
    by_day = {date.fromisoformat(row["trading_date"]): row for row in old}
    if len(by_day) != len(old):
        raise ValueError("Duplicate observed trading dates")
    first = date.fromisoformat(registry["scope"]["first_trading_date"])
    last = date.fromisoformat(registry["scope"]["last_trading_date"])
    guard = holiday_guard(first, last, registry)
    prior_report = json.loads((OLD / "acceptance-report.json").read_text())
    if prior_report["observed_trading_dates"] != len(old) or prior_report["checks"]["raw_checksums"] != "PASS" or \
            prior_report["checks"]["cross_chunk_duplicates"] != "PASS_EXACT_ONLY" or \
            prior_report["consolidated_parquet_sha256"] != digest(OLD / "nq_outright_ohlcv_1m.parquet"):
        raise ValueError("Retained upstream raw/parquet integrity evidence does not reconcile")
    degraded_utc_dates = set(prior_report["degraded_provider_conditions"])
    chosen = {day: row["selected_contract"] for day, row in by_day.items()}
    minutes, volume, duplicates = selected_bar_evidence(chosen)
    old_order = sorted(by_day)
    previous = {d: old_order[i-1] if i else None for i, d in enumerate(old_order)}
    sessions = []
    calendar = []
    missing_candidates = []
    day = first
    while day <= last:
        regime = regime_for(day, registry)
        reviewed_entry = date_evidence(day, registry)
        is_reviewed = bool(reviewed_entry and reviewed_entry["state"] == "REVIEWED_REGULAR")
        is_guarded = day in guard
        legacy = by_day.get(day)
        grid = schedule_minutes(day, regime) if day.weekday() < 5 else None
        source_ids = list(regime["source_ids"]) + (reviewed_entry["source_ids"] if reviewed_entry else [])
        if day.year == 2026:
            source_ids.append("CME_2026_FRIDAY_HOLIDAY")
        if is_guarded:
            source_ids.extend(("OPM_FEDERAL_HOLIDAYS", "PMC_CME_EQUITY"))
        if day.weekday() >= 5:
            calendar_state = "NONSESSION_PREOPEN" if legacy else "WEEKEND"
        elif regime["id"] == "R1_PRE_2012_TRADE_DATE_CHANGE":
            calendar_state = "PRE2012_MAPPING_UNRESOLVED"
        elif is_reviewed:
            calendar_state = "REVIEWED_REGULAR"
        elif reviewed_entry and reviewed_entry["state"] == "CME_HOLIDAY_WINDOW_HOURS_UNRESOLVED":
            calendar_state = "CME_HOLIDAY_WINDOW_HOURS_UNRESOLVED"
        elif is_guarded:
            calendar_state = "HOLIDAY_EXCEPTION_GUARD"
        else:
            calendar_state = "REGIME_PROVISIONAL"
        calendar.append(dict(certification_version=VERSION, trading_date=day.isoformat(), regime_id=regime["id"],
                             weekday=day.strftime("%A"), calendar_state=calendar_state,
                             source_ids=";".join(dict.fromkeys(source_ids)),
                             observed=bool(legacy), normal_active_minutes=len(grid[2]) if grid else "",
                             exception_verified=is_reviewed))
        if not legacy:
            if day.weekday() < 5:
                condition_dates = [x for x in (day - timedelta(days=1), day) if x.isoformat() in degraded_utc_dates]
                code = "POTENTIAL_PROVIDER_GAP" if condition_dates and not is_guarded else "HOLIDAY_OR_UNVERIFIED_ABSENCE"
                missing_candidates.append(dict(trading_date=day.isoformat(), calendar_state=calendar_state,
                                               reason_code=code, authoritative_expected=False,
                                               source_ids=";".join(source_ids)))
            day += timedelta(days=1)
            continue
        raw_condition = legacy["provider_condition"]
        provider_state = ("REVISED_AVAILABLE" if day == last else "AVAILABLE") if raw_condition == "available_for_session_utc_days" else (
            "METADATA_MISSING" if "missing_condition_metadata" in raw_condition else "DEGRADED")
        prev = previous[day]
        if day == first:
            contract_state = "NO_PRIOR_SESSION_BUFFER"
        elif prev is None or prev.weekday() >= 5 or (day - prev).days > 3 or \
                by_day[prev]["provider_condition"] != "available_for_session_utc_days" or volume[(prev, chosen[day])] <= 0 or \
                prev in guard or \
                (schedule_minutes(prev, regime_for(prev, registry)) is not None and
                 minutes.get(prev, set()) != schedule_minutes(prev, regime_for(prev, registry))[2]):
            contract_state = "PRIOR_VOLUME_INCOMPLETE"
        else:
            contract_state = "PRIOR_VOLUME_PRESENT"
        actual = minutes.get(day, set())
        if grid is None:
            coverage_state, expected_count, observed_active, off_schedule = "DATE_MAPPING_UNRESOLVED", "", "", ""
        else:
            start, end, expected = grid
            observed_active = len(actual & expected)
            off_schedule = len(actual - expected)
            expected_count = len(expected)
            coverage_state = "FULL_ACTIVE_GRID" if actual == expected and not duplicates[day] else "SPARSE_OR_OFF_SCHEDULE"
        tier, reason = classify(day=day, calendar_state=calendar_state, provider_state=provider_state,
                                contract_state=contract_state, coverage_state=coverage_state)
        sessions.append(dict(certification_version=VERSION, trading_date=day.isoformat(), tier=tier, reason_code=reason,
                             calendar_validity=calendar_state, provider_integrity=provider_state,
                             contract_selection=contract_state, observed_coverage=coverage_state,
                             research_eligibility="STRICT_AND_EXPLORATORY" if tier == "A" else
                             "EXPLORATORY_ONLY" if tier == "B" else "EXCLUDED",
                             selected_contract=chosen[day], expected_active_minutes=expected_count,
                             observed_active_minutes=observed_active, off_schedule_trade_minutes=off_schedule,
                             duplicate_selected_minutes=duplicates[day],
                             source_ids=";".join(dict.fromkeys(source_ids))))
        day += timedelta(days=1)
    if len(sessions) != 4207:
        raise AssertionError("Session reclassification lost a date")
    tiers = {date.fromisoformat(r["trading_date"]): r["tier"] for r in sessions}
    strict = {d: chosen[d] for d, tier in tiers.items() if tier == "A"}
    exploratory = {d: chosen[d] for d, tier in tiers.items() if tier in ("A", "B")}
    strict_segments = segments_for(set(strict), old_order)
    exploratory_segments = segments_for(set(exploratory), old_order)
    for row in sessions:
        d = date.fromisoformat(row["trading_date"])
        row["strict_segment_id"] = strict_segments.get(d, "")
        row["exploratory_segment_id"] = exploratory_segments.get(d, "")
    write_csv(OUT / "calendar-by-date.csv", calendar, list(calendar[0]))
    write_csv(OUT / "certification-by-session.csv", sessions, list(sessions[0]))
    write_csv(OUT / "strict-certified-allowlist.csv", [r for r in sessions if r["tier"] == "A"], list(sessions[0]))
    write_csv(OUT / "exploratory-research-allowlist.csv", [r for r in sessions if r["tier"] in ("A", "B")], list(sessions[0]))
    write_csv(OUT / "missing-date-candidates.csv", missing_candidates,
              list(missing_candidates[0]) if missing_candidates else ["trading_date", "calendar_state", "reason_code", "authoritative_expected", "source_ids"])
    strict_rows = write_research_dataset(OUT / "strict-certified.parquet", strict, tiers, strict_segments, strict=True)
    exploratory_rows = write_research_dataset(OUT / "exploratory-research.parquet", exploratory, tiers, exploratory_segments)
    annual = []
    for year in range(first.year, last.year + 1):
        subset = [r for r in sessions if r["trading_date"].startswith(str(year))]
        counts = Counter(r["tier"] for r in subset)
        annual.append(dict(year=year, observed=len(subset), tier_a=counts["A"], tier_b=counts["B"],
                           tier_c=counts["C"], tier_d=counts["D"],
                           unobserved_weekday_candidates=sum(x["trading_date"].startswith(str(year)) for x in missing_candidates)))
    write_csv(OUT / "annual-coverage.csv", annual, list(annual[0]))
    counts = Counter(r["tier"] for r in sessions)
    report = dict(version=VERSION, scope=[first.isoformat(), last.isoformat()],
                  status="PARTIAL_HISTORICAL_CERTIFICATION_WITH_PROVISIONAL_RESEARCH_TIER",
                  observed_dates=len(sessions), tier_counts=dict(sorted(counts.items())),
                  expected_sessions_authoritative=None, missing_expected_sessions_authoritative=None,
                  unobserved_weekday_candidates=len(missing_candidates),
                  potential_provider_gap_candidates=[r["trading_date"] for r in missing_candidates if r["reason_code"] == "POTENTIAL_PROVIDER_GAP"],
                  reason_code_counts=dict(sorted(Counter(r["reason_code"] for r in sessions).items())),
                  strict_research_dates=len(strict), exploratory_research_dates=len(exploratory),
                  strict_research_segments=max(strict_segments.values()),
                  exploratory_research_segments=max(exploratory_segments.values()),
                  strict_rows=strict_rows, exploratory_rows=exploratory_rows,
                  strict_date_range=[min(strict).isoformat(), max(strict).isoformat()],
                  exploratory_date_range=[min(exploratory).isoformat(), max(exploratory).isoformat()],
                  caveat="Tier B validates regular regime, provider condition, causal contract evidence and complete active trade-minute grid, but individual historical CME exceptions were not fully audited. Do not call Tier B exchange certified.",
                  source_hashes={str(p.relative_to(ROOT)): digest(p) for p in
                                 (REGISTRY, EVIDENCE, OLD / "coverage-by-session.csv", OLD / "nq_outright_ohlcv_1m.parquet", OLD / "acceptance-report.json")},
                  output_hashes={name: digest(OUT / name) for name in (
                      "calendar-by-date.csv", "certification-by-session.csv", "strict-certified-allowlist.csv",
                      "exploratory-research-allowlist.csv", "missing-date-candidates.csv", "annual-coverage.csv",
                      "strict-certified.parquet", "exploratory-research.parquet")})
    (OUT / "certification-report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Phase 3 NQ historical certification", "", f"Version: `{VERSION}`. Status: **partial historical certification**.", "",
             "## Session decisions", "", "| Tier | Meaning | Observed dates | Research use |", "|---|---|---:|---|",
             f"| A | Date-reviewed CME schedule, clean provider, causal contract, full active grid | {counts['A']:,} | Strict and exploratory |",
             f"| B | Source-backed regular regime; dated exceptions remain provisional | {counts['B']:,} | Exploratory only |",
             f"| C | Evidence unresolved | {counts['C']:,} | Excluded |",
             f"| D | Contradicted or boundary-invalid | {counts['D']:,} | Excluded |", "",
             f"Strict data: {strict_rows:,} selected-contract bars across {len(strict)} dates. Exploratory data: {exploratory_rows:,} bars across {len(exploratory)} dates.",
             f"The datasets label {max(strict_segments.values())} strict and {max(exploratory_segments.values())} exploratory continuity segments. The date ranges in the JSON report are endpoints, not claims of contiguous coverage. Tier B is not exchange certified.", "",
             "## Calendar and missing dates", "",
             "The versioned registry records the 2012, 2015 and 2021 trading-hour changes and pre-2012 trade-date behavior. Calendar rows carry source IDs and exception status. Individual historical holiday and early-close exceptions remain incomplete.",
             f"There are {len(missing_candidates)} unobserved weekday candidates. No complete authoritative expected-session count is asserted. Five 2014 dates are potential provider gaps, not certified missing CME sessions: {', '.join(report['potential_provider_gap_candidates'])}.", "",
             "The conservative federal/Good Friday/adjacent-day guard only withholds Tier B; it never asserts that CME was closed. The independent pandas_market_calendars CME equity source has a documented conflict with CME's 2012–2015 close and was not adopted as an authoritative schedule.", "",
             "## Data evidence", "",
             "Tier B requires provider `available`, an ordinary weekday outside the exception guard, full selected-contract coverage of every scheduled active minute, no off-schedule or duplicate selected minute, and usable prior-session volume evidence. A missing OHLCV bar is never called missing data solely because it is absent. Degraded and metadata-incomplete sessions remain Tier C.",
             "The original eleven accepted dates remain Tier A, including the October 6 provider revision. The first session and the Sunday 2018-08-05 preopen artifact remain Tier D. Tier C and D dates are absent from both research datasets.", "",
             "## Reproduction", "", "Run `python -m scripts.certify_nq_history_phase3` from the repository root. The JSON report records input and output SHA-256 hashes; CSVs give all decisions, yearly counts and allowlists. No trading or modeling code is changed.", ""]
    (OUT / "certification-report.md").write_text("\n".join(lines))
    annual_lines = ["# Annual NQ Phase 3 coverage", "", "Counts are observed dates, not authoritative expected CME sessions.", "",
                    "| Year | A | B | C | D | Unobserved weekday candidates |", "|---:|---:|---:|---:|---:|---:|"]
    annual_lines += [f"| {r['year']} | {r['tier_a']} | {r['tier_b']} | {r['tier_c']} | {r['tier_d']} | {r['unobserved_weekday_candidates']} |" for r in annual]
    annual_lines += ["", "See `annual-coverage.csv` and `missing-date-candidates.csv` for reproducible rows.", ""]
    (OUT / "annual-coverage.md").write_text("\n".join(annual_lines))
    print(json.dumps({k: report[k] for k in ("version", "status", "tier_counts", "strict_rows", "exploratory_rows")}, indent=2))


if __name__ == "__main__":
    main()
