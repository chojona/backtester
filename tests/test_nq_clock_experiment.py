"""Independent arithmetic and boundary checks for the isolated NQ clock experiment."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math

import pytest

from backtester.data import Bar
from backtester.nq_clock_experiment import (
    ClockMinute, GapEvidence, PROVIDER_OBSERVED_NO_TRADE,
    experimental_clock_rv, sample_clock_prices,
)
from backtester.sessions import SessionCalendar
from backtester.volatility import RealizedVolatility

UTC = timezone.utc
START = datetime(2022, 2, 16, 4, 40, tzinfo=UTC)
CLOSES = [14558.0, 14555.25, 14555.25, 14557.5, 14557.25,
          14557.75, 14558.25, None, 14557.25, 14559.0]
OPENS = [14557.25, 14557.5, 14555.25, 14556.0, 14557.25,
         14558.0, 14558.75, None, 14558.75, 14558.25]
VOLUMES = [10, 10, 1, 8, 24, 5, 26, None, 10, 13]


def evidence(start=START + timedelta(minutes=7), contract="NQH22"):
    return GapEvidence(
        start, start + timedelta(minutes=1), contract, PROVIDER_OBSERVED_NO_TRADE,
        "b351972c9a66d514b97d6b944d90c783cdc770268078e18850a1b3d3059e805b",
        "d26aadc23c4ce02c5ed49574a1aa62f80fee2980581d6c3be0556e3de2c250c0",
        0, True, True, "gap-investigation-20261014T194238Z/manifest.json")


def fixture_rows():
    rows = []
    for i, close in enumerate(CLOSES):
        stamp = START + timedelta(minutes=i)
        if close is None:
            rows.append(ClockMinute(stamp, "NQH22", "2022-02-16/overnight", evidence=evidence()))
        else:
            opening = OPENS[i]
            bar = Bar(stamp, opening, max(opening, close), min(opening, close),
                      close, VOLUMES[i], "NQH22", "NQ")
            rows.append(ClockMinute(stamp, "NQH22", "2022-02-16/overnight", bar=bar))
    return rows


def test_actual_gap_independent_rv_and_no_artificial_activity():
    rows = fixture_rows()
    samples = sample_clock_prices(rows)
    assert samples[7].source == PROVIDER_OBSERVED_NO_TRADE
    assert samples[7].price == CLOSES[6]
    assert sum(row.bar.volume for row in rows if row.bar) == sum(v for v in VOLUMES if v is not None) == 107
    assert sum(row.bar is not None for row in rows) == 9
    assert len([row.bar for row in rows if row.bar]) == 9
    prices = [CLOSES[0], CLOSES[1], CLOSES[2], CLOSES[3], CLOSES[4],
              CLOSES[5], CLOSES[6], CLOSES[6], CLOSES[8], CLOSES[9]]
    prior = OPENS[0]
    reference_1m = 0.0
    for price in prices:
        reference_1m += math.log(price / prior) ** 2
        prior = price
    reference_5m = math.log(prices[4] / OPENS[0]) ** 2 + math.log(prices[9] / prices[4]) ** 2
    got_1m = experimental_clock_rv(rows, block_minutes=1)
    got_5m = experimental_clock_rv(rows, block_minutes=5)
    assert got_1m["rv"] == pytest.approx(reference_1m, abs=1e-18)
    assert got_5m["rv"] == pytest.approx(reference_5m, abs=1e-18)
    assert got_1m["returns"] == 10 and got_5m["returns"] == 2

    incumbent = RealizedVolatility(SessionCalendar())
    record = None
    for row in rows:
        if row.bar:
            record = incumbent.update(row.bar, as_of=row.bar.end)
    assert not record.prefix_complete
    assert record.rv_1m is None and record.rv_5m is None


def test_unknown_gap_and_bad_evidence_rejected():
    rows = fixture_rows()
    with pytest.raises(ValueError):
        sample_clock_prices(rows[:7] + [replace(rows[7], evidence=None)] + rows[8:])
    with pytest.raises(ValueError):
        sample_clock_prices(rows[:7] + rows[8:])  # omitted minute cannot disappear from the grid
    for change in ({"trade_records": 1}, {"trading_enabled": False},
                   {"response_complete": False}):
        with pytest.raises(ValueError):
            replace(evidence(), **change)
    with pytest.raises(ValueError):
        sample_clock_prices(rows[:7] + [replace(rows[7], evidence=replace(evidence(), contract="NQM22"))] + rows[8:])
    with pytest.raises(ValueError):
        sample_clock_prices(rows[7:])  # no previous observed price


def test_contract_session_break_and_maintenance_reset():
    rows = fixture_rows()
    with pytest.raises(ValueError):
        sample_clock_prices(rows[:5] + [replace(rows[5], contract="NQM22")])
    with pytest.raises(ValueError):
        sample_clock_prices(rows[:5] + [replace(rows[5], start=rows[5].start + timedelta(minutes=2))])
    # A new uninterrupted segment starts from its own first bar open.
    next_bar = Bar(START + timedelta(hours=2), 20000, 20001, 20000, 20001, 1, "NQM22", "NQ")
    next_row = ClockMinute(next_bar.timestamp, "NQM22", "next-session", bar=next_bar)
    result = experimental_clock_rv(rows + [next_row], block_minutes=1)
    assert result["rv"] == pytest.approx(
        experimental_clock_rv(rows, block_minutes=1)["rv"] + math.log(20001 / 20000) ** 2)
    # Same contract after a maintenance break also needs a new segment.
    after_break = replace(next_row, contract="NQH22", segment="after-maintenance",
                          bar=replace(next_bar, contract="NQH22"))
    assert sample_clock_prices(rows + [after_break])[-1].source == "OBSERVED_TRADE"
    with pytest.raises(ValueError):
        experimental_clock_rv(rows + [next_row], block_minutes=5)
