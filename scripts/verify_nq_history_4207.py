"""Independently verify retained NQ history and the Phase 3 research gate.

Run from the repository root with the Python 3.12 environment. This reads the
licensed local data but writes only an ignored JSON report under results/.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/databento-nq-full-history"
PHASE = BASE / "phase3-v3.0.0"
RAW = ROOT / "data/raw/databento/NQ/full-history/8c2dcea828fa59a0"
UTC = timezone.utc
NY = ZoneInfo("America/New_York")
MINUTE_NS = 60_000_000_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def raw_overlap_check(report: dict) -> tuple[dict, dict[str, set[str]]]:
    manifests = [(p, json.loads(p.read_text())) for p in RAW.glob("*/manifest.json")]
    manifests.sort(key=lambda pair: (pair[1]["request"]["start"], str(pair[0])))
    require(len(manifests) == report["complete_chunks"] == 67, "Raw chunk count changed")
    seen: dict[tuple[int, int], tuple[int, ...]] = {}
    raw_count = duplicate_count = 0
    condition_values: dict[str, set[str]] = defaultdict(set)
    for manifest_path, manifest in manifests:
        require(manifest["download_complete"] and manifest["provider"] == "Databento", "Incomplete raw chunk")
        require(manifest["request"]["dataset"] == "GLBX.MDP3" and manifest["request"]["schema"] == "ohlcv-1m", "Unexpected request")
        for filename, expected in manifest["files"].items():
            require(sha256(manifest_path.parent / filename) == expected, f"Raw checksum mismatch: {manifest_path.parent / filename}")
        for item in manifest.get("conditions", []):
            condition_values[item["date"]].add(item.get("condition", "unknown"))
        start = int(datetime.fromisoformat(manifest["request"]["start"]).timestamp() * 1_000_000_000)
        end = int(datetime.fromisoformat(manifest["request"]["end"]).timestamp() * 1_000_000_000)
        seen = {key: value for key, value in seen.items() if key[0] >= start}
        with (manifest_path.parent / "ohlcv-1m.jsonl").open() as stream:
            for line in stream:
                record = json.loads(line)
                ts = int(record["hd"]["ts_event"])
                iid = int(record["hd"]["instrument_id"])
                values = tuple(int(record[k]) for k in ("open", "high", "low", "close", "volume"))
                require(start <= ts < end and ts % MINUTE_NS == 0, "Raw UTC timestamp outside request or minute grid")
                op, hi, lo, cl, vol = values
                require(min(op, hi, lo, cl, vol) > 0 and hi >= max(op, lo, cl) and lo <= min(op, hi, cl), "Invalid raw OHLCV")
                key = (ts, iid)
                prior = seen.get(key)
                if prior is not None:
                    require(prior == values, f"Conflicting duplicate: {key}")
                    duplicate_count += 1
                else:
                    seen[key] = values
                raw_count += 1
    require(raw_count == report["raw_ohlcv_rows"], "Raw row count changed")
    require(duplicate_count == report["deduplicated_exact_overlap_rows"], "Overlap duplicate count changed")
    require(raw_count - duplicate_count == report["output_rows"], "Unique raw rows do not reconcile")
    summary = dict(chunks=len(manifests), raw_rows=raw_count, exact_overlap_duplicates=duplicate_count,
                   conflicting_duplicates=0, provider_condition_conflicts={k: sorted(v) for k, v in condition_values.items() if len(v) > 1})
    return summary, condition_values


def expected_grid(day: date, regime: dict) -> set[int] | None:
    if day.weekday() >= 5 or regime["id"] == "R1_PRE_2012_TRADE_DATE_CHANGE":
        return None
    opened = datetime.combine(day - timedelta(days=1), datetime.min.time(), NY).replace(hour=18).astimezone(UTC)
    h, m = map(int, regime["close_et"].split(":"))
    closed = datetime.combine(day, datetime.min.time(), NY).replace(hour=h, minute=m).astimezone(UTC)
    grid = set(range(int(opened.timestamp() // 60), int(closed.timestamp() // 60)))
    if regime.get("pause_et"):
        begin, end = regime["pause_et"].split("-")
        bh, bm = map(int, begin.split(":"))
        eh, em = map(int, end.split(":"))
        a = datetime.combine(day, datetime.min.time(), NY).replace(hour=bh, minute=bm).astimezone(UTC)
        b = datetime.combine(day, datetime.min.time(), NY).replace(hour=eh, minute=em).astimezone(UTC)
        grid.difference_update(range(int(a.timestamp() // 60), int(b.timestamp() // 60)))
    return grid


def main() -> None:
    upstream = json.loads((BASE / "acceptance-report.json").read_text())
    certification = json.loads((PHASE / "certification-report.json").read_text())
    for name, expected in certification["source_hashes"].items():
        require(sha256(ROOT / name) == expected, f"Certification source hash changed: {name}")
    for name, expected in certification["output_hashes"].items():
        require(sha256(PHASE / name) == expected, f"Certification output hash changed: {name}")
    raw, provider_conditions = raw_overlap_check(upstream)

    observed = rows(BASE / "coverage-by-session.csv")
    decisions = rows(PHASE / "certification-by-session.csv")
    calendar = {r["trading_date"]: r for r in rows(PHASE / "calendar-by-date.csv")}
    strict_allow = rows(PHASE / "strict-certified-allowlist.csv")
    require(len(observed) == len(decisions) == 4207, "Observed date count changed")
    old_by_day = {r["trading_date"]: r for r in observed}
    by_day = {r["trading_date"]: r for r in decisions}
    require(len(old_by_day) == len(by_day) == 4207 and set(old_by_day) == set(by_day), "Date register mismatch or duplicates")
    registry = json.loads((ROOT / "calendars/nq-history-v3.json").read_text())
    regimes = {r["id"]: r for r in registry["regimes"]}
    minute_sets: dict[date, set[int]] = defaultdict(set)
    selected_duplicates = Counter()
    daily_volume: dict[date, Counter[str]] = defaultdict(Counter)
    daily_contracts: dict[date, set[str]] = defaultdict(set)
    count = 0
    source = pq.ParquetFile(BASE / "nq_outright_ohlcv_1m.parquet")
    require(str(source.schema_arrow.field("timestamp_utc").type) == "timestamp[ns, tz=UTC]", "UTC timestamp type changed")
    for batch in source.iter_batches(batch_size=100_000, columns=["ts_event_ns", "timestamp_utc", "trading_date", "contract", "volume"]):
        table = pa.Table.from_batches([batch])
        stamps = table["ts_event_ns"]
        require(pc.all(pc.equal(stamps, pc.cast(table["timestamp_utc"], pa.int64()))).as_py(), "UTC timestamp differs from nanoseconds")
        for ts, day, contract, volume in zip(stamps.to_pylist(), table["trading_date"].to_pylist(),
                                              table["contract"].to_pylist(), table["volume"].to_pylist()):
            require(ts % MINUTE_NS == 0 and day.isoformat() in old_by_day and volume > 0,
                    "Consolidated row has off-minute timestamp, unknown date or nonpositive volume")
            daily_volume[day][contract] += volume
            daily_contracts[day].add(contract)
            if contract == old_by_day[day.isoformat()]["selected_contract"]:
                minute = ts // MINUTE_NS
                if minute in minute_sets[day]:
                    selected_duplicates[day] += 1
                minute_sets[day].add(minute)
            count += 1
    require(count == upstream["output_rows"] == source.metadata.num_rows, "Consolidated row count mismatch")

    ordered = sorted(daily_contracts)
    require([d.isoformat() for d in ordered] == sorted(by_day), "Parquet date coverage differs from decision register")
    rolls = 0
    for index, day in enumerate(ordered):
        label = day.isoformat()
        row = by_day[label]
        legacy = old_by_day[label]
        require(row["reason_code"].startswith(row["tier"] + "_") and row["source_ids"],
                f"Decision lacks a reproducible reason or source: {label}")
        require(row["selected_contract"] == legacy["selected_contract"], f"Selected contract mismatch: {label}")
        if index:
            prior = ordered[index - 1]
            leader = max(daily_contracts[day], key=lambda c: (daily_volume[prior][c], c))
            require(row["selected_contract"] == leader, f"Prior-volume roll rule mismatch: {label}")
            rolls += row["selected_contract"] != by_day[prior.isoformat()]["selected_contract"]
        regime = regimes[calendar[label]["regime_id"]]
        require(regime["first"] <= label <= regime["last"], f"Wrong CME regime: {label}")
        grid = expected_grid(day, regime)
        actual = minute_sets[day]
        if grid is None:
            require(row["observed_coverage"] == "DATE_MAPPING_UNRESOLVED" and row["tier"] not in ("A", "B"), f"Unmapped or nonsession date promoted: {label}")
        else:
            require(int(row["observed_active_minutes"]) == len(actual & grid), f"Active-minute count mismatch: {label}")
            require(int(row["off_schedule_trade_minutes"]) == len(actual - grid), f"Off-schedule count mismatch: {label}")
            require(int(row["expected_active_minutes"]) == len(grid), f"Expected-minute count mismatch: {label}")
            require(int(row["duplicate_selected_minutes"]) == selected_duplicates[day], f"Selected duplicate count mismatch: {label}")
        tier = row["tier"]
        if tier in ("A", "B"):
            require(grid is not None and actual == grid and not selected_duplicates[day], f"Eligible grid incomplete: {label}")
            require(row["provider_integrity"] in ("AVAILABLE", "REVISED_AVAILABLE") and row["contract_selection"] == "PRIOR_VOLUME_PRESENT", f"Eligible provider/roll evidence invalid: {label}")
            utc_days = {datetime.fromtimestamp(min(actual) * 60, UTC).date().isoformat(),
                        datetime.fromtimestamp(max(actual) * 60, UTC).date().isoformat()}
            require(all(provider_conditions.get(d) == {"available"} for d in utc_days), f"Eligible provider condition not clean: {label}")
            require(row["research_eligibility"] == ("STRICT_AND_EXPLORATORY" if tier == "A" else "EXPLORATORY_ONLY"), f"Eligibility label mismatch: {label}")
            require(calendar[label]["calendar_state"] == ("REVIEWED_REGULAR" if tier == "A" else "REGIME_PROVISIONAL"), f"Calendar tier mismatch: {label}")
        else:
            require(row["research_eligibility"] == "EXCLUDED", f"Unresolved date admitted: {label}")
    require(rolls == upstream["roll_count"] == len(rows(BASE / "rolls.csv")), "Roll boundary count mismatch")
    strict_dates = {r["trading_date"] for r in strict_allow}
    require(len(strict_dates) == certification["strict_research_dates"] and strict_dates == {d for d, r in by_day.items() if r["tier"] == "A"}, "Strict allowlist mismatch")
    strict_file = pq.ParquetFile(PHASE / "strict-certified.parquet")
    strict_rows = 0
    for batch in strict_file.iter_batches(columns=["trading_date", "quality_tier", "certification_version", "contract"]):
        table = pa.Table.from_batches([batch])
        for day, tier, version, contract in zip(*(table[name].to_pylist() for name in ("trading_date", "quality_tier", "certification_version", "contract"))):
            require(day.isoformat() in strict_dates and tier == "A" and version == certification["version"] and contract == by_day[day.isoformat()]["selected_contract"], "Ineligible strict research row")
            strict_rows += 1
    require(strict_rows == certification["strict_rows"] == strict_file.metadata.num_rows, "Strict row count mismatch")
    exploratory_file = pq.ParquetFile(PHASE / "exploratory-research.parquet")
    exploratory_rows = 0
    for batch in exploratory_file.iter_batches(columns=["trading_date", "quality_tier", "contract"]):
        table = pa.Table.from_batches([batch])
        for day, tier, contract in zip(*(table[name].to_pylist() for name in ("trading_date", "quality_tier", "contract"))):
            require(tier in ("A", "B") and by_day[day.isoformat()]["tier"] == tier and
                    contract == by_day[day.isoformat()]["selected_contract"], "Excluded date in exploratory research")
            exploratory_rows += 1
    require(exploratory_rows == certification["exploratory_rows"] == exploratory_file.metadata.num_rows,
            "Exploratory row count mismatch")
    counts = dict(sorted(Counter(r["tier"] for r in decisions).items()))
    require(counts == certification["tier_counts"] and sum(counts.values()) == 4207, "Tier counts mismatch")
    result = dict(status="PASS_WITH_EXPLICIT_EXCLUSIONS", observed_dates=4207, tiers=counts,
                  strict_dates=len(strict_dates), strict_rows=strict_rows,
                  exploratory_rows=exploratory_rows, roll_boundaries=rolls,
                  raw=raw, consolidated_rows=count, checks=["raw_file_checksums", "exact_overlap_duplicates",
                  "utc_timestamps", "dated_cme_regimes_and_dst_grid", "active_minute_coverage",
                  "prior_session_volume_rolls", "provider_and_calendar_tier_gates", "strict_research_isolation"],
                  limitations=["Historical CME holiday and early-close exceptions remain incomplete; Tier B is exploratory only.",
                  "OHLCV absence cannot distinguish no-trade minutes from provider loss; Tier C remains excluded.",
                  "Pre-2012 trade-date assignment has not been rebuilt; those dates remain excluded."])
    destination = PHASE / "independent-verification.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
