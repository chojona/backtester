from datetime import date

import pytest

from backtester.nq_historical_calendar import ordinary_nq_trade_date
from backtester.sessions import local_at


def test_pre2012_next_trade_date_and_pause_boundaries():
    monday = date(2012, 11, 12)
    assert ordinary_nq_trade_date(local_at(monday, "16:14")) == monday
    assert ordinary_nq_trade_date(local_at(monday, "16:15")) is None
    assert ordinary_nq_trade_date(local_at(monday, "16:29")) is None
    assert ordinary_nq_trade_date(local_at(monday, "16:30")) == date(2012, 11, 13)
    assert ordinary_nq_trade_date(local_at(monday, "17:29")) == date(2012, 11, 13)
    assert ordinary_nq_trade_date(local_at(monday, "17:30")) is None
    assert ordinary_nq_trade_date(local_at(monday, "18:00")) == date(2012, 11, 13)


def test_friday_weekend_and_transition():
    assert ordinary_nq_trade_date(local_at(date(2012, 11, 16), "16:15")) is None
    assert ordinary_nq_trade_date(local_at(date(2012, 11, 18), "17:59")) is None
    assert ordinary_nq_trade_date(local_at(date(2012, 11, 18), "18:00")) == date(2012, 11, 19)
    with pytest.raises(ValueError, match="Pre-2012"):
        ordinary_nq_trade_date(local_at(date(2012, 11, 19), "09:30"))
