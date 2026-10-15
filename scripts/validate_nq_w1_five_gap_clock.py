"""Read-only arithmetic audit of the five evidenced W1 no-trade minutes."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import databento as db
import pyarrow.dataset as ds
from backtester.data import Bar
from backtester.sessions import SessionCalendar
from backtester.volatility import RealizedVolatility

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/raw/databento/NQ/w1-five-gap-investigation-20261014T205456Z"
CANDIDATE = ROOT / "results/nq-w1-120-session-candidate.json"
SOURCE = ROOT / "results/databento-nq-full-history/nq_outright_ohlcv_1m.parquet"
LEDGER = ROOT / "results/databento-nq-full-history/phase3-v3.0.0/certification-by-session.csv"
OUT = ROOT / "results/nq-w1-five-gap-clock-validation.json"
MINUTE = timedelta(minutes=1)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for part in iter(lambda: file.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def logret(a, b):
    assert a > 0 and b > 0 and math.isfinite(a) and math.isfinite(b)
    return math.log(b / a)


def verify_evidence(manifest, candidate):
    assert manifest["completed"] and len(manifest["requests"]) == len(manifest["responses"]) == 10
    assert sha(CANDIDATE) == manifest["candidate_sha256"]
    assert sha(SOURCE) == manifest["source_parquet_sha256"] == candidate["sources_sha256"]["parquet"]
    assert sha(LEDGER) == manifest["phase3_ledger_sha256"] == candidate["sources_sha256"]["phase3_ledger"]
    gaps = candidate["active_minute_gaps"]
    assert len(gaps) == 5
    evidence = {}
    for gap, trade_q, status_q, trade, status in zip(gaps, manifest["requests"][::2], manifest["requests"][1::2],
                                                      manifest["responses"][::2], manifest["responses"][1::2]):
        for q, r, role in ((trade_q, trade, "missing_minute_trades"),
                           (status_q, status, "session_open_through_gap_status")):
            request = q["request"]
            assert r["request"] == request and r["role"] == role and r["trade_date"] == gap["trade_date"]
            assert request == {"dataset": "GLBX.MDP3", "schema": "trades" if role == "missing_minute_trades" else "status",
                               "symbols": [gap["raw_symbol"]], "stype_in": "raw_symbol",
                               "start": gap["start_utc"] if role == "missing_minute_trades" else gap["session_open_utc"],
                               "end": gap["end_utc"]}
            assert r["bounds_cover_request"]
            for key in ("dbn", "jsonl"):
                assert sha(RUN / r[f"{key}_file"]) == r[f"{key}_sha256"]
            lines = (RUN / r["jsonl_file"]).read_text().splitlines()
            assert len(lines) == r["returned_records"]
            meta = db.DBNStore.from_file(RUN / r["dbn_file"]).metadata
            assert meta.dataset == request["dataset"] and str(meta.schema) == request["schema"]
            assert meta.symbols == request["symbols"] and str(meta.stype_in) == "raw_symbol"
            assert meta.limit is None and not meta.partial and not meta.not_found
            assert meta.start == int(stamp(request["start"]).timestamp()) * 10**9
            assert meta.end == int(stamp(request["end"]).timestamp()) * 10**9
            assert r["metadata"]["start_ns"] == meta.start and r["metadata"]["end_ns"] == meta.end
        assert trade["returned_records"] == 0
        events = [json.loads(s) for s in (RUN / status["jsonl_file"]).read_text().splitlines()]
        assert len(events) in (2, 3)
        assert [e["action"] for e in events] in ([6, 7], [6, 7, 7])
        assert all(e["is_trading"] == "Y" and e["is_quoting"] == "Y" for e in events)
        assert all(int(e["ts_recv"]) >= int(stamp(status_q["request"]["start"]).timestamp()) * 10**9
                   and int(e["ts_recv"]) < int(stamp(status_q["request"]["end"]).timestamp()) * 10**9 for e in events)
        assert len({e["hd"]["instrument_id"] for e in events}) == 1
        evidence[gap["start_utc"]] = {"gap": gap, "trade_sha256": trade["dbn_sha256"],
                                      "status_sha256": status["dbn_sha256"],
                                      "status_count": len(events), "instrument_id": events[0]["hd"]["instrument_id"]}
    assert [r["request"] for r in manifest["requests"]] == [r["request"] for r in candidate["retrieval"]["requests"]]
    return evidence


def segments(day):
    # Candidate active parts carry dated holiday halt boundaries. The frozen
    # research clock subdivides each active part at 09:30 and 16:00 New York.
    from zoneinfo import ZoneInfo
    ny = ZoneInfo("America/New_York")
    result = []
    for active in day["segments"]:
        start, end = stamp(active["start_utc"]), stamp(active["end_utc"])
        local_day = start.astimezone(ny).date()
        last_local_day = end.astimezone(ny).date()
        cuts = []
        while local_day <= last_local_day:
            cuts.extend(datetime.combine(local_day, datetime.strptime(t, "%H:%M").time(), ny).astimezone(timezone.utc)
                        for t in ("09:30", "16:00"))
            local_day += timedelta(days=1)
        bounds = [start] + [c for c in cuts if start < c < end] + [end]
        for a, b in zip(bounds, bounds[1:]):
            assert (b - a).total_seconds() % 900 == 0
            result.append((a, b))
    return result


def measure(day, bars, evidence):
    symbol, contract = day["selected_raw_symbol"], day["selected_contract"]
    segs = segments(day)
    exp_r, sparse_r, exp_pairs, sparse_pairs = [], [], [], []
    exp_blocks, sparse_blocks = [], []
    details = []
    gap_local = None
    for seg_start, seg_end in segs:
        grid = [seg_start + i * MINUTE for i in range(int((seg_end - seg_start) / MINUTE))]
        assert len(grid) % 5 == 0
        observed = [bars.get((symbol, t)) for t in grid]
        gap_indices = [i for i, b in enumerate(observed) if b is None]
        assert all(t.isoformat().replace("+00:00", "Z") in evidence for i, t in enumerate(grid) if observed[i] is None)
        assert observed[0] is not None
        # Clock returns use the first observed open at this frozen segment start.
        prev_clock = observed[0]["open"]
        prev_sparse = None
        previous_sparse_index = None
        segment_exp, segment_sparse, clock_prices = [], [], []
        segment_exp_pairs, segment_sparse_pairs = [], []
        for i, (t, bar) in enumerate(zip(grid, observed)):
            if bar is None:
                assert i > 0
                r_exp = 0.0
                r_sparse = None
            else:
                assert bar["contract"] == contract and bar["raw_symbol"] == symbol
                assert bar["volume"] > 0
                if i == 0:
                    assert prev_sparse is None
                    sparse_reference = bar["open"]
                elif previous_sparse_index == i - 1:
                    sparse_reference = prev_sparse
                else:
                    sparse_reference = bar["open"]
                r_exp = logret(prev_clock, bar["close"])
                r_sparse = logret(sparse_reference, bar["close"])
                prev_clock = bar["close"]
                prev_sparse, previous_sparse_index = bar["close"], i
            segment_exp.append(r_exp)
            segment_sparse.append(r_sparse)
            clock_prices.append(prev_clock)
            if i:
                segment_exp_pairs.append(abs(segment_exp[i - 1] * r_exp))
                if r_sparse is not None and segment_sparse[i - 1] is not None:
                    segment_sparse_pairs.append(abs(segment_sparse[i - 1] * r_sparse))
        for offset in range(0, len(grid), 5):
            block_return = math.fsum(segment_exp[offset:offset + 5])
            block_reference = observed[0]["open"] if offset == 0 else clock_prices[offset - 1]
            assert abs(block_return - logret(block_reference, clock_prices[offset + 4])) < 1e-12
            exp_blocks.append((grid[offset], block_return))
            sparse_block = segment_sparse[offset:offset + 5]
            if all(r is not None for r in sparse_block):
                sparse_blocks.append((grid[offset], math.fsum(sparse_block)))
        if gap_indices:
            assert len(gap_indices) == 1 and gap_local is None
            i = gap_indices[0]
            assert 0 < i < len(grid) - 2 and observed[i + 1] is not None and observed[i + 2] is not None
            block_offset = i // 5 * 5
            post_clock, post_sparse, next_return = segment_exp[i + 1], segment_sparse[i + 1], segment_exp[i + 2]
            assert post_sparse is not None and abs(post_clock) > 0
            block_return = math.fsum(segment_exp[block_offset:block_offset + 5])
            gap_local = {"gap_utc": grid[i].isoformat().replace("+00:00", "Z"),
                         "prior_close": observed[i - 1]["close"], "next_open": observed[i + 1]["open"],
                         "next_close": observed[i + 1]["close"],
                         "post_gap_clock_return": post_clock, "post_gap_sparse_return": post_sparse,
                         "next_return": next_return,
                         "rv1_delta_formula": post_clock**2 - post_sparse**2,
                         "bpv_delta_formula": math.pi/2 * abs(next_return) * (abs(post_clock) - abs(post_sparse)),
                         "missing_sparse_block_start_utc": grid[block_offset].isoformat().replace("+00:00", "Z"),
                         "missing_sparse_block_return": block_return,
                         "rv5_delta_formula": block_return**2}
        exp_r.extend(segment_exp)
        sparse_r.extend(r for r in segment_sparse if r is not None)
        exp_pairs.extend(segment_exp_pairs)
        sparse_pairs.extend(segment_sparse_pairs)
        details.append({"start_utc": seg_start.isoformat().replace("+00:00", "Z"),
                        "end_utc": seg_end.isoformat().replace("+00:00", "Z"),
                        "minutes": len(grid), "observed_bars": len(grid) - len(gap_indices),
                        "gap_indices": gap_indices, "rv5_blocks": len(grid) // 5,
                        "sparse_rv5_blocks": sum(all(r is not None for r in segment_sparse[j:j + 5])
                                                  for j in range(0, len(grid), 5))})
    exp_metrics = {"rv1": math.fsum(r*r for r in exp_r), "rv5": math.fsum(r*r for _, r in exp_blocks),
                   "rs_positive": math.fsum(r*r for r in exp_r if r > 0),
                   "rs_negative": math.fsum(r*r for r in exp_r if r < 0),
                   "bpv": math.pi/2 * math.fsum(exp_pairs), "one_minute_returns": len(exp_r),
                   "five_minute_blocks": len(exp_blocks), "bpv_pairs": len(exp_pairs)}
    sparse_metrics = {"observed_rv1": math.fsum(r*r for r in sparse_r),
                      "observed_rv5_eligible_blocks": math.fsum(r*r for _, r in sparse_blocks),
                      "observed_rs_positive": math.fsum(r*r for r in sparse_r if r > 0),
                      "observed_rs_negative": math.fsum(r*r for r in sparse_r if r < 0),
                      "observed_bpv": math.pi/2 * math.fsum(sparse_pairs),
                      "one_minute_returns": len(sparse_r), "five_minute_blocks": len(sparse_blocks),
                      "bpv_pairs": len(sparse_pairs)}
    assert exp_metrics["rv1"] >= 0 and abs(exp_metrics["rv1"] - exp_metrics["rs_positive"] - exp_metrics["rs_negative"]) < 1e-16
    if gap_local:
        assert abs(exp_metrics["rv1"] - sparse_metrics["observed_rv1"] - gap_local["rv1_delta_formula"]) < 1e-15
        assert abs(exp_metrics["rv5"] - sparse_metrics["observed_rv5_eligible_blocks"] - gap_local["rv5_delta_formula"]) < 1e-15
        assert abs(exp_metrics["bpv"] - sparse_metrics["observed_bpv"] - gap_local["bpv_delta_formula"]) < 1e-15
    assert sum(x["minutes"] for x in details) == day["expected_minutes"]
    assert sum(x["observed_bars"] for x in details) == day["observed_bars"]
    return {"experimental": exp_metrics, "sparse_diagnostic": sparse_metrics,
            "segments": details, "gap_local": gap_local,
            "rv5_blocks": [(t.isoformat().replace("+00:00", "Z"), r) for t, r in exp_blocks],
            "sparse_rv5_blocks": [(t.isoformat().replace("+00:00", "Z"), r) for t, r in sparse_blocks]}


def main():
    candidate = json.loads(CANDIDATE.read_text())
    manifest = json.loads((RUN / "manifest.json").read_text())
    evidence = verify_evidence(manifest, candidate)
    dataset = ds.dataset(SOURCE, format="parquet")
    # Timestamp/contract selection respects holiday-remapped trade dates without
    # modifying the retained Parquet's original trading_date labels.
    first = stamp(candidate["trade_dates"][0]["segments"][0]["start_utc"])
    last = stamp(candidate["trade_dates"][-1]["segments"][-1]["end_utc"])
    table = dataset.to_table(columns=["timestamp_utc", "raw_symbol", "contract", "instrument_id", "open", "high", "low", "close", "volume"],
                             filter=(ds.field("timestamp_utc") >= first) & (ds.field("timestamp_utc") < last))
    bars = {}
    for row in table.to_pylist():
        key = (row["raw_symbol"], row["timestamp_utc"])
        assert key not in bars
        bars[key] = row
    outputs = []
    for day in candidate["trade_dates"]:
        result = measure(day, bars, evidence)
        if day["trade_date"] in {e["gap"]["trade_date"] for e in evidence.values()}:
            # Read-only call to the original sparse-bar estimator. The current
            # implementation deliberately returns null canonical daily values.
            production = RealizedVolatility(SessionCalendar(breaks=[]))
            final = None
            for start, end in segments(day):
                for i in range(int((end - start) / MINUTE)):
                    row = bars.get((day["selected_raw_symbol"], start + i * MINUTE))
                    if row is None:
                        continue
                    bar = Bar(row["timestamp_utc"], row["open"], row["high"], row["low"], row["close"],
                              row["volume"], row["contract"], "NQ")
                    final = production.update(bar, as_of=bar.end)
            assert final is not None and not final.session_complete and final.missing_bars_to_now == 1
            assert final.rv_1m is None and final.rv_5m is None and final.bpv is None
            assert final.samples_5m == 275
            result["original_sparse_estimator"] = {"rv_1m": final.rv_1m, "rv_5m": final.rv_5m,
                                                     "bpv": final.bpv, "rs_positive": final.rs_positive,
                                                     "rs_negative": final.rs_negative,
                                                     "observed_rv": final.observed_rv,
                                                     "samples_5m": final.samples_5m,
                                                     "observed_bars": final.observed_bars,
                                                     "missing_bars_to_now": final.missing_bars_to_now,
                                                     "session_complete": final.session_complete}
        outputs.append({"trade_date": day["trade_date"], "selected_contract": day["selected_contract"],
                        "expected_minutes": day["expected_minutes"], "observed_bars": day["observed_bars"],
                        **result})
    gap_dates = {e["gap"]["trade_date"] for e in evidence.values()}
    assert {r["trade_date"] for r in outputs if r["observed_bars"] != r["expected_minutes"]} == gap_dates
    assert sum(r["expected_minutes"] for r in outputs) == 169020
    assert sum(r["observed_bars"] for r in outputs) == 169015
    assert sum(r["experimental"]["five_minute_blocks"] for r in outputs) == 169020 // 5
    # Independently reconstruct every HAR row from chronological session indices,
    # then compare once per date with the candidate's frozen origin/target plan.
    planned = candidate["har"]["target_and_origin_rows"]
    assert len(planned) == 98
    rows = []
    for j in range(22, 120):
        q, target = planned[j - 22], outputs[j]
        assert q["target_ordinal"] == j + 1 and q["target_trade_date"] == target["trade_date"]
        assert q["forecast_origin_trade_date"] == outputs[j - 1]["trade_date"]
        assert q["feature_22_first_trade_date"] == outputs[j - 22]["trade_date"]
        assert q["feature_5_first_trade_date"] == outputs[j - 5]["trade_date"]
        feature = outputs[j - 22:j]
        assert len({x["trade_date"] for x in feature}) == 22
        rows.append({"target_date": target["trade_date"], "split": q["split"],
                     "feature_date": outputs[j - 1]["trade_date"],
                     "rv_1": outputs[j - 1]["experimental"]["rv5"],
                     "rv_5": math.fsum(x["experimental"]["rv5"] for x in feature[-5:]) / 5,
                     "rv_22": math.fsum(x["experimental"]["rv5"] for x in feature) / 22,
                     "target_rv": target["experimental"]["rv5"],
                     "feature_22_dates": [x["trade_date"] for x in feature]})
    assert Counter(r["target_date"] for r in rows) == Counter(x["trade_date"] for x in outputs[22:])
    assert Counter(r["split"] for r in rows) == {"train": 50, "validation": 20, "test": 28}
    touched = [r for r in rows if r["target_date"] in gap_dates or gap_dates.intersection(r["feature_22_dates"])]
    assert all(all(r["feature_22_dates"].count(day) <= 1 for day in gap_dates) for r in rows)
    assert len(touched) == 65 and Counter(r["split"] for r in touched) == {"train": 38, "validation": 4, "test": 23}
    # Full block detail is retained for the five investigated dates. Other
    # dates need only daily metrics for the chronological feature audit.
    for row in outputs:
        if row["trade_date"] not in gap_dates:
            row.pop("rv5_blocks")
            row.pop("sparse_rv5_blocks")
    result = {"label": "EXPERIMENTAL_PROVIDER_CLOCK_MATH_ONLY", "candidate_sha256": sha(CANDIDATE),
              "evidence_manifest_sha256": sha(RUN / "manifest.json"), "source_parquet_sha256": sha(SOURCE),
              "evidence": evidence, "dates": outputs, "har_rows": rows,
              "potential_har_rows": len(rows), "potential_rows_touching_five_gaps": len(touched),
              "potential_split_counts": dict(Counter(r["split"] for r in rows)),
              "actual_certified_har_rows": 0,
              "note": "Potential arithmetic only: calendar, predecessor volume, certification, and vendor availability gates remain open."}
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"evidence_verified": len(evidence), "dates": len(outputs),
                      "potential_rows": len(rows), "gap_dates": gap_dates, "output": str(OUT)}, default=list))


if __name__ == "__main__":
    main()
