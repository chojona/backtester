"""Independent checks of the retained bars and non-certifying W1 candidate."""
import hashlib
import json
import math
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq
import pytest


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "calendars/nq-2022-holiday-candidate-v1.json").read_text())
ROWS = {r["trade_date"]: r for r in DATA["trade_dates"]}
PARQUET = ROOT / "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"
HOLIDAYS = [("2022-06-21", "2022-06-20"), ("2022-07-05", "2022-07-04"),
            ("2022-09-06", "2022-09-05")]


def raw_dates(*days):
    table = pq.read_table(PARQUET, columns=["trading_date", "timestamp_utc", "contract", "open", "close", "volume"],
                          filters=[("trading_date", ">=", min(date.fromisoformat(x) for x in days)),
                                   ("trading_date", "<=", max(date.fromisoformat(x) for x in days))])
    return [dict(zip(table.column_names, values)) for values in zip(*(table[c].to_pylist() for c in table.column_names))]


def reference_variation(bars):
    bars = sorted(bars, key=lambda x: x["timestamp_utc"])
    assert all(b["timestamp_utc"] - a["timestamp_utc"] == timedelta(minutes=1)
               for a, b in zip(bars, bars[1:]))
    returns = [math.log(bars[0]["close"] / bars[0]["open"])]
    returns += [math.log(b["close"] / a["close"]) for a, b in zip(bars, bars[1:])]
    coarse = [math.fsum(returns[i:i+5]) for i in range(0, len(returns), 5)]
    def session(stamp):
        local = stamp.astimezone(ZoneInfo("America/New_York")).time()
        return "OVERNIGHT" if local < time(9, 30) or local >= time(18) else (
            "RTH" if local < time(16) else "POST_RTH")
    pairs = [abs(returns[i-1]*returns[i]) for i in range(1, len(returns))
             if session(bars[i-1]["timestamp_utc"]) == session(bars[i]["timestamp_utc"])]
    return (math.fsum(x*x for x in returns),
            math.pi/2 * math.fsum(pairs),
            math.fsum(x*x for x in coarse))


def test_workbook_identity_and_trade_date_calendar():
    assert len(DATA["trade_dates"]) == 117
    assert len({r["trade_date"] for r in DATA["trade_dates"]}) == 117
    for tuesday, monday in HOLIDAYS:
        source = DATA["cme_workbooks"][tuesday]
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]
        assert monday not in ROWS
        row = ROWS[tuesday]
        assert row["expected_minutes"] == 2520
        assert [s["expected_minutes"] for s in row["segments"]] == [1140, 1380]
        first, second = row["segments"]
        assert datetime.fromisoformat(second["start_utc"]) - datetime.fromisoformat(first["end_utc"]) == timedelta(hours=5)
        assert row["nontrading_halt_preopen_utc"] == {"start": first["end_utc"], "end": second["start_utc"]}
        assert row["coverage_complete_against_candidate_grid"] and row["off_grid_selected_bars"] == 0


@pytest.mark.parametrize("tuesday,monday", HOLIDAYS)
def test_raw_bars_independent_segment_rv_bpv_and_five_minute(tuesday, monday):
    row = ROWS[tuesday]
    bars = [b for b in raw_dates(monday, tuesday) if b["contract"] == row["selected_contract"]]
    assert len(bars) == 2520
    references = []
    for segment in row["segments"]:
        start, end = (datetime.fromisoformat(segment[k]) for k in ("start_utc", "end_utc"))
        part = [b for b in bars if start <= b["timestamp_utc"] < end]
        assert len(part) == segment["expected_minutes"]
        assert {b["trading_date"].isoformat() for b in part} == ({monday} if len(part) == 1140 else {tuesday})
        rv, bpv, rv5 = reference_variation(part)
        references.append((rv, bpv))
        assert segment["rv_1m"] == pytest.approx(rv, rel=1e-12)
        assert segment["bpv_within_segment"] == pytest.approx(bpv, rel=1e-12)
        assert segment["rv_5m_segment_anchored"] == pytest.approx(rv5, rel=1e-12)
        assert segment["five_minute_complete_blocks"] == len(part)//5
    assert row["combined_rv_1m"] == pytest.approx(math.fsum(x[0] for x in references), rel=1e-12)
    assert row["combined_bpv_no_cross_halt_pair"] == pytest.approx(math.fsum(x[1] for x in references), rel=1e-12)


@pytest.mark.parametrize("tuesday,monday", HOLIDAYS)
def test_holiday_and_following_day_roll_use_only_completed_volume(tuesday, monday):
    holiday = ROWS[tuesday]
    following = next(r for r in DATA["trade_dates"] if r["predecessor_trade_date"] == tuesday)
    previous = holiday["predecessor_trade_date"]
    bars = raw_dates(previous, monday, tuesday)
    def volume(label):
        result = {}
        for b in bars:
            if b["trading_date"].isoformat() == label:
                result[b["contract"]] = result.get(b["contract"], 0) + b["volume"]
        return result
    friday, monday_volume, tuesday_volume = map(volume, (previous, monday, tuesday))
    combined = {c: monday_volume.get(c, 0) + tuesday_volume.get(c, 0)
                for c in monday_volume.keys() | tuesday_volume.keys()}
    assert holiday["selected_contract"] == max(
        [x["contract"] for x in holiday["candidate_volume_rank"]], key=lambda c: (friday.get(c, 0), c))
    assert following["selected_contract"] == max(
        [x["contract"] for x in following["candidate_volume_rank"]], key=lambda c: (combined.get(c, 0), c))
    assert holiday["selected_contract"] == holiday["historical_selected_contract"]
    assert following["selected_contract"] == following["historical_selected_contract"]


def test_corrected_har_index_and_availability():
    rows = DATA["trade_dates"]
    assert not any(r["winner_changed"] for r in rows)
    index = {r["trade_date"]: i for i, r in enumerate(rows)}
    for tuesday, monday in HOLIDAYS:
        i = index[tuesday]
        assert rows[i-1]["trade_date"] == ROWS[tuesday]["predecessor_trade_date"]
        assert rows[i+1]["predecessor_trade_date"] == tuesday
        assert monday not in index
        # At Tuesday close, 1/5/22 features include Tuesday once; Wednesday is target.
        if i < 21:
            assert len(rows[max(0, i-21):i+1]) < 22
            continue
        features = rows[i-21:i+1]
        assert len(features) == 22
        assert features[-1]["trade_date"] == tuesday
        assert features[-5:] == rows[i-4:i+1]
        assert rows[i+1]["trade_date"] > features[-1]["trade_date"]
        origin = datetime.fromisoformat(features[-1]["segments"][-1]["end_utc"])
        target_available = datetime.fromisoformat(rows[i+1]["segments"][-1]["end_utc"])
        assert all(datetime.fromisoformat(r["segments"][-1]["end_utc"]) <= origin for r in features)
        assert origin < target_available
