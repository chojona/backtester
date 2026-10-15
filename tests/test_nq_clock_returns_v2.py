"""Independent regression arithmetic for the versioned NQ clock return rule."""
from datetime import datetime, timedelta, timezone
import math

import pytest

from backtester.data import Bar
from backtester.nq_clock_experiment import GapEvidence, PROVIDER_OBSERVED_NO_TRADE
from backtester.nq_clock_returns_v2 import ClockMinuteV2, VERSION, measure_clock_v2

UTC = timezone.utc
START = datetime(2022, 8, 16, 13, 25, tzinfo=UTC)


def observed(i, opening, close, active="session", research="OVERNIGHT", contract="NQU22"):
    t = START + timedelta(minutes=i)
    bar = Bar(t, opening, max(opening, close), min(opening, close), close, 1, contract, "NQ")
    return ClockMinuteV2(t, contract, active, research, bar=bar)


def evidence(t, contract="NQU22"):
    return GapEvidence(t, t + timedelta(minutes=1), contract, PROVIDER_OBSERVED_NO_TRADE,
                       "a" * 64, "b" * 64, 0, True, True, "synthetic fixture")


def test_contiguous_research_cuts_keep_close_reference_and_split_bpv_rv5():
    # Both cut opens differ from their preceding closes. Fifteen observed bars
    # produce three independently anchored five-minute blocks.
    closes = [99.2, 99.4, 99.6, 99.8, 100,
              102, 103, 104, 105, 106,
              104, 103, 102, 101, 100]
    opens = [99] + closes[:-1]
    opens[5], opens[10] = 101, 105
    labels = ["OVERNIGHT"] * 5 + ["RTH"] * 5 + ["POST_RTH"] * 5
    rows = [observed(i, opens[i], closes[i], research=labels[i]) for i in range(15)]
    result = measure_clock_v2(rows)
    assert result["version"] == VERSION
    returns = [math.log(close / (opens[i] if i == 0 else closes[i-1]))
               for i, close in enumerate(closes)]
    assert result["returns"] == pytest.approx(returns, abs=1e-15)
    assert returns[5] == pytest.approx(math.log(102/100), abs=1e-15)
    assert returns[10] == pytest.approx(math.log(104/106), abs=1e-15)
    assert returns[5] != pytest.approx(math.log(102/101), abs=1e-6)
    assert returns[10] != pytest.approx(math.log(104/105), abs=1e-6)
    expected_rv1 = math.fsum(r*r for r in returns)
    expected_rv5 = math.fsum(x*x for x in (math.log(100/99), math.log(106/100), math.log(100/106)))
    expected_positive = math.fsum(r*r for r in returns if r > 0)
    expected_negative = math.fsum(r*r for r in returns if r < 0)
    pairs = [abs(returns[i-1]*returns[i]) for i in range(1, 15) if labels[i] == labels[i-1]]
    expected_bpv = math.pi/2 * math.fsum(pairs)
    metrics = result["metrics"]
    assert metrics["rv1"] == pytest.approx(expected_rv1, abs=1e-15)
    assert metrics["rv5"] == pytest.approx(expected_rv5, abs=1e-15)
    assert metrics["rs_positive"] == pytest.approx(expected_positive, abs=1e-15)
    assert metrics["rs_negative"] == pytest.approx(expected_negative, abs=1e-15)
    assert metrics["bpv"] == pytest.approx(expected_bpv, abs=1e-15)
    assert metrics["bpv_pairs"] == 12
    assert pairs[4] == pytest.approx(abs(returns[5]*returns[6]), abs=1e-15)
    assert pairs[8] == pytest.approx(abs(returns[10]*returns[11]), abs=1e-15)
    assert [t for t, _ in result["rv5_blocks"]] == [START, START + timedelta(minutes=5),
                                                   START + timedelta(minutes=10)]


def test_true_halt_session_and_contract_changes_reset_from_open():
    rows = [observed(0, 99, 100), observed(1, 100, 101)]
    rows.append(observed(7, 200, 201, active="after-halt", research="OVERNIGHT"))
    rows.append(observed(8, 300, 301, active="after-roll", research="RTH", contract="NQZ22"))
    rows.append(observed(9, 400, 402, active="new-session", research="OVERNIGHT", contract="NQZ22"))
    got = measure_clock_v2(rows)
    assert got["returns"] == pytest.approx((math.log(100/99), math.log(101/100),
                                              math.log(201/200), math.log(301/300),
                                              math.log(402/400)))
    assert got["metrics"]["bpv_pairs"] == 1
    with pytest.raises(ValueError, match="active interval"):
        measure_clock_v2(rows[:2] + [observed(2, 200, 201, contract="NQZ22")])


def test_evidenced_zero_and_unknown_gap_behavior():
    t = START + timedelta(minutes=1)
    rows = [observed(0, 99, 100),
            ClockMinuteV2(t, "NQU22", "session", "OVERNIGHT", evidence=evidence(t)),
            observed(2, 101, 102)]
    got = measure_clock_v2(rows)
    assert got["returns"] == pytest.approx((math.log(100/99), 0, math.log(102/100)))
    assert got["prices"] == (100, 100, 102)
    assert got["metrics"]["no_trade_minutes"] == 1
    assert got["metrics"]["bpv_pairs"] == 2
    unknown = [rows[0], ClockMinuteV2(t, "NQU22", "session", "OVERNIGHT", unknown=True), rows[2]]
    incomplete = measure_clock_v2(unknown)
    assert incomplete["returns"][1] is None
    assert incomplete["returns"][2] == pytest.approx(math.log(102/101))
    assert all(incomplete["metrics"][name] is None for name in
               ("rv1", "rv5", "rs_positive", "rs_negative", "bpv"))
    with pytest.raises(ValueError, match="matching evidence"):
        measure_clock_v2([rows[0], ClockMinuteV2(t, "NQU22", "session", "OVERNIGHT",
                                                   evidence=evidence(t, "NQZ22"))])
    with pytest.raises(ValueError, match="Exactly one"):
        measure_clock_v2([rows[0], ClockMinuteV2(t, "NQU22", "session", "OVERNIGHT")])
