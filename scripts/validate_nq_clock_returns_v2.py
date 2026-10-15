"""Rebuild the W1 evidenced clock experiment under frozen return references.

Writes only results/nq-clock-returns-v2.0.0; never edits the prior experiment.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.dataset as ds

from backtester.data import Bar
from backtester.nq_clock_experiment import GapEvidence, PROVIDER_OBSERVED_NO_TRADE
from backtester.nq_clock_returns_v2 import ClockMinuteV2, VERSION, measure_clock_v2
from scripts.validate_nq_w1_five_gap_clock import (
    CANDIDATE, LEDGER, OUT as OLD, ROOT, RUN, SOURCE, verify_evidence,
)

OUTPUT = ROOT / "results" / VERSION
AUDIT = ROOT / "reports/nq-return-boundary-specification-audit.md"
MINUTE = timedelta(minutes=1)
NY = ZoneInfo("America/New_York")
FIELDS = ("rv1", "rv5", "rs_positive", "rs_negative", "bpv")
AUDIT_FIVE = {
    "2022-06-06": (0.000283004126192, 0.000245807530114, 0.000147365747282, 0.000135638378910, 0.000284655372334),
    "2022-07-27": (0.000261577898609, 0.000336715308672, 0.000170349132546, 0.000091228766063, 0.000249036523493),
    "2022-08-16": (0.000107185211682, 0.000111139850500, 0.000051209207064, 0.000055976004618, 0.000105954201691),
    "2022-08-18": (0.000130934710263, 0.000134137847952, 0.000063726049361, 0.000067208660902, 0.000133528497791),
    "2022-10-13": (0.002197493363833, 0.002007580383880, 0.000596987248747, 0.001600506115087, 0.001185547615150),
}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def research(stamp):
    local = stamp.astimezone(NY)
    clock = (local.hour, local.minute)
    if clock < (9, 30) or clock >= (18, 0):
        return "OVERNIGHT"
    return "RTH" if clock < (16, 0) else "POST_RTH"


def active_grid(day):
    for number, part in enumerate(day["segments"]):
        start, end = utc(part["start_utc"]), utc(part["end_utc"])
        assert (end - start) / MINUTE == part["expected_minutes"]
        for i in range(part["expected_minutes"]):
            yield number, start + i * MINUTE


def evidence_object(item, manifest_path):
    gap = item["gap"]
    return GapEvidence(utc(gap["start_utc"]), utc(gap["end_utc"]), gap["contract"],
                       PROVIDER_OBSERVED_NO_TRADE, item["trade_sha256"],
                       item["status_sha256"], 0, True, True, str(manifest_path))


def make_minutes(day, bars, evidence):
    rows = []
    for active, stamp in active_grid(day):
        source = bars.get((day["selected_raw_symbol"], stamp))
        kwargs = {}
        if source is None:
            key = stamp.isoformat().replace("+00:00", "Z")
            if key not in evidence or evidence[key]["gap"]["trade_date"] != day["trade_date"]:
                raise ValueError(f"Unverified scheduled minute: {key}")
            kwargs["evidence"] = evidence_object(evidence[key], RUN / "manifest.json")
        else:
            if (source["contract"] != day["selected_contract"] or
                    source["raw_symbol"] != day["selected_raw_symbol"] or source["volume"] <= 0):
                raise ValueError("Selected contract or traded bar mismatch")
            kwargs["bar"] = Bar(stamp, source["open"], source["high"], source["low"],
                                source["close"], source["volume"], source["contract"], "NQ")
        rows.append(ClockMinuteV2(stamp, day["selected_contract"],
                                  f"{day['trade_date']}/active-{active}",
                                  research(stamp), **kwargs))
    assert len(rows) == day["expected_minutes"]
    assert sum(row.bar is not None for row in rows) == day["observed_bars"]
    return rows


def independent_reference(day, bars, evidence):
    """Direct raw-price arithmetic, without the v2 API or stored v1 returns."""
    all_returns, pair_products, block_returns = [], [], []
    no_trade = []
    for active, part in enumerate(day["segments"]):
        start, end = utc(part["start_utc"]), utc(part["end_utc"])
        previous_price = None
        prior_return = None
        prior_label = None
        block = []
        block_label = None
        t = start
        while t < end:
            bar = bars.get((day["selected_raw_symbol"], t))
            label = research(t)
            if label != block_label:
                if block:
                    assert len(block) % 5 == 0
                block = []
                block_label = label
            if bar is None:
                key = t.isoformat().replace("+00:00", "Z")
                assert key in evidence and previous_price is not None
                r = 0.0
                no_trade.append(key)
            else:
                assert bar["contract"] == day["selected_contract"]
                r = math.log(bar["close"] / (previous_price if previous_price is not None else bar["open"]))
                previous_price = bar["close"]
            if prior_label == label and prior_return is not None:
                pair_products.append(abs(prior_return * r))
            all_returns.append(r)
            block.append(r)
            if len(block) == 5:
                block_returns.append(math.fsum(block))
                block = []
            prior_return, prior_label = r, label
            t += MINUTE
        assert not block
    return {
        "rv1": math.fsum(r*r for r in all_returns),
        "rv5": math.fsum(r*r for r in block_returns),
        "rs_positive": math.fsum(r*r for r in all_returns if r > 0),
        "rs_negative": math.fsum(r*r for r in all_returns if r < 0),
        "bpv": math.pi/2 * math.fsum(pair_products),
        "no_trade": no_trade,
        "one_minute_returns": len(all_returns),
        "five_minute_blocks": len(block_returns),
        "bpv_pairs": len(pair_products),
    }


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return sha(path)


def main():
    candidate = json.loads(CANDIDATE.read_text())
    manifest_path = RUN / "manifest.json"
    evidence_manifest = json.loads(manifest_path.read_text())
    evidence = verify_evidence(evidence_manifest, candidate)  # reopens all ten DBNs/JSONLs
    assert set(evidence) == {gap["start_utc"] for gap in candidate["active_minute_gaps"]}
    assert len(evidence) == 5 and AUDIT.exists()
    old_hash = sha(OLD)
    old = json.loads(OLD.read_text())
    assert old["candidate_sha256"] == sha(CANDIDATE)
    assert old["evidence_manifest_sha256"] == sha(manifest_path)
    assert old["source_parquet_sha256"] == sha(SOURCE)
    assert len(old["dates"]) == len(candidate["trade_dates"]) == 120
    dataset = ds.dataset(SOURCE, format="parquet")
    first = utc(candidate["trade_dates"][0]["segments"][0]["start_utc"])
    last = utc(candidate["trade_dates"][-1]["segments"][-1]["end_utc"])
    table = dataset.to_table(
        columns=["timestamp_utc", "raw_symbol", "contract", "open", "high", "low", "close", "volume"],
        filter=(ds.field("timestamp_utc") >= first) & (ds.field("timestamp_utc") < last),
    )
    bars = {}
    for bar in table.to_pylist():
        key = (bar["raw_symbol"], bar["timestamp_utc"])
        if key in bars:
            raise ValueError(f"Duplicate raw bar: {key}")
        bars[key] = bar
    daily, five_checks = [], {}
    all_evidenced = []
    for day, previous in zip(candidate["trade_dates"], old["dates"]):
        assert day["trade_date"] == previous["trade_date"]
        minutes = make_minutes(day, bars, evidence)
        got = measure_clock_v2(minutes)
        metrics = got["metrics"]
        assert got["complete"] and metrics["unknown_minutes"] == 0
        assert metrics["one_minute_returns"] == day["expected_minutes"]
        assert metrics["five_minute_blocks"] == day["expected_minutes"] // 5
        assert abs(metrics["rv1"] - metrics["rs_positive"] - metrics["rs_negative"]) < 1e-15
        expected = independent_reference(day, bars, evidence)
        for field in FIELDS:
            assert math.isclose(metrics[field], expected[field], rel_tol=0, abs_tol=2e-15), (day["trade_date"], field)
        assert (metrics["one_minute_returns"], metrics["five_minute_blocks"], metrics["bpv_pairs"],
                metrics["no_trade_minutes"]) == (expected["one_minute_returns"], expected["five_minute_blocks"],
                                                  expected["bpv_pairs"], len(expected["no_trade"]))
        all_evidenced.extend(expected["no_trade"])
        if day["trade_date"] in AUDIT_FIVE:
            for field, target in zip(FIELDS, AUDIT_FIVE[day["trade_date"]]):
                assert math.isclose(expected[field], target, rel_tol=0, abs_tol=5e-13), (day["trade_date"], field)
            five_checks[day["trade_date"]] = {field: expected[field] for field in FIELDS}
        old_metrics = previous["experimental"]
        delta = {field: metrics[field] - old_metrics[field] for field in FIELDS}
        daily.append({"trade_date": day["trade_date"], "selected_contract": day["selected_contract"],
                      "expected_minutes": day["expected_minutes"], "observed_source_bars": day["observed_bars"],
                      "metrics": metrics, "delta_from_v1": delta,
                      "no_trade_utc": expected["no_trade"],
                      **({"rv5_blocks": [(t.isoformat().replace("+00:00", "Z"), r)
                                          for t, r in got["rv5_blocks"]]} if day["trade_date"] in AUDIT_FIVE else {})})
    assert sorted(all_evidenced) == sorted(evidence)
    assert sum(d["expected_minutes"] for d in daily) == 169020
    assert sum(d["observed_source_bars"] for d in daily) == 169015
    assert sum(d["metrics"]["five_minute_blocks"] for d in daily) == 33804
    planned = candidate["har"]["target_and_origin_rows"]
    assert len(planned) == 98
    har = []
    for j in range(22, 120):
        plan = planned[j - 22]
        feature = daily[j - 22:j]
        target = daily[j]
        assert plan["target_ordinal"] == j + 1
        assert plan["target_trade_date"] == target["trade_date"]
        assert plan["forecast_origin_trade_date"] == feature[-1]["trade_date"]
        assert plan["feature_22_first_trade_date"] == feature[0]["trade_date"]
        assert plan["feature_5_first_trade_date"] == feature[-5]["trade_date"]
        assert len({item["trade_date"] for item in feature}) == 22
        har.append({"target_date": target["trade_date"], "split": plan["split"],
                    "feature_date": feature[-1]["trade_date"],
                    "rv_1": feature[-1]["metrics"]["rv5"],
                    "rv_5": math.fsum(item["metrics"]["rv5"] for item in feature[-5:]) / 5,
                    "rv_22": math.fsum(item["metrics"]["rv5"] for item in feature) / 22,
                    "target_rv": target["metrics"]["rv5"],
                    "feature_22_dates": [item["trade_date"] for item in feature]})
    assert dict(Counter(row["split"] for row in har)) == {"train": 50, "validation": 20, "test": 28}
    assert [row["target_date"] for row in har] == [row["target_date"] for row in old["har_rows"]]
    assert [row["feature_22_dates"] for row in har] == [row["feature_22_dates"] for row in old["har_rows"]]
    changed_days = {field: sum(abs(row["delta_from_v1"][field]) > 1e-18 for row in daily) for field in FIELDS}
    changed_har = {field: sum(abs(row[field] - prior[field]) > 1e-18 for row, prior in zip(har, old["har_rows"]))
                   for field in ("rv_1", "rv_5", "rv_22", "target_rv")}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    daily_path, har_path = OUTPUT / "daily-series.json", OUTPUT / "potential-har-rows.json"
    daily_hash = write_json(daily_path, {"version": VERSION, "label": "EXPERIMENTAL_PROVIDER_CLOCK_MATH_ONLY",
                                         "dates": daily, "actual_certified_har_rows": 0})
    har_hash = write_json(har_path, {"version": VERSION, "label": "POTENTIAL_ARITHMETIC_ONLY",
                                     "rows": har, "actual_certified_har_rows": 0})
    inputs = {"candidate": sha(CANDIDATE), "source_parquet": sha(SOURCE),
              "phase3_ledger": sha(LEDGER), "evidence_manifest": sha(manifest_path),
              "return_boundary_audit": sha(AUDIT), "previous_experiment": old_hash}
    comparison = {"old_output_sha256": old_hash,
                  "new_output_sha256": {daily_path.name: daily_hash, har_path.name: har_hash},
                  "changed_daily_rows_by_metric": changed_days,
                  "changed_potential_har_rows_by_field": changed_har,
                  "five_date_independent_reference": five_checks,
                  "verified_no_trade_minutes": sorted(all_evidenced),
                  "totals": {"sessions": len(daily), "clock_minutes": 169020, "raw_bars": 169015,
                             "evidenced_no_trade": 5, "five_minute_blocks": 33804,
                             "potential_har_rows": len(har), "actual_certified_har_rows": 0}}
    manifest = {"version": VERSION, "scope": "non-certifying evidenced W1 clock arithmetic",
                "input_sha256": inputs, "comparison": comparison,
                "no_paid_retrieval": True, "har_fitted": False}
    write_json(OUTPUT / "manifest.json", manifest)
    assert sha(OLD) == old_hash
    assert {name: sha(path) for name, path in (("candidate", CANDIDATE), ("source_parquet", SOURCE),
           ("phase3_ledger", LEDGER), ("evidence_manifest", manifest_path),
           ("return_boundary_audit", AUDIT))} == {k: v for k, v in inputs.items() if k != "previous_experiment"}
    print(json.dumps({"version": VERSION, "output": str(OUTPUT), "changed_days": changed_days,
                      "changed_har_rows": changed_har, "old_sha256": old_hash,
                      "daily_sha256": daily_hash, "har_sha256": har_hash}, sort_keys=True))


if __name__ == "__main__":
    main()
