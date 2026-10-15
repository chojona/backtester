"""Regression checks against the frozen research release and certification."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import csv

import pytest

from backtester.nq_research_data import (
    BPV_ESTIMATOR_VERSION, ROOT, SCHEMA_VERSION, W1, PHASE3, SessionObservation,
    consecutive_windows, load_sessions,
)


@pytest.fixture(scope="module")
def strict():
    if not (ROOT / PHASE3 / "strict-certified.parquet").is_file():
        pytest.skip("Local certified Parquet is not present")
    return load_sessions("strict")


@pytest.fixture(scope="module")
def conditional():
    if not (ROOT / W1 / "manifest.json").is_file():
        pytest.skip("Local conditional release is not present")
    return load_sessions("conditional", allow_conditional=True)


def synthetic_session(day, ordinal, *, mode="conditional", contract="NQM22", segment=1):
    end = datetime.combine(day, datetime.min.time(), timezone.utc) + timedelta(hours=21)
    return SessionObservation(
        SCHEMA_VERSION, mode, day, contract, end - timedelta(hours=23), end,
        0.3, 0.1, 0.2, 0.25, 1380, 0, False, True,
        "synthetic_evidence", ("synthetic_assumption",) if mode == "conditional" else (),
        (("synthetic-input.bin", "0" * 64),), "synthetic-method-v1",
        end + timedelta(minutes=45) if mode == "conditional" else None,
        "assumed" if mode == "conditional" else "unknown", ordinal, segment,
        "synthetic_calendar", "B" if mode == "conditional" else "A")


def test_synthetic_eligibility_gaps_and_rolls():
    a = synthetic_session(date(2022, 6, 13), 1)
    b = synthetic_session(date(2022, 6, 14), 2, contract="NQU22")
    c = synthetic_session(date(2022, 6, 16), 4, contract="NQU22")
    assert len(consecutive_windows((a, b, c), 2, conditional_policy="release_chronology")) == 1
    assert consecutive_windows((a, b), 2, conditional_policy="release_chronology")[0].observations == (a, b)
    with pytest.raises(ValueError, match="Mixed eligibility"):
        consecutive_windows((a, synthetic_session(date(2022, 6, 14), 2, mode="strict")), 2)
    with pytest.raises(ValueError, match="conditional_policy"):
        consecutive_windows((a, b), 2)


def test_strict_loader_from_synthetic_sealed_artifacts(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    phase = tmp_path / PHASE3
    phase.mkdir(parents=True)
    bpv = tmp_path / "results/databento-nq-full-history/bpv-segment-v1.0.0"
    bpv.mkdir(parents=True)
    raw = tmp_path / "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"
    raw.write_bytes(b"synthetic source marker")
    day = date(2026, 9, 14)
    start = datetime(2026, 9, 13, 22, tzinfo=timezone.utc)
    bars = [{"trading_date": day, "timestamp_utc": start + timedelta(minutes=i),
             "contract": "NQU26", "quality_tier": "A", "certification_version": "nq-history-v3.0.0",
             "research_segment_id": 1} for i in range(2)]
    pq.write_table(pa.Table.from_pylist(bars), phase / "strict-certified.parquet")
    allow = phase / "strict-certified-allowlist.csv"
    with allow.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["trading_date", "selected_contract", "tier",
            "certification_version", "research_eligibility", "expected_active_minutes",
            "observed_active_minutes", "off_schedule_trade_minutes", "duplicate_selected_minutes",
            "strict_segment_id", "calendar_validity"])
        writer.writeheader()
        writer.writerow({"trading_date": day.isoformat(), "selected_contract": "NQU26", "tier": "A",
            "certification_version": "nq-history-v3.0.0", "research_eligibility": "STRICT_AND_EXPLORATORY",
            "expected_active_minutes": 2, "observed_active_minutes": 2, "off_schedule_trade_minutes": 0,
            "duplicate_selected_minutes": 0, "strict_segment_id": 1, "calendar_validity": "REVIEWED_REGULAR"})
    (phase / "certification-by-session.csv").write_text("synthetic certification register\n")
    measures = bpv / "volatility-by-session.csv"
    with measures.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["trading_date", "contract", "n", "rv",
            "positive_semivariance", "negative_semivariance", "bpv", "bpv_estimator_version"])
        writer.writeheader()
        writer.writerow({"trading_date": day.isoformat(), "contract": "NQU26", "n": 2,
            "rv": 0.3, "positive_semivariance": 0.1, "negative_semivariance": 0.2,
            "bpv": 0.25, "bpv_estimator_version": BPV_ESTIMATOR_VERSION})
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    (phase / "certification-report.json").write_text(json.dumps({
        "version": "nq-history-v3.0.0", "strict_research_dates": 1,
        "source_hashes": {"results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet": digest(raw)},
        "output_hashes": {name: digest(phase / name) for name in
            ("strict-certified.parquet", "strict-certified-allowlist.csv", "certification-by-session.csv")},
    }))
    (bpv / "manifest.json").write_text(json.dumps({"version": BPV_ESTIMATOR_VERSION,
        "source_parquet_sha256": digest(raw), "output_csv_sha256": digest(measures)}))
    sessions = load_sessions("strict", root=tmp_path)
    assert len(sessions) == 1 and sessions[0].availability_status == "unknown"
    assert sessions[0].source_hashes
    assert not consecutive_windows(sessions, 2)


def test_conditional_loader_from_synthetic_release(tmp_path):
    release = tmp_path / W1
    release.mkdir(parents=True)
    source = tmp_path / "source.bin"
    source.write_bytes(b"synthetic conditional source")
    row = {
        "ordinal": 1, "trade_date": "2022-07-05", "active_segments": [{
            "start_utc": "2022-07-03T22:00:00Z", "end_utc": "2022-07-04T17:00:00Z",
            "expected_minutes": 1140, "observed_bars": 1140, "missing_minutes_utc": []}, {
            "start_utc": "2022-07-04T22:00:00Z", "end_utc": "2022-07-05T21:00:00Z",
            "expected_minutes": 1380, "observed_bars": 1380, "missing_minutes_utc": []}],
        "matched_coverage": {"covered_minutes_1m": 2520},
        "minute_counts": {"OBSERVED_TRADE": 2520}, "historical_tier_unchanged": "C",
        "unresolved_electronic_volume": {"contract": "NQH23", "value": None},
        "calendar_evidence_label": "assumed_ordinary_hours_provisional",
        "daily_estimators": {"rv1": 0.3, "rs_positive": 0.1,
                             "rs_negative": 0.2, "bpv": 0.25},
        "selected_contract_for_conditional_path": "NQU22",
        "selector_evidence_label": "assumed_existing_path_unresolved_winner",
    }
    series = release / "daily-series.json"
    series.write_text(json.dumps({"schema_version": "nq-w1-exploratory-v1.0.0", "dates": [row]}))
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = release / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": "nq-w1-exploratory-v1.0.0",
        "decision": "GO_CONDITIONAL_EXPLORATORY_MODEL_DEVELOPMENT",
        "historical_point_in_time_availability_proven": False, "strict_causal_validity": False,
        "date_count": 1, "input_sha256": {"source.bin": digest(source)},
        "output_sha256": {"daily-series.json": digest(series)},
    }))
    (release / "SHA256SUMS").write_text(
        f"{digest(series)}  daily-series.json\n{digest(manifest)}  manifest.json\n")
    with pytest.raises(PermissionError):
        load_sessions("conditional", root=tmp_path)
    sessions = load_sessions("conditional", root=tmp_path, allow_conditional=True)
    assert len(sessions) == 1 and sessions[0].historical_tier == "C"
    assert sessions[0].availability_status == "assumed"
    assert "unresolved_selector_existing_path" in sessions[0].assumption_ids
    assert "provisional_ordinary_hours" in sessions[0].assumption_ids


def test_strict_and_conditional_are_separate(strict, conditional):
    assert len(strict) == 11 and all(r.eligibility == "strict" and r.historical_tier == "A" for r in strict)
    assert len(conditional) == 120 and all(r.eligibility == "conditional" and r.assumption_ids for r in conditional)
    with pytest.raises(PermissionError):
        load_sessions("conditional")
    with pytest.raises(ValueError, match="Mixed eligibility"):
        consecutive_windows((strict[0], conditional[0]), 2)


def test_missing_sessions_break_windows(strict, conditional):
    assert len(consecutive_windows(strict, 2)) == 9
    assert len(consecutive_windows(strict, 11)) == 0
    shortened = conditional[:30] + conditional[31:]
    windows = consecutive_windows(shortened, 2, conditional_policy="release_chronology")
    assert len(windows) == 117
    assert all(w.observations[1].session_ordinal == w.observations[0].session_ordinal + 1 for w in windows)
    with pytest.raises(ValueError, match="conditional_policy"):
        consecutive_windows(conditional, 2)


def test_rolls_do_not_join_returns(conditional):
    june = {r.cme_trade_date: r for r in conditional}
    assert june[date(2022, 6, 13)].selected_contract == "NQM22"
    assert june[date(2022, 6, 14)].selected_contract == "NQU22"
    assert june[date(2022, 9, 12)].selected_contract == "NQU22"
    assert june[date(2022, 9, 13)].selected_contract == "NQZ22"
    assert all(r.methodology_version.endswith("nq-clock-returns-v2.0.0") for r in conditional)


def test_availability_is_not_promoted(strict, conditional):
    assert all(r.availability_status == "unknown" and r.availability_time_utc is None for r in strict)
    assert all(r.availability_status == "assumed" and
               r.availability_time_utc == r.session_end_utc + timedelta(minutes=45) for r in conditional)
    assert all("session_measure_available_45m_after_close" in r.assumption_ids for r in conditional)


def test_calendar_exception_and_lineage(conditional, strict):
    rows = {r.cme_trade_date: r for r in conditional}
    assert date(2022, 7, 4) not in rows
    assert rows[date(2022, 7, 5)].eligible_minute_count == 2520
    assert len([r for r in conditional if "provisional_ordinary_hours" in r.assumption_ids]) == 9
    assert len([r for r in conditional if "unresolved_selector_existing_path" in r.assumption_ids]) == 10
    for r in (strict[0], conditional[0]):
        assert r.schema_version == SCHEMA_VERSION
        assert all(len(digest) == 64 for _, digest in r.source_hashes)
    assert BPV_ESTIMATOR_VERSION in strict[0].methodology_version
    assert any(name.endswith("strict-certified.parquet") for name, _ in strict[0].source_hashes)
    assert any(name.endswith("minute-classifications.csv.gz") for name, _ in conditional[0].source_hashes)


def test_reproducible_windows(conditional):
    first = consecutive_windows(conditional, 23, conditional_policy="release_chronology")
    second = consecutive_windows(conditional, 23, conditional_policy="release_chronology")
    assert first == second and len(first) == 98
    assert first[0].observations[0].cme_trade_date == date(2022, 6, 2)
    assert first[0].observations[-1].cme_trade_date == date(2022, 7, 6)
    assert first[-1].observations[-1].cme_trade_date == date(2022, 11, 21)
    assert all(w.source_hashes for w in first)
    broken = list(conditional)
    broken[1] = replace(broken[1], session_ordinal=1000)
    with pytest.raises(ValueError, match="chronological"):
        consecutive_windows(broken, 23, conditional_policy="release_chronology")
    foreign = list(conditional)
    foreign[1] = replace(foreign[1], source_hashes=(("other-release.json", "0" * 64),))
    with pytest.raises(ValueError, match="Mixed research releases"):
        consecutive_windows(foreign, 2, conditional_policy="release_chronology")


def test_prospective_requires_a_sealed_manifest():
    with pytest.raises(ValueError, match="manifest"):
        load_sessions("prospective")


def test_prospective_observed_availability_and_hashes(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"immutable prospective minute evidence")
    rows = tmp_path / "daily.json"
    rows.write_text(json.dumps([{
        "cme_trade_date": "2026-10-16", "selected_contract": "NQZ26",
        "session_start_utc": "2026-10-15T22:00:00Z", "session_end_utc": "2026-10-16T21:00:00Z",
        "realized_variance": 0.3, "positive_semivariance": 0.1,
        "negative_semivariance": 0.2, "bipower_variation": 0.25,
        "eligible_minute_count": 1380, "missing_minute_count": 0,
        "has_missing_minutes": False, "continuity_ok": True,
        "evidence_classification": "prospective_observed", "assumption_ids": [],
        "availability_time_utc": "2026-10-16T21:00:02Z", "session_ordinal": 1,
        "continuity_segment": 1, "calendar_status": "reviewed", "historical_tier": "A",
    }]))
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION, "eligibility": "prospective",
        "methodology_version": "prospective-clock-v1", "session_count": 1,
        "source_sha256": {"source.bin": digest(source)},
        "observations_file": "daily.json", "observations_sha256": digest(rows),
    }))
    observed = load_sessions("prospective", root=tmp_path, prospective_manifest="manifest.json")
    assert observed[0].availability_status == "observed"
    assert observed[0].availability_time_utc > observed[0].session_end_utc
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed evidence"):
        load_sessions("prospective", root=tmp_path, prospective_manifest="manifest.json")
    source.write_bytes(b"immutable prospective minute evidence")
    escaped = json.loads(manifest.read_text())
    escaped["source_sha256"] = {"../source.bin": digest(source)}
    manifest.write_text(json.dumps(escaped))
    with pytest.raises(ValueError, match="relative to the research root"):
        load_sessions("prospective", root=tmp_path, prospective_manifest="manifest.json")
    with pytest.raises(ValueError, match="inside research root"):
        load_sessions("prospective", root=tmp_path, prospective_manifest=tmp_path.parent / "outside.json")
