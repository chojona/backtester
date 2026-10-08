"""Report observed coverage separately from unacquired historical dates.
Never invent usable sessions from a weekday template or provider daily health.
"""
import argparse
from collections import Counter
from datetime import date,timedelta
import csv
import json
from pathlib import Path
from scripts.prepare_nq_history import ROOT,write
from backtester.providers.databento import hash_file


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--preparation',type=Path,default=ROOT/'results/databento-history-preparation')
    args=ap.parse_args(); out=args.preparation.resolve()
    if not out.is_relative_to(ROOT/'results'): raise ValueError('Report output must stay Git-ignored under results/')
    discovery=json.loads((out/'discovery.json').read_text())
    first=date.fromisoformat(discovery['earliest_trading_date']); last=date.fromisoformat(discovery['latest_complete_session'])
    evidence_path=ROOT/'docs/acceptance/databento-2026-10-07-evidence.json'
    evidence=json.loads(evidence_path.read_text())
    for path,h in evidence['hashes'].items():
        if hash_file(ROOT/path)!=h: raise ValueError('Existing acceptance input changed; rerun independent acceptance')
    if not evidence['all_offline_checks_pass']: raise ValueError('Existing acceptance has failed checks')
    known={r['day']:r for r in evidence['sessions']}
    rows=[]; day=first
    condition={r['date']:r['condition'] for r in discovery['latest_conditions']}
    while day<=last:
        key=day.isoformat(); accepted=known.get(key)
        rows.append(dict(date=key,status='EXISTING_ACCEPTED_SESSION' if accepted else 'NOT_ACQUIRED_CALENDAR_UNREVIEWED',contract=accepted['active'] if accepted else '',usable_session='yes' if accepted else 'unknown',observed_active_minutes=1380 if accepted else '',market_gap_minutes=0 if accepted else '',provider_utc_day_condition=condition.get(key,'')))
        day+=timedelta(days=1)
    with (out/'coverage-by-date.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=dict(status='PRE_ACQUISITION_COVERAGE_INCOMPLETE',earliest_trading_date=first.isoformat(),latest_elapsed_session=last.isoformat(),known_accepted_sessions=len(known),known_active_traded_minutes=1380*len(known),known_rolls=evidence['rolls'],known_panel_states=evidence['states'],known_missing_slots=69,rejected_observations_in_existing_accepted_active_series=0,full_history_usable_sessions=None,full_history_missing_intervals=None,full_history_rolls=None,full_history_rejected_observations=None,unacquired_calendar_dates=len(rows)-len(known),date_status_counts=dict(Counter(r['status'] for r in rows)),limitations=['Every calendar date is listed, including weekends and holidays, without asserting it should be an exchange session.','Unacquired dates are not classified as observed market-data gaps.','Newly acquired raw chunks remain pending calendar, normalization, overlap-deduplication and acceptance checks; this report does not count them as usable.','October 6 provider UTC-day condition is degraded; its session and adjacent UTC-day overlaps need investigation.'])
    write(out/'coverage-summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
