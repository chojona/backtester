"""Reproducible, read-only front-three NQ feasibility audit."""
from __future__ import annotations

import json
from collections import Counter

from audit_nq_causal_contract_selection import ROOT, build_register

OUTPUT = ROOT / "results/nq-front-three-selector-feasibility.json"
CANDIDATE = ROOT / "results/nq-w1-120-session-candidate.json"


def classify(cell: dict) -> str:
    if not cell["definition_identity_valid_at_origin"]:
        return "ineligible_or_not_yet_listed"
    if not cell["electronic_source_requested_all_segments"]:
        return "not_requested"
    if cell["retained_electronic_volume"] is None:
        return "requested_no_retained_bar"
    return "requested_observed_volume"


def main() -> None:
    # Rebuild predecessor totals directly from the immutable Parquet and exact
    # CME active segments. The legacy nine-contract output file is not read.
    base = build_register()
    candidate = json.loads(CANDIDATE.read_text())
    assert len(base["dates"]) == len(candidate["trade_dates"]) == 120
    dates = []
    coverage = Counter()
    for row in base["dates"]:
        front = row["candidates"][:3]
        assert len(front) == 3 and all(c["contract"] == row["rule_derived_roster"][i] for i, c in enumerate(front))
        cells = []
        for c in front:
            status = classify(c)
            coverage[status] += 1
            cells.append({
                "contract": c["contract"], "raw_symbol": c["raw_symbol"],
                "eligibility_definition_first_provider_receipt_utc": c["definition_first_provider_receipt_utc"],
                "eligibility_activation_utc": c["definition_activation_utc"],
                "eligibility_expiration_utc": c["definition_expiration_utc"],
                "classification": status,
                "request_manifests_by_predecessor_segment": c["electronic_source_segment_requests"],
                "predecessor_electronic_volume": c["retained_electronic_volume"],
                "predecessor_bar_count": c["retained_bar_count"],
                "last_bar_start_utc": c["last_bar_start_utc"],
                "last_observed_bar_completion_utc": c["last_observed_bar_completion_utc"],
                "electronic_provider_available_utc": c["electronic_volume_provider_available_utc"],
                "later_cleared_volume_diagnostic_only": c["later_cleared_volume"],
                "later_cleared_first_provider_receipt_utc": c["later_cleared_first_provider_receipt_utc"],
            })
        observed = [c for c in cells if c["classification"] == "requested_observed_volume"]
        rank = sorted(observed, key=lambda c: (c["predecessor_electronic_volume"], c["contract"]), reverse=True)
        unresolved = [c["contract"] for c in cells if c["classification"] != "requested_observed_volume"]
        conditional_winner = rank[0]["contract"] if not unresolved else None
        if conditional_winner is not None:
            comparison = "matches_legacy" if conditional_winner == row["historical_selected_contract"] else "differs_from_legacy"
        else:
            comparison = "indeterminate"
        reasons = []
        if unresolved:
            reasons.append("unknown_predecessor_electronic_volume:" + ",".join(unresolved))
            reasons.append("no_origin_available_upper_bound_for_unknown_competitor")
        reasons.extend(("full_venue_definition_book_not_independently_established",
                        "electronic_feed_completeness_not_independently_established",
                        "electronic_ohlcv_receipt_or_publication_by_5pm_origin_unrecorded"))
        dates.append({
            "target_trade_date": row["target_trade_date"],
            "predecessor_cme_trade_date": row["predecessor_cme_trade_date"],
            "predecessor_active_segments_utc": row["predecessor_active_segments_utc"],
            "predecessor_observation_complete_utc": row["predecessor_observation_complete_utc"],
            "decision_origin_utc": row["decision_origin_utc"],
            "front_three_roster": [c["contract"] for c in cells],
            "cells": cells,
            "observed_subset_rank": [{"contract": c["contract"], "volume": c["predecessor_electronic_volume"]} for c in rank],
            "unknown_competitors": unresolved,
            "conditional_exploratory_winner": conditional_winner,
            "legacy_selected_contract": row["historical_selected_contract"],
            "winner_comparison": comparison,
            "strictly_causally_validated": False,
            "evidence_gaps": reasons,
        })
    by_date = {r["target_trade_date"]: r for r in dates}
    trade_dates = [r["target_trade_date"] for r in dates]
    assert len(set(trade_dates)) == 120
    gaps = set(candidate["coverage"]["gapped_dates"])
    chronology = []
    for item in candidate["har"]["target_and_origin_rows"]:
        target = item["target_trade_date"]
        index = trade_dates.index(target)
        assert index >= 22
        window = trade_dates[index - 22:index + 1]
        unresolved_in_window = [day for day in window if by_date[day]["conditional_exploratory_winner"] is None]
        gaps_in_window = [day for day in window if day in gaps]
        chronology.append({
            "target_trade_date": target, "split": item["split"],
            "selector_window_trade_dates": window,
            "unresolved_selector_dates": unresolved_in_window,
            "retained_selected_bar_gap_dates": gaps_in_window,
            "selector_window_complete_under_ohlcv_assumption": not unresolved_in_window,
            "existing_selected_bar_grid_complete": not gaps_in_window,
            "full_row_supported_without_dropping_dates": not unresolved_in_window and not gaps_in_window,
        })
    assert len(chronology) == 98
    summary = {
        "target_dates": 120, "front_three_cells": 360,
        "coverage_counts": dict(coverage),
        "conditionally_ranked_dates": sum(r["conditional_exploratory_winner"] is not None for r in dates),
        "unresolved_dates": sum(r["conditional_exploratory_winner"] is None for r in dates),
        "conditional_winner_matches_legacy": sum(r["winner_comparison"] == "matches_legacy" for r in dates),
        "conditional_winner_differs_from_legacy": sum(r["winner_comparison"] == "differs_from_legacy" for r in dates),
        "winner_comparison_indeterminate": sum(r["winner_comparison"] == "indeterminate" for r in dates),
        "strictly_causally_validated_dates": 0,
        "har_potential_rows": len(chronology),
        "har_rows_with_unresolved_selector_window": sum(bool(r["unresolved_selector_dates"]) for r in chronology),
        "har_rows_with_retained_selected_bar_gap": sum(bool(r["retained_selected_bar_gap_dates"]) for r in chronology),
        "har_rows_supported_without_dropping_dates": sum(r["full_row_supported_without_dropping_dates"] for r in chronology),
        "har_rows_supported_without_dropping_dates_by_split": {split: sum(r["split"] == split and r["full_row_supported_without_dropping_dates"] for r in chronology)
                                                               for split in ("train", "validation", "test")},
    }
    result = {
        "schema_version": 1,
        "status": "NO_GO_existing_data_for_undropped_120_date_exploratory_series",
        "scope": "120 corrected CME trade dates, 2022-06-02 through 2022-11-21",
        "rule": "At predecessor close, three nearest unexpired March-cycle NQ quarters under the 2022-05-23 listing rule; descending (predecessor electronic volume, contract code) rank; target bars never enter eligibility",
        "ohlcv_availability_assumption": "Conditional ranks require all requested 1-minute Globex bars, any corrections, and their summed predecessor volume to have been available by 5 PM ET. Retained historical OHLCV has no original provider receipt/publication timestamps, so this assumption is unverified.",
        "known_limitations": ["Requested/no-bar does not prove zero", "Unrequested does not prove zero or nonlisting", "Later cleared volume is a different metric and was received after the origin", "A retrospective definition response is not a certified full as-of venue book", "Five retained selected-minute gaps and calendar guards remain independent HAR gates"],
        "source_sha256": base["source_sha256"],
        "electronic_request_manifest_sha256": base["electronic_request_manifest_sha256"],
        "summary": summary, "unresolved_target_dates": [r["target_trade_date"] for r in dates if r["conditional_exploratory_winner"] is None],
        "winner_differences": [r["target_trade_date"] for r in dates if r["winner_comparison"] == "differs_from_legacy"],
        "dates": dates, "har_chronology": chronology,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
