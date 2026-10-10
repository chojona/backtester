"""Regression checks for the offline Phase 3 certification gate."""
import csv
import json
from datetime import date, timedelta

import pyarrow.parquet as pq

from scripts.certify_nq_history_phase3 import (
    EVIDENCE, OLD, OUT, REGISTRY, classify, holiday_guard, load_registry,
    regime_for, schedule_minutes, segments_for,
)


def test_regime_cutovers_and_pre2012_date_assignment():
    registry = load_registry()
    assert regime_for(date(2012, 11, 16), registry)["id"] == "R1_PRE_2012_TRADE_DATE_CHANGE"
    assert "next trade date" in registry["regimes"][0]["date_assignment"]
    assert regime_for(date(2012, 11, 19), registry)["close_et"] == "17:15"
    assert regime_for(date(2015, 9, 21), registry)["close_et"] == "17:00"
    assert regime_for(date(2021, 6, 25), registry)["pause_et"] == "16:15-16:30"
    assert "pause_et" not in regime_for(date(2021, 6, 28), registry)
    assert schedule_minutes(date(2012, 11, 16), regime_for(date(2012, 11, 16), registry)) is None
    assert len(schedule_minutes(date(2012, 11, 19), regime_for(date(2012, 11, 19), registry))[2]) == 1380
    assert len(schedule_minutes(date(2021, 6, 25), regime_for(date(2021, 6, 25), registry))[2]) == 1365
    assert len(schedule_minutes(date(2021, 6, 28), regime_for(date(2021, 6, 28), registry))[2]) == 1380


def test_tiers_do_not_promote_sparse_or_degraded_data():
    common = dict(day=date(2020, 1, 7), calendar_state="REGIME_PROVISIONAL",
                  provider_state="AVAILABLE", contract_state="PRIOR_VOLUME_PRESENT",
                  coverage_state="FULL_ACTIVE_GRID")
    assert classify(**common)[0] == "B"
    assert classify(**{**common, "provider_state": "DEGRADED"})[0] == "C"
    assert classify(**{**common, "coverage_state": "SPARSE_OR_OFF_SCHEDULE"})[0] == "C"
    assert classify(**{**common, "calendar_state": "HOLIDAY_EXCEPTION_GUARD"})[0] == "C"
    assert classify(**{**common, "calendar_state": "CME_HOLIDAY_WINDOW_HOURS_UNRESOLVED"})[0] == "C"
    assert classify(**{**common, "contract_state": "PRIOR_VOLUME_INCOMPLETE"})[0] == "C"
    assert classify(**{**common, "calendar_state": "NONSESSION_PREOPEN"})[0] == "D"


def test_holiday_guard_withholds_b_without_asserting_cme_closure():
    registry = load_registry()
    guard = holiday_guard(date(2026, 1, 1), date(2026, 10, 6), registry)
    assert date(2026, 9, 7) in guard  # Labor Day risk window.
    assert date(2026, 9, 14) not in guard
    assert date(2026, 10, 6) not in guard


def test_research_segments_break_at_exclusions_and_long_gaps():
    days = [date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 28),
            date(2026, 9, 29), date(2026, 10, 6)]
    segments = segments_for({days[0], days[1], days[3], days[4]}, days)
    assert segments == {days[0]: 1, days[1]: 1, days[3]: 2, days[4]: 3}


def test_real_history_regressions_and_dataset_isolation():
    if not (OUT / "certification-report.json").exists():
        import pytest
        pytest.skip("Retained licensed history is not present")
    report = json.loads((OUT / "certification-report.json").read_text())
    sessions = {r["trading_date"]: r for r in csv.DictReader((OUT / "certification-by-session.csv").open())}
    old = {r["trading_date"]: r for r in csv.DictReader((OLD / "coverage-by-session.csv").open())}
    assert len(sessions) == len(old) == 4207
    assert report["tier_counts"]["A"] == 11
    assert sessions["2010-06-07"]["tier"] == "D"
    assert sessions["2018-08-05"]["reason_code"] == "D_NONSESSION_PREOPEN_BAR"
    assert sessions["2018-08-06"]["tier"] == "C"
    assert sessions["2026-10-06"]["provider_integrity"] == "REVISED_AVAILABLE"
    assert sessions["2026-10-06"]["tier"] == "A"
    september = [date(2026, 9, 14) + timedelta(days=i) for i in range(12)
                 if (date(2026, 9, 14) + timedelta(days=i)).weekday() < 5]
    assert len(september) == 10 and all(sessions[d.isoformat()]["tier"] == "A" for d in september)
    assert all(sessions[d]["tier"] in ("C", "D") for d in
               ("2014-06-11", "2014-06-16", "2014-09-22", "2025-11-28"))
    strict = pq.read_table(OUT / "strict-certified.parquet", columns=["trading_date", "quality_tier", "research_segment_id"])
    exploratory = pq.read_table(OUT / "exploratory-research.parquet", columns=["trading_date", "quality_tier", "research_segment_id"])
    assert set(strict["quality_tier"].to_pylist()) == {"A"}
    assert set(exploratory["quality_tier"].to_pylist()) == {"A", "B"}
    assert strict.num_rows == report["strict_rows"]
    assert exploratory.num_rows == report["exploratory_rows"]
    assert set(strict["research_segment_id"].to_pylist()) == {1, 2}
    assert set(strict["trading_date"].to_pylist()) == {date.fromisoformat(d) for d in sessions if sessions[d]["tier"] == "A"}
    assert {e["id"] for e in json.loads(EVIDENCE.read_text())["evidence"]} >= \
           {"CME_2012_HOURS", "CME_2015_CLOSE", "CME_2021_PAUSE", "PMC_CME_EQUITY"}
    assert REGISTRY.exists()
