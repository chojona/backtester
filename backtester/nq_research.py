"""Strict NQ research inputs and unfitted, causal HAR design rows.

The functions here construct measurements and lag features only. They do not fit
or validate a forecasting model. Session ordinals come from the full certified
observed-session ledger, so exclusions and missing accepted dates break windows.
"""
from dataclasses import dataclass
from datetime import date, datetime
import csv
import math


def validate_strict_metadata(rows, allowlist, *, certification_version):
    """Check (date, contract, tier, version, segment) against a Tier A allowlist.

    ``rows`` may be a streaming iterator of parquet metadata tuples. The
    allowlist maps trading dates to (contract, tier, version, segment).
    """
    if not allowlist or any(tier != "A" or version != certification_version or
                            not isinstance(segment, int) or segment < 1
                            for _, tier, version, segment in allowlist.values()):
        raise ValueError("Strict allowlist must contain only versioned Tier A sessions")
    count = 0
    for day, contract, tier, version, segment in rows:
        if tier != "A" or version != certification_version or \
                allowlist.get(day) != (contract, tier, version, segment):
            raise ValueError(f"Uncertified or inconsistent strict research row: {day}")
        count += 1
    if not count:
        raise ValueError("Strict research dataset is empty")
    return count


def load_strict_nq_parquet(parquet_path, allowlist_path, *, certification_version):
    """Read a strict dataset only after row-by-row allowlist reconciliation."""
    import pyarrow.parquet as pq

    with open(allowlist_path, newline="") as stream:
        entries = list(csv.DictReader(stream))
    allowlist = {}
    for row in entries:
        day = date.fromisoformat(row["trading_date"])
        if day in allowlist:
            raise ValueError(f"Duplicate strict allowlist date: {day}")
        allowlist[day] = (row["selected_contract"], row["tier"],
                          row["certification_version"], int(row["strict_segment_id"]))
    reader = pq.ParquetFile(parquet_path)
    columns = ["trading_date", "contract", "quality_tier", "certification_version", "research_segment_id"]
    def metadata():
        for batch in reader.iter_batches(batch_size=100_000, columns=columns):
            yield from zip(*(batch.column(i).to_pylist() for i in range(len(columns))))
    count = validate_strict_metadata(metadata(), allowlist, certification_version=certification_version)
    if count != reader.metadata.num_rows:
        raise ValueError("Strict dataset row count does not reconcile")
    return reader.read()


@dataclass(frozen=True)
class DailyVariation:
    trading_date: date
    session_ordinal: int
    available_at: datetime
    rv: float
    quality_tier: str
    certification_version: str
    research_segment_id: int
    complete: bool


def require_strict_sessions(sessions, *, certification_version):
    """Reject every non-A, unversioned, partial, unordered or duplicated session."""
    rows = tuple(sessions)
    previous = None
    for row in rows:
        if row.quality_tier != "A" or row.certification_version != certification_version or not row.complete:
            raise ValueError("Strict research requires complete Tier A sessions at the expected certification version")
        if not isinstance(row.rv, (int, float)) or not math.isfinite(row.rv) or row.rv < 0:
            raise ValueError("Daily realized variance must be finite and nonnegative")
        if not isinstance(row.available_at, datetime) or row.available_at.tzinfo is None:
            raise ValueError("Session availability must be timezone-aware")
        if not isinstance(row.session_ordinal, int) or row.session_ordinal < 0 or not isinstance(row.research_segment_id, int) or row.research_segment_id < 1:
            raise ValueError("Session ordinal and segment must be positive integers")
        if previous is not None and (row.trading_date <= previous.trading_date or
                                     row.session_ordinal <= previous.session_ordinal or
                                     row.available_at <= previous.available_at):
            raise ValueError("Strict sessions must be unique and chronological")
        previous = row
    return rows


def build_har_rows(sessions, *, certification_version):
    """At session t close, 1/5/22 completed RV means predict session t+1 RV.

    A row exists only when all 22 feature sessions and the next target are
    consecutive in the full observed-session ledger and share one research
    segment. Feature availability must strictly precede target availability.
    """
    rows = require_strict_sessions(sessions, certification_version=certification_version)
    output = []
    for target_index in range(22, len(rows)):
        window = rows[target_index - 22:target_index + 1]
        if len({r.research_segment_id for r in window}) != 1 or any(
            b.session_ordinal != a.session_ordinal + 1 for a, b in zip(window, window[1:])
        ):
            continue
        features = window[:-1]
        target = window[-1]
        if features[-1].available_at >= target.available_at:
            raise ValueError("HAR target must become available after all features")
        output.append(dict(as_of=features[-1].available_at,
                           feature_date=features[-1].trading_date,
                           target_date=target.trading_date,
                           target_available_at=target.available_at,
                           research_segment_id=target.research_segment_id,
                           rv_1=features[-1].rv,
                           rv_5=math.fsum(r.rv for r in features[-5:]) / 5,
                           rv_22=math.fsum(r.rv for r in features) / 22,
                           target_rv=target.rv))
    return output
