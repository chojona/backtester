"""Isolated, evidence-gated clock-time NQ sampling experiment.

This module does not create bars or alter the production variance estimator.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from .data import Bar
from .volatility import log_return

MINUTE = timedelta(minutes=1)
PROVIDER_OBSERVED_NO_TRADE = "PROVIDER_OBSERVED_NO_TRADE"


@dataclass(frozen=True)
class GapEvidence:
    start: datetime
    end: datetime
    contract: str
    classification: str
    trade_response_sha256: str
    status_response_sha256: str
    trade_records: int
    trading_enabled: bool
    response_complete: bool
    source: str

    def __post_init__(self):
        if self.classification != PROVIDER_OBSERVED_NO_TRADE:
            raise ValueError("Unsupported gap classification")
        if self.start.tzinfo is None or self.end.tzinfo is None or self.end - self.start != MINUTE:
            raise ValueError("Evidence must bound exactly one aware minute")
        if not self.contract or not self.source or any(
            len(h) != 64 or any(c not in "0123456789abcdef" for c in h)
            for h in (self.trade_response_sha256, self.status_response_sha256)
        ):
            raise ValueError("Evidence requires source and SHA-256 response hashes")
        if self.trade_records != 0 or self.trading_enabled is not True or self.response_complete is not True:
            raise ValueError("No-trade evidence requires complete zero-trade and active-status responses")


@dataclass(frozen=True)
class ClockMinute:
    start: datetime
    contract: str
    segment: str  # explicit uninterrupted session/maintenance segment identifier
    bar: Bar | None = None
    evidence: GapEvidence | None = None


@dataclass(frozen=True)
class PriceSample:
    start: datetime
    contract: str
    segment: str
    price: float
    source: str  # OBSERVED_TRADE or PROVIDER_OBSERVED_NO_TRADE


def sample_clock_prices(minutes):
    """Sample minute-end prices; refuse any unresolved scheduled minute.

    The caller supplies the expected active-minute grid, including empty minutes.
    A new segment explicitly resets the price reference across a break or session.
    """
    rows = tuple(minutes)
    if not rows:
        raise ValueError("An expected minute grid is required")
    samples = []
    previous = None
    previous_bar = None
    for row in rows:
        if row.start.tzinfo is None or row.start.utcoffset() != timedelta(0) or row.start.second or row.start.microsecond:
            raise ValueError("Expected minutes must be UTC-aligned")
        if not row.contract or not row.segment:
            raise ValueError("Contract and uninterrupted segment are required")
        if previous is not None:
            if row.start <= previous.start:
                raise ValueError("Expected minutes must increase strictly")
            if row.segment == previous.segment:
                if row.contract != previous.contract or row.start - previous.start != MINUTE:
                    raise ValueError("Contract changes and time gaps require an explicit segment reset")
            elif row.start - previous.start < MINUTE:
                raise ValueError("Segments may not overlap")
        if (row.bar is None) == (row.evidence is None):
            raise ValueError("Each minute needs exactly one observed bar or gap evidence")
        if row.bar is not None:
            bar = row.bar
            if (bar.timestamp != row.start or bar.duration != MINUTE or bar.contract != row.contract
                    or bar.bar_state != "TRADED" or not bar.published or bar.coverage_state == "UNKNOWN"):
                raise ValueError("Only matching published, observed one-minute trade bars are accepted")
            if not all(math.isfinite(p) and p > 0 for p in (bar.open, bar.high, bar.low, bar.close)):
                raise ValueError("Prices must be positive and finite")
            sample = PriceSample(row.start, row.contract, row.segment, bar.close, "OBSERVED_TRADE")
            previous_bar = bar
        else:
            evidence = row.evidence
            if (evidence.start != row.start or evidence.end != row.start + MINUTE
                    or evidence.contract != row.contract or previous is None
                    or previous.segment != row.segment or previous.contract != row.contract
                    or previous.start + MINUTE != row.start or previous_bar is None):
                raise ValueError("No-trade carry requires matching evidence and a prior observed trade in this segment")
            sample = PriceSample(row.start, row.contract, row.segment, samples[-1].price,
                                 PROVIDER_OBSERVED_NO_TRADE)
        samples.append(sample)
        previous = row
    return tuple(samples)


def experimental_clock_rv(minutes, *, block_minutes):
    """Unannualized log RV over complete, nonoverlapping clock blocks.

    The first return in each segment uses its first observed bar open. A segment
    with a terminal partial block is reported as partial and never silently used.
    """
    if block_minutes not in (1, 5):
        raise ValueError("This experiment supports 1- and 5-minute blocks")
    rows = tuple(minutes)
    samples = sample_clock_prices(rows)
    groups = []
    group = []
    for row, sample in zip(rows, samples):
        if group and (row.segment, row.contract) != (group[-1][0].segment, group[-1][0].contract):
            groups.append(group)
            group = []
        group.append((row, sample))
    groups.append(group)
    squared = []
    for group in groups:
        prior = group[0][0].bar.open
        for offset in range(0, len(group), block_minutes):
            block = group[offset:offset + block_minutes]
            if len(block) != block_minutes:
                raise ValueError("Incomplete terminal clock block")
            end = block[-1][1].price
            squared.append(log_return(prior, end) ** 2)
            prior = end
    return {"label": "EXPERIMENTAL_EVIDENCED_CLOCK_RV", "block_minutes": block_minutes,
            "rv": math.fsum(squared), "returns": len(squared), "samples": samples}
