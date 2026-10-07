"""Immutable intraday bars and provider-independent validated CSV ingestion."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import math
from .instruments import contract_root, instrument


@dataclass(frozen=True)
class Bar:
    timestamp: datetime                 # bar OPEN timestamp, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    contract: str
    symbol: str
    duration: timedelta = timedelta(minutes=1)
    trade_count: object = None
    bid_volume: object = None
    ask_volume: object = None
    open_interest: object = None
    bar_state: str = "TRADED"
    coverage_state: str = "UNVERIFIED"
    provider: object = None
    dataset: object = None
    schema: object = None
    instrument_id: object = None
    raw_symbol: object = None
    source_ts_event_ns: object = None
    request_id: object = None
    coverage_evidence: object = None
    published: bool = True
    open_interest_available_at: object = None
    open_interest_state: object = None

    @property
    def end(self):
        return self.timestamp + self.duration

    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            raise ValueError("Timestamp must include a UTC offset; naive timestamps are rejected")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(timezone.utc))
        if self.duration.total_seconds() <= 0:
            raise ValueError("Bar duration must be positive")
        values = (self.open, self.high, self.low, self.close, self.volume)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("OHLCV must be finite")
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close, self.high):
            raise ValueError("Impossible OHLC")
        if self.volume < 0:
            raise ValueError("Negative volume")
        for name in ("trade_count", "bid_volume", "ask_volume", "open_interest"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("Invalid " + name)
        if contract_root(self.contract) != self.symbol:
            raise ValueError("Contract root does not match instrument")
        instrument(self.symbol)
        if self.bar_state not in ("TRADED", "NO_TRADE") or self.coverage_state not in ("UNVERIFIED", "PROVIDER_AVAILABLE", "UNKNOWN"):
            raise ValueError("Invalid bar/coverage state")
        if self.bar_state == "NO_TRADE":
            if self.volume != 0 or len({self.open, self.high, self.low, self.close}) != 1 or self.published or self.coverage_state != "PROVIDER_AVAILABLE":
                raise ValueError("NO_TRADE requires zero volume, flat known price, available coverage and unpublished provenance")
        if self.open_interest_available_at is not None:
            if self.open_interest_available_at.tzinfo is None or self.open_interest_available_at > self.timestamp:
                raise ValueError("Open interest is not yet available at this bar")


@dataclass
class IntegrityReport:
    rows: int = 0
    contracts: list = field(default_factory=list)
    missing_intervals: list = field(default_factory=list)
    off_tick_prices: int = 0
    warnings: list = field(default_factory=list)


class DataProvider(ABC):
    @abstractmethod
    def load(self):
        """Return (immutable chronological bars, integrity report)."""


def validate(bars, calendar):
    if not bars:
        raise ValueError("No bars")
    report = IntegrityReport(rows=len(bars), contracts=sorted({b.contract for b in bars}))
    previous_global, previous_contract = None, {}
    for bar in bars:
        if previous_global and bar.timestamp < previous_global:
            raise ValueError("Out-of-order timestamps")
        previous_global = bar.timestamp
        last = previous_contract.get(bar.contract)
        if last and bar.timestamp < last.end:
            raise ValueError("Duplicate or overlapping bars for " + bar.contract)
        if abs(bar.timestamp.timestamp() % bar.duration.total_seconds()) > 1e-8:
            raise ValueError("Timestamp not aligned to the configured bar interval")
        if not calendar.valid_bar(bar.timestamp, bar.duration):
            raise ValueError("Bar crosses a session boundary or occurs outside trading hours: " + bar.timestamp.isoformat())
        if last and bar.duration != last.duration:
            raise ValueError("Mixed intervals for " + bar.contract)
        if last:
            missing, first = 0, None
            probe = last.end
            while probe < bar.timestamp:
                if calendar.valid_bar(probe, bar.duration):
                    first = first or probe
                    missing += 1
                probe += bar.duration
            if probe != bar.timestamp:
                raise ValueError("Bars are not aligned to the configured interval")
            if missing:
                report.missing_intervals.append(dict(contract=bar.contract, start=first.isoformat(),
                                                     before=bar.timestamp.isoformat(), count=missing))
        ins = instrument(bar.symbol)
        if any(abs(ins.round_tick(p) - p) > 1e-8 for p in (bar.open, bar.high, bar.low, bar.close)):
            report.off_tick_prices += 1
        previous_contract[bar.contract] = bar
    report.warnings.extend(["Partial dataset boundaries are not treated as complete sessions.", calendar.source])
    if report.off_tick_prices:
        report.warnings.append("Off-tick prices found; may indicate adjusted or corrupted input")
    return report


class CSVProvider(DataProvider):
    def __init__(self, path, symbol, calendar, interval_minutes=1, contract=None):
        if interval_minutes not in (1, 5):
            raise ValueError("Initial CSV support is 1 or 5 minutes")
        self.path, self.symbol, self.calendar = Path(path), symbol, calendar
        self.interval, self.contract = timedelta(minutes=interval_minutes), contract

    def load(self):
        bars = []
        with self.path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            if not {"timestamp", "open", "high", "low", "close", "volume"}.issubset(reader.fieldnames or []):
                raise ValueError("CSV requires timestamp,open,high,low,close,volume")
            for line, row in enumerate(reader, 2):
                try:
                    contract = row.get("contract") or self.contract
                    if not contract:
                        raise ValueError("Dated contract is required; continuous inputs need constituent contracts")
                    if row.get("symbol") and row["symbol"] != self.symbol:
                        raise ValueError("Unexpected symbol")
                    optional = {key: float(row[key]) if row.get(key) else None
                                for key in ("trade_count", "bid_volume", "ask_volume", "open_interest")}
                    for key in ("bar_state", "coverage_state", "provider", "dataset", "schema", "raw_symbol", "request_id", "coverage_evidence", "open_interest_state"):
                        if row.get(key):
                            optional[key] = row[key]
                    for key in ("instrument_id", "source_ts_event_ns"):
                        if row.get(key):
                            optional[key] = int(row[key])
                    if row.get("published"):
                        if row["published"] not in ("True", "False"):
                            raise ValueError("Invalid published marker")
                        optional["published"] = row["published"] == "True"
                    if row.get("open_interest_available_at"):
                        optional["open_interest_available_at"] = datetime.fromisoformat(row["open_interest_available_at"])
                    bars.append(Bar(datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                                    *(float(row[key]) for key in ("open", "high", "low", "close", "volume")),
                                    contract, self.symbol, self.interval, **optional))
                except (ValueError, TypeError) as error:
                    raise ValueError("CSV line {}: {}".format(line, error)) from error
        report = validate(bars, self.calendar)
        return tuple(bars), report
