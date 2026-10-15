"""Independent numerical and adversarial checks for the research preflight."""
from datetime import date, datetime, timedelta, timezone
import math
import random

import pytest

from backtester.data import Bar, validate
from backtester.features import VWAP, FeatureEngine
from backtester.execution import ExecutionCosts, FillModel, Order, OrderRequest, Side
from backtester.instruments import instrument
from backtester.portfolio import Portfolio
from backtester.risk import risk_per_contract
from backtester.sessions import SessionCalendar
from backtester.volatility import (
    RealizedVolatility, bipower_variation, log_return, realized_variance,
    semivariances,
)
from backtester.volatility_charts import aggregate_ohlcv


def bar(stamp, opening, closing, volume=1):
    return Bar(stamp, opening, max(opening, closing), min(opening, closing),
               closing, volume, "NQH26", "NQ")


def test_hand_calculated_variation_and_vwap():
    returns = [0.01, -0.02, 0.03]
    assert log_return(100, 100 * math.exp(0.01)) == pytest.approx(0.01)
    assert realized_variance(returns) == pytest.approx(0.0014)
    assert semivariances(returns) == pytest.approx((0.001, 0.0004))
    assert bipower_variation(returns) == pytest.approx(math.pi / 2 * 0.0008)
    start = datetime(2026, 1, 4, 23, tzinfo=timezone.utc)
    first = Bar(start, 100, 104, 98, 102, 2, "NQH26", "NQ")
    second = Bar(start + timedelta(minutes=1), 102, 108, 100, 106, 3, "NQH26", "NQ")
    vwap = VWAP("typical")
    vwap.update(first)
    assert vwap.update(second) == pytest.approx((((104 + 98 + 102) / 3) * 2 +
                                                 ((108 + 100 + 106) / 3) * 3) / 5)


def test_seeded_variation_properties():
    rng = random.Random(20261014)
    for _ in range(500):
        returns = [rng.uniform(-0.05, 0.05) for _ in range(rng.randrange(2, 60))]
        rv = realized_variance(returns)
        positive, negative = semivariances(returns)
        assert rv == pytest.approx(positive + negative, abs=1e-15)
        assert bipower_variation(returns) == pytest.approx(
            math.pi / 2 * sum(abs(returns[i] * returns[i - 1])
                              for i in range(1, len(returns))))
        assert realized_variance([-r for r in returns]) == pytest.approx(rv)


def test_atr_true_range_hand_calculation():
    calendar = SessionCalendar(breaks=[])
    features = FeatureEngine(calendar, atr_period=2)
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    first = Bar(start, 100, 102, 99, 101, 1, "NQH26", "NQ")
    second = Bar(start + timedelta(minutes=1), 101, 105, 100, 104, 1, "NQH26", "NQ")
    assert features.update(first)["ATR"] is None
    assert features.update(second)["ATR"] == pytest.approx((3 + 5) / 2)


def test_aggregation_rejects_missing_minute_and_preserves_ohlcv():
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    bars = [bar(start + timedelta(minutes=i), 100 + i, 101 + i, i + 1)
            for i in range(5)]
    points = [dict(bar=b, segment_open=start) for b in bars]
    result = aggregate_ohlcv(points, 5)
    assert result == [[int(start.timestamp() * 1000), 100, 105, 100, 105, 15]]
    assert aggregate_ohlcv(points[:2] + points[3:], 5) == []


def test_validation_rejects_duplicate_order_and_bad_time():
    calendar = SessionCalendar(breaks=[])
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    first, second = bar(start, 100, 101), bar(start + timedelta(minutes=1), 101, 102)
    with pytest.raises(ValueError, match="Duplicate"):
        validate([first, first], calendar)
    with pytest.raises(ValueError, match="Out-of-order"):
        validate([second, first], calendar)
    with pytest.raises(ValueError, match="aligned"):
        validate([bar(start + timedelta(seconds=30), 100, 101)], calendar)


def test_total_bpv_excludes_rth_boundary_pair_per_documented_convention():
    calendar = SessionCalendar(breaks=[])
    opened = calendar.bounds(date(2026, 1, 5))[0]
    measure = RealizedVolatility(calendar)
    price = 100.0
    final = None
    for minute in range(931):  # Sunday 18:00 ET through Monday 09:30 ET.
        stamp = opened + timedelta(minutes=minute)
        next_price = price * math.exp(0.001)
        item = bar(stamp, price, next_price)
        final = measure.update(item, as_of=item.end)
        price = next_price
    assert final.segment == "RTH" and final.prefix_complete
    assert final.rv_1m == pytest.approx(931 * 0.001**2)
    assert final.bpv == pytest.approx(math.pi / 2 * 929 * 0.001**2)


def test_two_contract_nq_round_trip_accounting():
    nq = instrument("NQ")
    costs = ExecutionCosts(commission=2, exchange_fee=1, slippage_ticks=1)
    model = FillModel(nq, costs)
    portfolio = Portfolio(nq, cash=100000)
    calendar = SessionCalendar(breaks=[])
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    entry_bar = bar(start, 100, 100)
    entry_request = OrderRequest(Side.BUY, 2, stop_loss=95)
    entry = model.fill(Order(1, start, date(2026, 1, 5), "NQH26", entry_request),
                       entry_bar, 2)
    assert entry.price == 100.25 and entry.fees == 6 and entry.slippage == 10
    portfolio.open(entry, entry_request, calendar.classify(start), 2 * risk_per_contract(100.25, 95, nq, costs))
    exit_stamp = start + timedelta(minutes=1)
    exit_bar = bar(exit_stamp, 102, 102)
    exit_request = OrderRequest(Side.SELL, 2, reduce_only=True)
    exit_fill = model.fill(Order(2, exit_stamp, date(2026, 1, 5), "NQH26", exit_request),
                           exit_bar, 2)
    trade = portfolio.close(exit_fill, "audit", "manual")
    assert exit_fill.price == 101.75 and exit_fill.fees == 6 and exit_fill.slippage == 10
    assert trade["gross_pnl"] == 80
    assert trade["fees"] == 12 and trade["slippage"] == 20
    assert trade["net_pnl"] == 48 and portfolio.balance == 100048


def test_missing_prefix_and_future_bar_are_censored():
    calendar = SessionCalendar(breaks=[])
    opened = calendar.bounds(date(2026, 1, 5))[0]
    first = bar(opened, 100, 101)
    third = bar(opened + timedelta(minutes=2), 101, 102)
    measure = RealizedVolatility(calendar)
    with pytest.raises(ValueError, match="not yet complete"):
        measure.update(first, as_of=first.timestamp)
    measure.update(first, as_of=first.end)
    result = measure.update(third, as_of=third.end)
    assert result.missing_bars_to_now == 1
    assert not result.prefix_complete and result.rv_1m is None
    with pytest.raises(ValueError, match="chronological"):
        measure.update(first, as_of=third.end)


def test_dst_session_open_uses_new_york_offset():
    calendar = SessionCalendar(breaks=[])
    before = calendar.bounds(date(2026, 3, 6))[0]
    after = calendar.bounds(date(2026, 3, 9))[0]
    assert before.hour == 23 and after.hour == 22
    assert calendar.valid_bar(after, timedelta(minutes=1))
