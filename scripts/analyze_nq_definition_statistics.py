"""Reproduce the bounded definition/statistics evidence audit from untouched DBN."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/raw/databento/NQ/definition-statistics-20261014T223138Z"
PLAN = ROOT / "results/nq-contract-evidence-acquisition-plan.json"
RESULT = ROOT / "results/nq-definition-statistics-evidence.json"
STREAM = ROOT / "results/nq-cleared-volume-stream.jsonl"
SENTINEL = 2**63 - 1


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for part in iter(lambda: file.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def iso(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def day(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, timezone.utc).date().isoformat()


def ns(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() * 1e9)


def main() -> None:
    acquisition = json.loads((RUN / "acquisition.json").read_text())
    if not acquisition["completed"] or len(acquisition["responses"]) != 2:
        raise ValueError("Acquisition incomplete")
    for row in acquisition["responses"]:
        if sha(RUN / row["dbn_file"]) != row["dbn_sha256"]:
            raise ValueError("Raw DBN hash changed")
    plan = json.loads(PLAN.read_text())
    if sha(PLAN) != acquisition["plan_sha256"]:
        raise ValueError("Source plan changed")
    definitions = defaultdict(list)
    definition_count = 0
    for x in db.DBNStore.from_file(RUN / "01-definition.dbn.zst"):
        definition_count += 1
        definitions[x.instrument_id].append(dict(ts_recv=x.ts_recv, ts_event=x.ts_event,
            raw_symbol=x.raw_symbol, instrument_id=x.instrument_id, activation=x.activation,
            expiration=x.expiration, maturity_year=x.maturity_year, maturity_month=x.maturity_month,
            exchange=x.exchange, group=x.group, asset=x.asset, security_type=x.security_type,
            instrument_class=str(x.instrument_class), leg_count=x.leg_count,
            security_update_action=x.security_update_action))
    for rows in definitions.values(): rows.sort(key=lambda r: (r["ts_recv"], r["ts_event"]))
    ids = {rows[-1]["raw_symbol"]: iid for iid, rows in definitions.items()}
    contracts = {iid: f"NQ{'FGHJKMNQUVXZ'[r[-1]['maturity_month']-1]}{r[-1]['maturity_year'] % 100:02d}"
                 for iid, r in definitions.items()}
    identity = {rows[-1]["raw_symbol"]: dict(instrument_id=iid, contract=contracts[iid],
        first_definition_received_utc=iso(rows[0]["ts_recv"]),
        first_definition_received_ns=rows[0]["ts_recv"],
        activation_ns=rows[-1]["activation"], expiration_ns=rows[-1]["expiration"],
        activation_utc=iso(rows[-1]["activation"]), expiration_utc=iso(rows[-1]["expiration"]),
        maturity_year=rows[-1]["maturity_year"], maturity_month=rows[-1]["maturity_month"],
        exchange=rows[-1]["exchange"], group=rows[-1]["group"], asset=rows[-1]["asset"],
        security_type=rows[-1]["security_type"], instrument_class=rows[-1]["instrument_class"],
        leg_count=rows[-1]["leg_count"], definition_messages=len(rows)) for iid, rows in definitions.items()}
    inventory = Counter()
    groups = defaultdict(list)
    stat_count = 0
    with STREAM.open("w") as stream:
        for x in db.DBNStore.from_file(RUN / "02-statistics.dbn.zst"):
            stat_count += 1
            typ = int(x.stat_type)
            inventory[str(typ)] += 1
            if typ != 6: continue
            row = dict(instrument_id=x.instrument_id, raw_symbol=definitions[x.instrument_id][-1]["raw_symbol"] if x.instrument_id in definitions else None,
                       ts_recv_ns=x.ts_recv, ts_event_ns=x.ts_event, ts_ref_ns=x.ts_ref,
                       quantity=x.quantity, price=x.price, stat_type=typ, sequence=x.sequence,
                       channel_id=x.channel_id, ts_in_delta=x.ts_in_delta,
                       update_action=int(x.update_action), stat_flags=x.stat_flags,
                       publisher_id=int(x.publisher_id))
            stream.write(json.dumps(row) + "\n")
            groups[(x.instrument_id, day(x.ts_ref))].append(row)
    for rows in groups.values(): rows.sort(key=lambda r: (r["ts_recv_ns"], r["sequence"], r["channel_id"]))
    volume_actions = Counter(str(r["update_action"]) for rows in groups.values() for r in rows)
    multi_message_groups = sum(len(rows) > 1 for rows in groups.values())
    expected = plan["date_coverage"]
    cells = []
    dates = []
    revision_events = []
    for entry in expected:
        target = entry["target_trade_date"]
        prior = entry["predecessor_cme_trade_date"]
        origin = ns(entry["forecast_origin_after_utc"])
        observed = {r["contract"]: r for r in entry["observed_prior_volume"]}
        date_cells = []
        for contract in entry["expected_target_outrights"]:
            matching = [iid for iid, code in contracts.items() if code == contract]
            iid = matching[0] if len(matching) == 1 else None
            defs = definitions.get(iid, []) if iid is not None else []
            at_origin = [r for r in defs if r["ts_recv"] <= origin]
            effective = at_origin[-1] if at_origin else None
            valid_identity = bool(effective and effective["exchange"] == "XCME" and effective["group"] == "NQ"
                                  and effective["asset"] == "NQ" and effective["security_type"] == "FUT"
                                  and effective["instrument_class"] == "F" and effective["leg_count"] == 0
                                  and effective["activation"] <= origin < effective["expiration"])
            messages = groups.get((iid, prior), []) if iid is not None else []
            valid = [r for r in messages if 0 <= r["quantity"] < SENTINEL and r["update_action"] != 3]
            first = valid[0] if valid else None
            latest = valid[-1] if valid else None
            asof = [r for r in valid if r["ts_recv_ns"] <= origin]
            prior_value = None
            for msg in valid:
                if prior_value is not None and msg["quantity"] != prior_value:
                    revision_events.append(dict(target_trade_date=target, predecessor_trade_date=prior,
                                                contract=contract, raw_symbol=msg["raw_symbol"],
                                                ts_recv_ns=msg["ts_recv_ns"], ts_event_ns=msg["ts_event_ns"],
                                                quantity=msg["quantity"], prior_quantity=prior_value,
                                                update_action=msg["update_action"], sequence=msg["sequence"],
                                                channel_id=msg["channel_id"], stat_flags=msg["stat_flags"]))
                prior_value = msg["quantity"]
            row = dict(target_trade_date=target, predecessor_trade_date=prior, origin_utc=entry["forecast_origin_after_utc"],
                       contract=contract, raw_symbol=defs[-1]["raw_symbol"] if defs else None, instrument_id=iid,
                       definition_at_origin=bool(effective), definition_identity_valid_at_origin=valid_identity,
                       definition_first_received_utc=iso(defs[0]["ts_recv"]) if defs else None,
                       definition_first_received_ns=defs[0]["ts_recv"] if defs else None,
                       cleared_message_count=len(messages), valid_cleared_message_count=len(valid),
                       explicit_zero=bool(valid and any(r["quantity"] == 0 for r in valid)),
                       first_cleared_quantity=first["quantity"] if first else None,
                       first_cleared_ts_recv_ns=first["ts_recv_ns"] if first else None,
                       first_cleared_ts_event_ns=first["ts_event_ns"] if first else None,
                       latest_in_window_quantity=latest["quantity"] if latest else None,
                       latest_in_window_ts_recv_ns=latest["ts_recv_ns"] if latest else None,
                       asof_origin_quantity=asof[-1]["quantity"] if asof else None,
                       asof_origin_ts_recv_ns=asof[-1]["ts_recv_ns"] if asof else None,
                       retained_globex_ohlcv_volume=observed.get(contract, {}).get("retained_volume_lower_bound"),
                       retained_globex_bar_count=observed.get(contract, {}).get("retained_bar_count"),
                       previously_unknown=contract in entry["missing_prior_volume_contracts"])
            cells.append(row); date_cells.append(row)
        retrospective = [r for r in date_cells if r["latest_in_window_quantity"] is not None and r["definition_identity_valid_at_origin"]]
        causal = [r for r in date_cells if r["asof_origin_quantity"] is not None and r["definition_identity_valid_at_origin"]]
        def winner(rows, field):
            return max(rows, key=lambda r: (r[field], r["contract"]))["contract"] if rows else None
        dates.append(dict(target_trade_date=target, predecessor_trade_date=prior, origin_utc=entry["forecast_origin_after_utc"],
                          expected_roster=entry["expected_target_outrights"],
                          definition_valid_count=sum(r["definition_identity_valid_at_origin"] for r in date_cells),
                          retrospective_numeric_count=len(retrospective), causal_numeric_count=len(causal),
                          retrospective_provisional_winner=winner(retrospective, "latest_in_window_quantity"),
                          retrospective_complete_winner=winner(retrospective, "latest_in_window_quantity") if len(retrospective)==9 else None,
                          causal_complete_winner=winner(causal, "asof_origin_quantity") if len(causal)==9 else None))
    if len(cells) != 1080 or sum(r["previously_unknown"] for r in cells) != 752:
        raise ValueError("Unexpected plan cell counts")
    result = dict(source=dict(run=str(RUN.relative_to(ROOT)), acquisition_sha256=sha(RUN / "acquisition.json"),
                              definition_dbn_sha256=sha(RUN / "01-definition.dbn.zst"),
                              statistics_dbn_sha256=sha(RUN / "02-statistics.dbn.zst"),
                              volume_stream_sha256=sha(STREAM)),
                  record_counts=dict(definition=definition_count, statistics=stat_count),
                  stat_type_inventory=dict(inventory), identities=identity, cells=cells, dates=dates,
                  quantity_revisions=revision_events,
                  summary=dict(expected_dates=len(dates), expected_cells=len(cells), previously_unknown_cells=752,
                               previously_unknown_with_numeric=sum(r["previously_unknown"] and r["latest_in_window_quantity"] is not None for r in cells),
                               previously_unknown_with_explicit_zero=sum(r["previously_unknown"] and r["explicit_zero"] for r in cells),
                               missing_cleared_cells=sum(r["latest_in_window_quantity"] is None for r in cells),
                               valid_roster_dates=sum(r["definition_valid_count"]==9 for r in dates),
                               retrospective_complete_dates=sum(r["retrospective_complete_winner"] is not None for r in dates),
                               causal_complete_dates=sum(r["causal_complete_winner"] is not None for r in dates),
                               cleared_quantity_revision_events=len(revision_events),
                               cleared_message_groups=len(groups), multi_message_cleared_groups=multi_message_groups,
                               cleared_update_actions=dict(volume_actions),
                               matched_globex_cells=sum(r["retained_globex_ohlcv_volume"] is not None and r["latest_in_window_quantity"] is not None for r in cells),
                               cleared_gt_retained_globex_cells=sum(r["retained_globex_ohlcv_volume"] is not None and r["latest_in_window_quantity"] is not None and r["latest_in_window_quantity"] > r["retained_globex_ohlcv_volume"] for r in cells),
                               cleared_eq_retained_globex_cells=sum(r["retained_globex_ohlcv_volume"] is not None and r["latest_in_window_quantity"] == r["retained_globex_ohlcv_volume"] for r in cells),
                               cleared_lt_retained_globex_cells=sum(r["retained_globex_ohlcv_volume"] is not None and r["latest_in_window_quantity"] is not None and r["latest_in_window_quantity"] < r["retained_globex_ohlcv_volume"] for r in cells)))
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__": main()
