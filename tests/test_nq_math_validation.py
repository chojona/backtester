"""Independent synthetic references for NQ variation and strict HAR plumbing.

Reference arithmetic below deliberately does not call production estimators.
"""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import csv
import math
from pathlib import Path

import pytest

from backtester.nq_research import (
    DailyVariation, build_har_rows, load_strict_nq_parquet, require_strict_sessions,
    validate_strict_metadata,
)
from backtester.data import Bar
from backtester.sessions import SessionCalendar, local_at
from backtester.volatility import (
    RealizedVolatility, bipower_variation, realized_variance, semivariances,
)

VERSION = "nq-history-v3.0.0"


def reference_variations(values):
    """Direct mathematical definitions, independent of production functions."""
    total = up = down = adjacent = 0.0
    for index, value in enumerate(values):
        squared = value ** 2
        total += squared
        if value > 0:
            up += squared
        elif value < 0:
            down += squared
        if index:
            adjacent += abs(value) * abs(values[index - 1])
    return total, up, down, (math.pi / 2) * adjacent if len(values) >= 2 else None


def bars_from_returns(values, start=None):
    start = start or local_at(date(2026, 1, 4), "18:00")
    price = 100.0
    bars = []
    for index, value in enumerate(values):
        close = price * math.exp(value)
        bars.append(Bar(start + timedelta(minutes=index), price, max(price, close),
                        min(price, close), close, 10, "NQH26", "NQ", timedelta(minutes=1)))
        price = close
    return bars


def reference_stream_returns(bars, calendar):
    out = []
    previous = None
    for bar in bars:
        info = calendar.classify(bar.timestamp)
        previous_info = calendar.classify(previous.timestamp) if previous else None
        adjacent = (previous is not None and previous.end == bar.timestamp and
                    previous.contract == bar.contract and
                    previous_info.trading_date == info.trading_date and
                    previous_info.session == info.session and
                    previous.coverage_state != "UNKNOWN")
        if bar.coverage_state == "UNKNOWN":
            out.append(None)
        else:
            source = previous.close if adjacent else bar.open
            out.append(math.log(bar.close / source))
        previous = bar
    return out


def reference_coarse(returns, block_size):
    # The synthetic case begins at a segment opening and covers 30 minutes.
    return sum(sum(returns[i:i + block_size]) ** 2
               for i in range(0, len(returns), block_size))


@pytest.mark.parametrize("values", [
    [0.0] * 30,
    [0.002] * 30,
    [-0.002] * 30,
    [0.003, -0.003] * 15,
    [0.0] * 12 + [0.2] + [0.0] * 17,
    [0.001, -0.002, 0.0, 0.004, -0.001] * 6,
])
def test_scalar_reference_formulas(values):
    expected = reference_variations(values)
    assert realized_variance(values) == pytest.approx(expected[0], abs=1e-15)
    positive, negative = semivariances(values)
    assert positive == pytest.approx(expected[1], abs=1e-15)
    assert negative == pytest.approx(expected[2], abs=1e-15)
    assert bipower_variation(values) == pytest.approx(expected[3], abs=1e-15)
    assert positive + negative == pytest.approx(realized_variance(values), abs=1e-15)


@pytest.mark.parametrize("values", [
    [0.0] * 30, [0.001] * 30, [0.001, -0.001] * 15,
    [0.0] * 14 + [0.1] + [0.0] * 15,
])
def test_stream_reference_and_matched_1_5_15_minute_support(values):
    calendar = SessionCalendar()
    bars = bars_from_returns(values)
    expected_returns = reference_stream_returns(bars, calendar)
    expected = reference_variations(expected_returns)
    stream = RealizedVolatility(calendar)
    record = None
    for bar in bars:
        record = stream.update(bar, as_of=bar.end)
    assert record.prefix_complete
    assert record.covered_minutes_5m == record.covered_minutes_15m == 30
    assert record.rv_1m == pytest.approx(expected[0], abs=1e-14)
    assert record.rs_positive == pytest.approx(expected[1], abs=1e-14)
    assert record.rs_negative == pytest.approx(expected[2], abs=1e-14)
    assert record.bpv == pytest.approx(expected[3], abs=1e-14)
    assert record.rv_5m == pytest.approx(reference_coarse(expected_returns, 5), abs=1e-14)
    assert record.rv_15m == pytest.approx(reference_coarse(expected_returns, 15), abs=1e-14)


def test_frequency_comparison_drops_unmatched_final_minute():
    calendar = SessionCalendar()
    bars = bars_from_returns([0.001] * 30 + [0.02])
    stream = RealizedVolatility(calendar)
    for bar in bars:
        record = stream.update(bar, as_of=bar.end)
    returns = reference_stream_returns(bars, calendar)
    matched = returns[:30]
    assert record.covered_minutes_5m == record.covered_minutes_15m == 30
    assert record.rv_1m == pytest.approx(reference_variations(returns)[0], abs=1e-14)
    assert record.rv_5m == pytest.approx(reference_coarse(matched, 5), abs=1e-14)
    assert record.rv_15m == pytest.approx(reference_coarse(matched, 15), abs=1e-14)
    assert reference_variations(matched)[0] < record.rv_1m


def test_missing_observation_and_unknown_coverage_do_not_become_zeroes():
    calendar = SessionCalendar()
    bars = bars_from_returns([0.01] * 30)
    missing = bars[:7] + bars[8:]
    record = None
    stream = RealizedVolatility(calendar)
    for bar in missing:
        record = stream.update(bar, as_of=bar.end)
    assert record.missing_bars_to_now == 1
    assert all(getattr(record, name) is None for name in
               ("rv_1m", "rv_5m", "rv_15m", "rs_positive", "rs_negative", "bpv"))
    assert record.observed_rv == pytest.approx(reference_variations(reference_stream_returns(missing, calendar))[0])
    unknown = list(bars)
    unknown[7] = replace(unknown[7], coverage_state="UNKNOWN")
    stream = RealizedVolatility(calendar)
    for bar in unknown:
        record = stream.update(bar, as_of=bar.end)
    assert record.unknown_bars == 1 and record.rv_1m is None


def test_segment_boundary_preserves_close_return_but_excludes_bipower_pair():
    calendar = SessionCalendar()
    first = bars_from_returns([0.0] * 929 + [0.01], local_at(date(2026, 1, 4), "18:00"))
    second = bars_from_returns([0.02], local_at(date(2026, 1, 5), "09:30"))
    opening = first[-1].close
    closing = opening * math.exp(0.02)
    second = [replace(second[0], open=opening, high=closing, low=opening, close=closing)]
    stream = RealizedVolatility(calendar)
    for bar in first + second:
        record = stream.update(bar, as_of=bar.end)
    assert record.prefix_complete
    assert record.rv_1m == pytest.approx(0.01 ** 2 + 0.02 ** 2, abs=1e-14)
    assert record.bpv == pytest.approx(0.0, abs=1e-14)


def test_new_session_uses_own_open_and_excludes_overnight_price_gap():
    calendar = SessionCalendar()
    previous = bars_from_returns([0.01], local_at(date(2026, 1, 5), "16:59"))[0]
    current = bars_from_returns([0.02, 0.03], local_at(date(2026, 1, 5), "18:00"))
    current = [replace(b, open=b.open * 10, high=b.high * 10,
                       low=b.low * 10, close=b.close * 10) for b in current]
    stream = RealizedVolatility(calendar)
    stream.update(previous, as_of=previous.end)
    for bar in current:
        record = stream.update(bar, as_of=bar.end)
    assert record.observed_rv == pytest.approx(0.02 ** 2 + 0.03 ** 2, abs=1e-14)
    assert record.bpv == pytest.approx(math.pi / 2 * 0.02 * 0.03, abs=1e-14)


@pytest.mark.parametrize("tier", ["B", "C", "D"])
def test_strict_metadata_rejects_every_uncertified_tier(tier):
    day = date(2026, 9, 14)
    allow = {day: ("NQZ26", "A", VERSION, 1)}
    with pytest.raises(ValueError):
        validate_strict_metadata([(day, "NQZ26", tier, VERSION, 1)], allow,
                                 certification_version=VERSION)
    with pytest.raises(ValueError):
        validate_strict_metadata([(day, "NQZ26", "A", VERSION, 1)],
                                 {day: ("NQZ26", tier, VERSION, 1)},
                                 certification_version=VERSION)


def test_strict_metadata_checks_contract_version_segment_and_empty():
    day = date(2026, 9, 14)
    allow = {day: ("NQZ26", "A", VERSION, 1)}
    good = (day, "NQZ26", "A", VERSION, 1)
    assert validate_strict_metadata([good], allow, certification_version=VERSION) == 1
    for bad in [(), (day, "NQH27", "A", VERSION, 1),
                (day, "NQZ26", "A", "old", 1), (day, "NQZ26", "A", VERSION, 2)]:
        with pytest.raises(ValueError):
            validate_strict_metadata([bad] if bad else [], allow,
                                     certification_version=VERSION)


def test_strict_writer_rejects_non_a_selection_before_reading_source(tmp_path):
    from scripts.certify_nq_history_phase3 import write_research_dataset
    day = date(2026, 9, 14)
    with pytest.raises(ValueError, match="non-Tier A"):
        write_research_dataset(tmp_path / "bad.parquet", {day: "NQZ26"},
                               {day: "B"}, {day: 1}, strict=True)


def test_retained_strict_parquet_matches_tier_a_allowlist_when_present():
    import pyarrow.parquet as pq
    root = Path(__file__).resolve().parents[1]
    phase = root / "results/databento-nq-full-history/phase3-v3.0.0"
    parquet = phase / "strict-certified.parquet"
    csv_path = phase / "strict-certified-allowlist.csv"
    if not parquet.exists() or not csv_path.exists():
        pytest.skip("Retained licensed certification outputs unavailable")
    with csv_path.open() as stream:
        entries = list(csv.DictReader(stream))
    allow = {date.fromisoformat(row["trading_date"]):
             (row["selected_contract"], row["tier"], row["certification_version"],
              int(row["strict_segment_id"])) for row in entries}
    reader = pq.ParquetFile(parquet)
    columns = ["trading_date", "contract", "quality_tier", "certification_version", "research_segment_id"]
    def metadata():
        for batch in reader.iter_batches(batch_size=100_000, columns=columns):
            yield from zip(*(batch.column(i).to_pylist() for i in range(len(columns))))
    assert validate_strict_metadata(metadata(), allow, certification_version=VERSION) == reader.metadata.num_rows


@pytest.mark.parametrize("injected_tier", ["A", "B", "C", "D"])
def test_strict_loader_rejects_injected_uncertified_rows(tmp_path, injected_tier):
    import pyarrow as pa
    import pyarrow.parquet as pq
    day = date(2026, 9, 14)
    parquet = tmp_path / "strict.parquet"
    allowlist = tmp_path / "allowlist.csv"
    table = pa.table({"trading_date": pa.array([day], type=pa.date32()),
                      "contract": ["NQZ26"], "quality_tier": [injected_tier],
                      "certification_version": [VERSION], "research_segment_id": [1]})
    pq.write_table(table, parquet)
    allowlist.write_text("trading_date,selected_contract,tier,certification_version,strict_segment_id\n"
                         f"{day.isoformat()},NQZ26,A,{VERSION},1\n")
    if injected_tier == "A":
        assert load_strict_nq_parquet(parquet, allowlist, certification_version=VERSION).num_rows == 1
    else:
        with pytest.raises(ValueError):
            load_strict_nq_parquet(parquet, allowlist, certification_version=VERSION)


def daily_rows(count=50):
    first = datetime(2026, 1, 1, 22, tzinfo=timezone.utc)
    return [DailyVariation(date(2026, 1, 1) + timedelta(days=i), i,
                           first + timedelta(days=i), float(i + 1), "A", VERSION, 1, True)
            for i in range(count)]


def test_har_1_5_22_windows_and_next_session_target():
    rows = build_har_rows(daily_rows(), certification_version=VERSION)
    assert len(rows) == 28
    first = rows[0]
    assert first["rv_1"] == 22
    assert first["rv_5"] == pytest.approx(sum(range(18, 23)) / 5)
    assert first["rv_22"] == pytest.approx(sum(range(1, 23)) / 22)
    assert first["target_rv"] == 23
    assert first["feature_date"] < first["target_date"]
    assert first["as_of"] < first["target_available_at"]
    altered = daily_rows()
    altered[22] = replace(altered[22], rv=999)
    changed = build_har_rows(altered, certification_version=VERSION)
    assert changed[0]["rv_1"] == first["rv_1"]
    assert changed[0]["target_rv"] == 999
    assert changed[1]["rv_1"] == 999


def test_har_gap_and_segment_break_windows():
    base = daily_rows()
    assert not build_har_rows(base[:22], certification_version=VERSION)
    dropped = base[:24] + base[25:]
    rows = build_har_rows(dropped, certification_version=VERSION)
    assert all(r["target_date"] < base[25].trading_date or r["feature_date"] >= base[46].trading_date for r in rows)
    segmented = [replace(r, research_segment_id=2) if r.session_ordinal >= 25 else r for r in base]
    rows = build_har_rows(segmented, certification_version=VERSION)
    assert all(r["research_segment_id"] == 1 or r["feature_date"] >= base[46].trading_date for r in rows)


def test_har_rejects_non_a_partial_out_of_order_and_future_availability():
    base = daily_rows(24)
    for tier in ("B", "C", "D"):
        with pytest.raises(ValueError):
            build_har_rows(base[:10] + [replace(base[10], quality_tier=tier)] + base[11:],
                           certification_version=VERSION)
    with pytest.raises(ValueError):
        require_strict_sessions(base[:10] + [base[9]] + base[10:], certification_version=VERSION)
    with pytest.raises(ValueError):
        build_har_rows(base[:10] + [replace(base[10], complete=False)] + base[11:],
                       certification_version=VERSION)
    with pytest.raises(ValueError):
        build_har_rows(base[:22] + [replace(base[22], available_at=base[21].available_at)],
                       certification_version=VERSION)
