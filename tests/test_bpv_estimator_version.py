"""Historical and streaming BPV must use the same segment boundary rule."""
import math
from datetime import date, timedelta

import pytest

from backtester.data import Bar
from backtester.sessions import SessionCalendar, local_at
from backtester.volatility import (
    BPV_ESTIMATOR_VERSION, RealizedVolatility, segmented_bipower_variation,
)
from scripts.version_nq_bpv import segment


def test_versioned_bpv_excludes_both_segment_boundary_pairs():
    assert BPV_ESTIMATOR_VERSION == "bpv-segment-v1.0.0"
    returns = [0.01, 0.02, -0.03, 0.04, -0.05, 0.06]
    labels = ["OVERNIGHT"] * 2 + ["RTH"] * 2 + ["POST_RTH"] * 2
    expected = math.pi / 2 * (0.01 * 0.02 + 0.03 * 0.04 + 0.05 * 0.06)
    assert segmented_bipower_variation(returns, labels) == pytest.approx(expected)
    assert segmented_bipower_variation(returns[:3], labels[:3]) == pytest.approx(math.pi / 2 * 0.0002)
    with pytest.raises(ValueError, match="label"):
        segmented_bipower_variation(returns, labels[:-1])


def test_historical_segment_labels_agree_with_streaming_at_boundaries():
    day = date(2026, 9, 14)
    calendar = SessionCalendar(breaks=[])
    samples = [
        local_at(day, "09:28"), local_at(day, "09:29"),
        local_at(day, "09:30"), local_at(day, "09:31"),
        local_at(day, "15:59"), local_at(day, "16:00"),
        local_at(day, "16:01"),
    ]
    for stamp in samples:
        assert segment(stamp) == calendar.classify(stamp).session
    # The complete session exercises the production streaming accumulator.
    stamp = local_at(day - timedelta(days=1), "18:00")
    end = local_at(day, "17:00")
    price = 100.0
    returns, labels = [], []
    stream = RealizedVolatility(calendar)
    while stamp < end:
        change = 0.0001
        close = price * math.exp(change)
        bar = Bar(stamp, price, close, price, close, 10, "NQU26", "NQ")
        result = stream.update(bar, as_of=bar.end)
        returns.append(math.log(close / price))
        labels.append(segment(stamp))
        price = close
        stamp += timedelta(minutes=1)
    assert result.session_complete
    assert result.bpv == pytest.approx(segmented_bipower_variation(returns, labels), abs=1e-14)
