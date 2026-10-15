"""Inspect the frozen NQ research interface; no model or features are built."""
from collections import Counter

from backtester.nq_research_data import consecutive_windows, load_sessions


def main():
    strict = load_sessions("strict")
    conditional = load_sessions("conditional", allow_conditional=True)
    for name, sessions, policy in (("strict", strict, None),
                                   ("conditional", conditional, "release_chronology")):
        windows = consecutive_windows(sessions, 23, conditional_policy=policy)
        print(f"{name}: {len(sessions)} sessions, {len(windows)} consecutive 23-session windows")
        print(f"  availability: {dict(Counter(r.availability_status for r in sessions))}")
        if windows:
            first = windows[0]
            print(f"  first window: {first.observations[0].cme_trade_date} through "
                  f"{first.observations[-1].cme_trade_date}; "
                  f"{len(first.source_hashes)} sealed lineage entries")
    print("prospective: no sealed session estimator release configured")


if __name__ == "__main__":
    main()
