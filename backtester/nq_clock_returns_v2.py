"""Versioned, evidence-gated NQ clock returns; independent of production RV.

An active_id identifies uninterrupted price continuity. A research_segment
controls BPV pair eligibility and the origin of nonoverlapping RV5 blocks.
Changing the latter never resets the price reference by itself.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from .data import Bar
from .nq_clock_experiment import GapEvidence, PROVIDER_OBSERVED_NO_TRADE
from .volatility import log_return

VERSION = "nq-clock-returns-v2.0.0"
MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class ClockMinuteV2:
    start: datetime
    contract: str
    active_id: str
    research_segment: str
    bar: Bar | None = None
    evidence: GapEvidence | None = None
    unknown: bool = False


def measure_clock_v2(minutes):
    """Measure a supplied active-minute grid, rejecting unevidenced silence.

    UNKNOWN is explicit and makes canonical full-window measures null. The first
    subsequent observed bar restarts at its own open. Partial RV5 tails are
    omitted; every complete block is anchored to its research segment opening.
    """
    rows = tuple(minutes)
    if not rows:
        raise ValueError("An expected active-minute grid is required")
    returns, prices, sources, pairs, blocks = [], [], [], [], []
    previous = None
    previous_price = None
    previous_return = None
    group = []
    groups = []
    for row in rows:
        if (row.start.tzinfo is None or row.start.utcoffset() != timedelta(0)
                or row.start.second or row.start.microsecond):
            raise ValueError("Expected minutes must be aligned UTC")
        if not row.contract or not row.active_id or not row.research_segment:
            raise ValueError("Contract, active continuity and research segment are required")
        if sum((row.bar is not None, row.evidence is not None, row.unknown)) != 1:
            raise ValueError("Exactly one observed bar, evidenced no-trade, or UNKNOWN is required")
        if previous is not None:
            if row.start <= previous.start:
                raise ValueError("Expected minutes must increase")
            if row.active_id == previous.active_id:
                if row.contract != previous.contract or row.start != previous.start + MINUTE:
                    raise ValueError("An active interval must be contiguous on one contract")
            elif row.start < previous.start + MINUTE:
                raise ValueError("Active intervals overlap")
        same_active = (previous is not None and row.active_id == previous.active_id
                       and row.contract == previous.contract and row.start == previous.start + MINUTE)
        same_research = same_active and row.research_segment == previous.research_segment
        if not same_research and group:
            groups.append(group)
            group = []
        if row.bar is not None:
            bar = row.bar
            if (bar.timestamp != row.start or bar.duration != MINUTE or bar.contract != row.contract
                    or bar.bar_state != "TRADED" or not bar.published or bar.coverage_state == "UNKNOWN"
                    or not all(math.isfinite(p) and p > 0 for p in
                               (bar.open, bar.high, bar.low, bar.close))):
                raise ValueError("Only matching published observed trade bars are accepted")
            reference = previous_price if same_active and previous_price is not None else bar.open
            r = log_return(reference, bar.close)
            price, source = bar.close, "OBSERVED_TRADE"
        elif row.evidence is not None:
            ev = row.evidence
            if (ev.start != row.start or ev.end != row.start + MINUTE or ev.contract != row.contract
                    or ev.classification != PROVIDER_OBSERVED_NO_TRADE or not same_active
                    or previous_price is None):
                raise ValueError("No-trade carry requires matching evidence and a known prior price")
            r, price, source = 0.0, previous_price, PROVIDER_OBSERVED_NO_TRADE
        else:
            r, price, source = None, None, "UNKNOWN"
        if same_research and r is not None and previous_return is not None:
            pairs.append(abs(previous_return * r))
        returns.append(r)
        prices.append(price)
        sources.append(source)
        group.append((row.start, r))
        previous, previous_price, previous_return = row, price, r
    if group:
        groups.append(group)
    for group in groups:
        for offset in range(0, len(group) - 4, 5):
            block = group[offset:offset + 5]
            if all(r is not None for _, r in block):
                blocks.append((block[0][0], math.fsum(r for _, r in block)))
    known = [r for r in returns if r is not None]
    complete = len(known) == len(rows)
    metrics = {
        "rv1": math.fsum(r*r for r in known) if complete else None,
        "rv5": math.fsum(r*r for _, r in blocks) if complete else None,
        "rs_positive": math.fsum(r*r for r in known if r > 0) if complete else None,
        "rs_negative": math.fsum(r*r for r in known if r < 0) if complete else None,
        "bpv": math.pi/2 * math.fsum(pairs) if complete and pairs else None,
        "one_minute_returns": len(known), "five_minute_blocks": len(blocks),
        "bpv_pairs": len(pairs), "no_trade_minutes": sources.count(PROVIDER_OBSERVED_NO_TRADE),
        "unknown_minutes": len(rows) - len(known),
    }
    return {"version": VERSION, "complete": complete, "metrics": metrics,
            "returns": tuple(returns), "prices": tuple(prices), "sources": tuple(sources),
            "rv5_blocks": tuple(blocks)}
