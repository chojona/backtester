"""Read-only, evidence-preserving NQ session observations (schema v1.0.0)."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .volatility import BPV_ESTIMATOR_VERSION

SCHEMA_VERSION = "nq-research-session-v1.0.0"
ROOT = Path(__file__).resolve().parents[1]
PHASE3 = Path("results/databento-nq-full-history/phase3-v3.0.0")
BPV = Path("results/databento-nq-full-history/bpv-segment-v1.0.0")
W1 = Path("results/nq-w1-exploratory-v1.0.0")


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _verified(root: Path, rel: str, expected: str) -> str:
    relative = Path(rel)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Evidence path must be relative to the research root")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Evidence path escapes the research root")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Invalid evidence SHA-256 digest")
    if not path.is_file() or _digest(path) != expected:
        raise ValueError(f"Missing or changed evidence artifact: {rel}")
    return rel


def _utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("UTC timestamp required")
    return result.astimezone(timezone.utc)


def _py_datetime(value) -> datetime:
    return value.to_pydatetime() if hasattr(value, "to_pydatetime") else value


@dataclass(frozen=True)
class SessionObservation:
    schema_version: str
    eligibility: str
    cme_trade_date: date
    selected_contract: str
    session_start_utc: datetime
    session_end_utc: datetime
    realized_variance: float
    positive_semivariance: float
    negative_semivariance: float
    bipower_variation: float
    eligible_minute_count: int
    missing_minute_count: int
    has_missing_minutes: bool
    continuity_ok: bool
    evidence_classification: str
    assumption_ids: tuple[str, ...]
    source_hashes: tuple[tuple[str, str], ...]
    methodology_version: str
    availability_time_utc: datetime | None
    availability_status: str  # observed, assumed, unknown
    session_ordinal: int
    continuity_segment: int
    calendar_status: str
    historical_tier: str


@dataclass(frozen=True)
class SessionWindow:
    observations: tuple[SessionObservation, ...]
    eligibility: str
    conditional_policy: str | None
    source_hashes: tuple[tuple[str, str], ...]


def _metric(value) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("Invalid volatility measure")
    return number


def _validated(row: SessionObservation) -> SessionObservation:
    if row.schema_version != SCHEMA_VERSION or row.eligibility not in {"strict", "conditional", "prospective"}:
        raise ValueError("Unsupported observation schema or eligibility")
    if not row.selected_contract.startswith("NQ") or row.session_start_utc >= row.session_end_utc:
        raise ValueError("Invalid session identity")
    if row.has_missing_minutes or row.missing_minute_count or not row.continuity_ok or row.eligible_minute_count < 1:
        raise ValueError("Incomplete session")
    if row.session_ordinal < 1 or row.continuity_segment < 1:
        raise ValueError("Invalid chronology identifiers")
    if not math.isclose(row.realized_variance, row.positive_semivariance + row.negative_semivariance,
                        rel_tol=1e-9, abs_tol=1e-15):
        raise ValueError("Semivariance does not reconcile")
    if row.availability_status not in {"observed", "assumed", "unknown"} or (
        row.availability_status == "unknown") != (row.availability_time_utc is None):
        raise ValueError("Invalid availability status")
    if row.availability_time_utc is not None and row.availability_time_utc < row.session_end_utc:
        raise ValueError("Session measure cannot be available before session end")
    if row.eligibility in {"strict", "prospective"} and row.historical_tier != "A":
        raise ValueError("Strict or prospective session is not Tier A")
    if row.eligibility == "conditional" and (not row.assumption_ids or row.availability_status != "assumed"):
        raise ValueError("Conditional assumptions must remain explicit")
    if row.eligibility == "prospective" and row.availability_status != "observed":
        raise ValueError("Prospective data require observed availability")
    if not row.source_hashes or any(not re.fullmatch(r"[0-9a-f]{64}", h) for _, h in row.source_hashes):
        raise ValueError("Missing immutable source hashes")
    return row


def _ordered(rows: list[SessionObservation]) -> tuple[SessionObservation, ...]:
    if any(a.cme_trade_date >= b.cme_trade_date or a.session_ordinal >= b.session_ordinal
           for a, b in zip(rows, rows[1:])):
        raise ValueError("Research sessions must be unique and chronological")
    return tuple(rows)


def _load_strict(root: Path) -> tuple[SessionObservation, ...]:
    import pyarrow.parquet as pq

    report_path = root / PHASE3 / "certification-report.json"
    report = json.loads(report_path.read_text())
    _verified(root, "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet",
              report["source_hashes"]["results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"])
    for name in ("strict-certified.parquet", "strict-certified-allowlist.csv", "certification-by-session.csv"):
        _verified(root, str(PHASE3 / name), report["output_hashes"][name])
    bpv_manifest_path = root / BPV / "manifest.json"
    bpv_manifest = json.loads(bpv_manifest_path.read_text())
    if bpv_manifest["version"] != BPV_ESTIMATOR_VERSION or bpv_manifest["source_parquet_sha256"] != report["source_hashes"]["results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"]:
        raise ValueError("BPV methodology does not match certified source")
    _verified(root, str(BPV / "volatility-by-session.csv"), bpv_manifest["output_csv_sha256"])
    with (root / PHASE3 / "strict-certified-allowlist.csv").open(newline="") as stream:
        allowed = list(csv.DictReader(stream))
    with (root / BPV / "volatility-by-session.csv").open(newline="") as stream:
        metrics = {(r["trading_date"], r["contract"]): r for r in csv.DictReader(stream)}
    table = pq.read_table(root / PHASE3 / "strict-certified.parquet")
    bars = {}
    for r in table.to_pylist():
        key = r["trading_date"].isoformat()
        bars.setdefault(key, []).append(r)
    if len(allowed) != len(bars) or len(allowed) != report["strict_research_dates"]:
        raise ValueError("Strict allowlist and Parquet do not reconcile")
    lineage = tuple(sorted((str(PHASE3 / name), report["output_hashes"][name]) for name in
                           ("strict-certified.parquet", "strict-certified-allowlist.csv", "certification-by-session.csv"))) + (
        (str(PHASE3 / "certification-report.json"), _digest(report_path)),
        (str(BPV / "manifest.json"), _digest(bpv_manifest_path)),
        (str(BPV / "volatility-by-session.csv"), bpv_manifest["output_csv_sha256"]),
        ("results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet", bpv_manifest["source_parquet_sha256"]),
    )
    result = []
    for ordinal, a in enumerate(allowed, 1):
        day = a["trading_date"]
        rows = sorted(bars.pop(day), key=lambda r: r["timestamp_utc"])
        count = int(a["expected_active_minutes"])
        if (a["tier"] != "A" or a["certification_version"] != report["version"] or
            a["research_eligibility"] != "STRICT_AND_EXPLORATORY" or
            a["observed_active_minutes"] != str(count) or len(rows) != count or
            a["off_schedule_trade_minutes"] != "0" or a["duplicate_selected_minutes"] != "0" or
            any(r["contract"] != a["selected_contract"] or r["quality_tier"] != "A" or
                r["certification_version"] != report["version"] or
                r["research_segment_id"] != int(a["strict_segment_id"]) for r in rows) or
            any(b["timestamp_utc"] - x["timestamp_utc"] != timedelta(minutes=1) for x, b in zip(rows, rows[1:]))):
            raise ValueError(f"Invalid strict session: {day}")
        m = metrics[(day, a["selected_contract"])]
        if m["n"] != str(count) or m["bpv_estimator_version"] != BPV_ESTIMATOR_VERSION:
            raise ValueError("Strict estimator row mismatch")
        segment = int(a["strict_segment_id"])
        result.append(_validated(SessionObservation(
            SCHEMA_VERSION, "strict", date.fromisoformat(day), a["selected_contract"],
            _py_datetime(rows[0]["timestamp_utc"]),
            _py_datetime(rows[-1]["timestamp_utc"] + timedelta(minutes=1)),
            _metric(m["rv"]), _metric(m["positive_semivariance"]),
            _metric(m["negative_semivariance"]), _metric(m["bpv"]), count, 0, False, True,
            "tier_a_certified_retrospective", (), lineage,
            f"{report['version']}+{BPV_ESTIMATOR_VERSION}", None, "unknown", ordinal,
            segment, a["calendar_validity"], "A")))
    return _ordered(result)


def _load_conditional(root: Path) -> tuple[SessionObservation, ...]:
    base = root / W1
    manifest_path = base / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if (manifest["schema_version"] != "nq-w1-exploratory-v1.0.0" or
        manifest["decision"] != "GO_CONDITIONAL_EXPLORATORY_MODEL_DEVELOPMENT" or
        manifest["historical_point_in_time_availability_proven"] or manifest["strict_causal_validity"]):
        raise ValueError("Unsupported conditional release")
    for name, digest in manifest["output_sha256"].items():
        _verified(root, str(W1 / name), digest)
    for name, digest in manifest["input_sha256"].items():
        _verified(root, name, digest)
    for line in (base / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        _verified(root, str(W1 / name), expected)
    series = json.loads((base / "daily-series.json").read_text())
    if series["schema_version"] != manifest["schema_version"] or len(series["dates"]) != manifest["date_count"]:
        raise ValueError("Conditional series mismatch")
    lineage = tuple(sorted(manifest["input_sha256"].items())) + tuple(sorted(
        (str(W1 / name), digest) for name, digest in manifest["output_sha256"].items())) + (
        (str(W1 / "manifest.json"), _digest(manifest_path)),)
    result = []
    for i, r in enumerate(series["dates"], 1):
        segs = r["active_segments"]
        count = sum(int(s["expected_minutes"]) for s in segs)
        classes = r["minute_counts"]
        if any((_utc(s["end_utc"]) - _utc(s["start_utc"])) != timedelta(minutes=s["expected_minutes"])
               or s["observed_bars"] + len(s["missing_minutes_utc"]) != s["expected_minutes"]
               for s in segs):
            raise ValueError("Conditional active segment grid mismatch")
        if any(_utc(a["end_utc"]) > _utc(b["start_utc"]) for a, b in zip(segs, segs[1:])):
            raise ValueError("Conditional active segments overlap")
        if (r["ordinal"] != i or not segs or count != r["matched_coverage"]["covered_minutes_1m"] or
            count != classes.get("OBSERVED_TRADE", 0) + classes.get("PROVIDER_OBSERVED_NO_TRADE", 0) or
            sum(s["observed_bars"] for s in segs) != classes.get("OBSERVED_TRADE", 0) or
            sum(len(s["missing_minutes_utc"]) for s in segs) != classes.get("PROVIDER_OBSERVED_NO_TRADE", 0) or
            r["historical_tier_unchanged"] not in {"A", "B", "C"}):
            raise ValueError("Invalid conditional coverage or identity")
        assumptions = ["session_measure_available_45m_after_close", "retained_provider_scope"]
        if r["unresolved_electronic_volume"] is not None:
            assumptions.append("unresolved_selector_existing_path")
        if r["calendar_evidence_label"] == "assumed_ordinary_hours_provisional":
            assumptions.append("provisional_ordinary_hours")
        if classes.get("PROVIDER_OBSERVED_NO_TRADE", 0):
            assumptions.append("provider_supported_no_trade_clock")
        start, end = _utc(segs[0]["start_utc"]), _utc(segs[-1]["end_utc"])
        if any(_utc(s["end_utc"]) <= _utc(s["start_utc"]) for s in segs) or start >= end:
            raise ValueError("Invalid conditional session bounds")
        m = r["daily_estimators"]
        result.append(_validated(SessionObservation(
            SCHEMA_VERSION, "conditional", date.fromisoformat(r["trade_date"]),
            r["selected_contract_for_conditional_path"], start, end,
            _metric(m["rv1"]), _metric(m["rs_positive"]), _metric(m["rs_negative"]),
            _metric(m["bpv"]), count, 0, False, True,
            f"{r['selector_evidence_label']}|{r['calendar_evidence_label']}",
            tuple(assumptions), lineage, f"{manifest['schema_version']}+nq-clock-returns-v2.0.0",
            end + timedelta(minutes=45), "assumed", i, 1,
            r["calendar_evidence_label"], r["historical_tier_unchanged"])))
    return _ordered(result)


def _load_prospective(root: Path, manifest_path: Path) -> tuple[SessionObservation, ...]:
    """Read a future sealed daily release with observed receipt timestamps."""
    manifest_path = (manifest_path if manifest_path.is_absolute() else root / manifest_path).resolve()
    if not manifest_path.is_relative_to(root.resolve()):
        raise ValueError("Prospective manifest must be inside research root")
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("eligibility") != "prospective"
            or not manifest.get("methodology_version") or not manifest.get("source_sha256")
            or not manifest.get("observations_sha256")):
        raise ValueError("Unsupported prospective manifest")
    relative = manifest_path.relative_to(root.resolve())
    observations_rel = manifest["observations_file"]
    if observations_rel in manifest["source_sha256"]:
        raise ValueError("Observation artifact must have one declared digest")
    sources = {**manifest["source_sha256"], observations_rel: manifest["observations_sha256"]}
    for name, digest in sources.items():
        _verified(root, name, digest)
    records = json.loads((root / observations_rel).read_text())
    if not isinstance(records, list):
        raise ValueError("Prospective observations must be a list")
    lineage = tuple(sorted(sources.items())) + ((str(relative), _digest(manifest_path)),)
    output = []
    for r in records:
        if r.get("evidence_classification") != "prospective_observed" or r.get("assumption_ids"):
            raise ValueError("Prospective evidence must be observed and assumption-free")
        output.append(_validated(SessionObservation(
            SCHEMA_VERSION, "prospective", date.fromisoformat(r["cme_trade_date"]),
            r["selected_contract"], _utc(r["session_start_utc"]), _utc(r["session_end_utc"]),
            _metric(r["realized_variance"]), _metric(r["positive_semivariance"]),
            _metric(r["negative_semivariance"]), _metric(r["bipower_variation"]),
            int(r["eligible_minute_count"]), int(r["missing_minute_count"]),
            r["has_missing_minutes"], r["continuity_ok"], r["evidence_classification"], (),
            lineage, manifest["methodology_version"], _utc(r["availability_time_utc"]),
            "observed", int(r["session_ordinal"]), int(r["continuity_segment"]),
            r["calendar_status"], r["historical_tier"])))
    if len(output) != manifest.get("session_count"):
        raise ValueError("Prospective session count mismatch")
    return _ordered(output)


def load_sessions(mode: str = "strict", *, allow_conditional: bool = False,
                  root: Path = ROOT, prospective_manifest: Path | None = None) -> tuple[SessionObservation, ...]:
    """Load one eligibility class; conditional access requires explicit opt-in."""
    root = Path(root)
    if mode == "strict":
        return _load_strict(root)
    if mode == "conditional":
        if not allow_conditional:
            raise PermissionError("Conditional research requires allow_conditional=True")
        return _load_conditional(root)
    if mode == "prospective":
        if prospective_manifest is None:
            raise ValueError("Prospective mode requires a versioned prospective manifest")
        return _load_prospective(root, Path(prospective_manifest))
    raise ValueError(f"Unsupported research mode: {mode}")


def consecutive_windows(sessions, length: int, *, conditional_policy: str | None = None) -> tuple[SessionWindow, ...]:
    """Return chronological windows, rejecting unresolved gaps by default.

    ``conditional_policy='release_chronology'`` accepts the W1 release's frozen
    120-date calendar sequence, including documented holiday exceptions.
    """
    rows = tuple(sessions)
    if not isinstance(length, int) or isinstance(length, bool) or length < 1:
        raise ValueError("Positive integer window length required")
    if not rows:
        return ()
    mode = rows[0].eligibility
    for row in rows:
        _validated(row)
    if any(r.eligibility != mode for r in rows):
        raise ValueError("Mixed eligibility is forbidden")
    if any(r.schema_version != rows[0].schema_version or
           r.methodology_version != rows[0].methodology_version or
           r.source_hashes != rows[0].source_hashes for r in rows):
        raise ValueError("Mixed research releases are forbidden")
    if conditional_policy not in {None, "release_chronology"} or (conditional_policy and mode != "conditional"):
        raise ValueError("Unsupported conditional gap policy")
    if mode == "conditional" and conditional_policy is None:
        raise ValueError("Conditional windows require conditional_policy='release_chronology'")
    if any(a.cme_trade_date >= b.cme_trade_date or a.session_ordinal >= b.session_ordinal
           for a, b in zip(rows, rows[1:])):
        raise ValueError("Sessions must be unique and chronological")
    output = []
    for i in range(len(rows) - length + 1):
        span = rows[i:i + length]
        if any(b.session_ordinal != a.session_ordinal + 1 or
               b.continuity_segment != a.continuity_segment or
               (mode == "strict" and (b.cme_trade_date - a.cme_trade_date).days > 3)
               for a, b in zip(span, span[1:])):
            continue
        hashes = tuple(sorted(set(h for r in span for h in r.source_hashes)))
        output.append(SessionWindow(span, mode, conditional_policy, hashes))
    return tuple(output)
