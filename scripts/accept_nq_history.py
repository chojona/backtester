"""Audit and consolidate the approved full-history Databento NQ acquisition.

The output stays under ignored results/. This audit validates retained raw files,
deduplicates exact chunk overlaps, and computes selected-contract session measures.
It deliberately refuses to certify schedule completeness without a reviewed dated
CME calendar.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/databento/NQ/full-history/8c2dcea828fa59a0'
OUT = ROOT / 'results/databento-nq-full-history'
NY = ZoneInfo('America/New_York')
NANO = 1_000_000_000
TICK = re.compile(r'^NQ([HMUZ])(\d{1,4})$')
MONTHS = {'H': 3, 'M': 6, 'U': 9, 'Z': 12}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def ns_dt(n: int) -> datetime:
    return datetime.fromtimestamp(n / NANO, timezone.utc)


def trading_date(stamp: datetime) -> date:
    local = stamp.astimezone(NY)
    return local.date() + timedelta(days=1) if local.hour >= 18 else local.date()


def quarter_definition(record):
    raw = str(record.get('raw_symbol', '')).rstrip('\x00')
    m = TICK.fullmatch(raw)
    if not m or record.get('instrument_class') != 'F':
        return None
    exp = record.get('expiration')
    if exp is None or int(exp) >= 2**64 - 1:
        raise ValueError(f'No finite expiration in definition for {raw}')
    expiry = ns_dt(int(exp))
    year = expiry.year
    suffix = m.group(2)
    if not str(year).endswith(suffix) or MONTHS[m.group(1)] != expiry.month:
        raise ValueError(f'Raw symbol/expiration mismatch for {raw}')
    if record.get('exchange') != 'XCME' or record.get('currency') != 'USD' or int(record.get('leg_count', 0)) != 0:
        raise ValueError(f'Unexpected NQ definition metadata for {raw}')
    return dict(raw_symbol=raw, expiration=expiry.isoformat(), contract=f'NQ{m.group(1)}{year % 100:02d}')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifests = sorted(RAW.glob('*/manifest.json'))
    if len(manifests) != 67:
        raise ValueError(f'Expected 67 completed chunks, found {len(manifests)}')
    chunk_info = []
    warnings = defaultdict(set)
    provider_conditions = {}
    definitions = {}
    raw_rows = 0
    integrity_errors = []
    provenance = []
    discovery_path = ROOT / 'results/databento-history-preparation/discovery.json'
    discovery = json.loads(discovery_path.read_text())
    for mp in manifests:
        m = json.loads(mp.read_text())
        cid = mp.parent.name
        if not m.get('download_complete') or m.get('provider') != 'Databento' or m['request']['dataset'] != 'GLBX.MDP3':
            raise ValueError(f'Incomplete or unexpected manifest: {cid}')
        provenance.append(dict(chunk_id=cid,manifest_sha256=sha(mp),request=m['request'],raw_files=m['files']))
        for name, expected in m['files'].items():
            p = mp.parent / name
            if not p.is_file() or sha(p) != expected:
                integrity_errors.append(f'{cid}/{name}: missing or checksum mismatch')
        for c in m.get('conditions', []):
            provider_conditions[c['date']] = c.get('condition', 'unknown')
            if c.get('condition') != 'available':
                warnings[c['date']].add(c.get('condition', 'unknown'))
        for line in (mp.parent / 'definition.jsonl').open():
            r = json.loads(line)
            d = quarter_definition(r)
            if d is None:
                continue
            iid = int(r['hd']['instrument_id'])
            prior = definitions.get(iid)
            if prior and (prior['raw_symbol'], prior['expiration']) != (d['raw_symbol'], d['expiration']):
                raise ValueError(f'Conflicting point-in-time identity for instrument id {iid}')
            definitions[iid] = d
        chunk_info.append((cid, mp.parent, m))
    if integrity_errors:
        raise ValueError('\n'.join(integrity_errors[:20]))
    condition_inconsistencies=[]
    for row in discovery.get('latest_conditions', []):
        day=row['date']; earlier=row.get('condition'); current=provider_conditions.get(day)
        if earlier and current and earlier!=current:
            item=dict(date=day,discovery_condition=earlier,download_manifest_condition=current,
                      discovery_last_modified=row.get('last_modified_date'))
            condition_inconsistencies.append(item)
            warnings[day].add(f"discovery_condition_mismatch:{earlier}->{current}")

    dbpath = OUT / 'dedup.sqlite3'
    if dbpath.exists():
        dbpath.unlink()
    con = sqlite3.connect(dbpath)
    con.execute('PRAGMA journal_mode=OFF')
    con.execute('PRAGMA synchronous=OFF')
    con.execute('PRAGMA temp_store=FILE')
    con.execute('''CREATE TABLE bars(ts INTEGER NOT NULL, iid INTEGER NOT NULL, op INTEGER NOT NULL,
        hi INTEGER NOT NULL, lo INTEGER NOT NULL, cl INTEGER NOT NULL, vol INTEGER NOT NULL,
        PRIMARY KEY(ts,iid)) WITHOUT ROWID''')
    exact_dups = 0
    rejected = Counter()
    insert_sql = 'INSERT OR IGNORE INTO bars VALUES(?,?,?,?,?,?,?)'
    for ci, (cid, folder, manifest) in enumerate(chunk_info, 1):
        pending = []
        for line in (folder / 'ohlcv-1m.jsonl').open():
            r = json.loads(line); hd = r.get('hd', {})
            ts, iid = int(hd['ts_event']), int(hd['instrument_id'])
            raw_rows += 1
            d = definitions.get(iid)
            if d is None:
                rejected['no_quarterly_outright_definition'] += 1
                continue
            if d['raw_symbol'] not in manifest['request']['symbols']:
                rejected['symbol_not_in_chunk_request'] += 1
                continue
            if ts % (60 * NANO):
                rejected['unaligned_timestamp'] += 1
                continue
            op, hi, lo, cl, vol = (int(r[k]) for k in ('open','high','low','close','volume'))
            if min(op,hi,lo,cl) <= 0 or hi < max(op,lo,cl) or lo > min(op,hi,cl) or vol <= 0:
                rejected['invalid_ohlcv'] += 1
                continue
            pending.append((ts,iid,op,hi,lo,cl,vol))
        before = con.total_changes
        con.executemany(insert_sql, pending)
        inserted = con.total_changes - before
        exact_dups += len(pending) - inserted
        # Verify ignored key collisions are exact, not conflicting payloads.
        if inserted < len(pending):
            for row in pending:
                found = con.execute('SELECT op,hi,lo,cl,vol FROM bars WHERE ts=? AND iid=?', row[:2]).fetchone()
                if found != row[2:]:
                    raise ValueError(f'Conflicting duplicate across chunks at {row[:2]}')
        con.commit()
        print(f'Consolidated {ci}/{len(chunk_info)} chunks', flush=True)

    # Select each session's highest-volume quarterly outright. No adjusted prices are written.
    by_day_contract = defaultdict(int)
    # Read chronologically in bounded batches, retaining only daily groups in memory.
    cur = con.execute('SELECT ts,iid,op,hi,lo,cl,vol FROM bars ORDER BY ts,iid')
    parquet_path = OUT / 'nq_outright_ohlcv_1m.parquet'
    schema = pa.schema([
        ('ts_event_ns', pa.int64()), ('timestamp_utc', pa.timestamp('ns', tz='UTC')),
        ('trading_date', pa.date32()), ('instrument_id', pa.int64()), ('raw_symbol', pa.string()),
        ('contract', pa.string()), ('open', pa.float64()), ('high', pa.float64()),
        ('low', pa.float64()), ('close', pa.float64()), ('volume', pa.int64()),
    ])
    writer = pq.ParquetWriter(parquet_path, schema, compression='zstd')
    batch = []
    while True:
        rows = cur.fetchmany(100_000)
        if not rows: break
        for ts,iid,op,hi,lo,cl,vol in rows:
            stamp = ns_dt(ts); td = trading_date(stamp); d = definitions[iid]
            batch.append((ts, stamp, td, iid, d['raw_symbol'], d['contract'], *(x / 1e9 for x in (op,hi,lo,cl)), vol))
            key=(td,d['contract']);by_day_contract[key]+=vol
        columns = list(zip(*batch))
        arrays = [pa.array(columns[i], type=schema.field(i).type) for i in range(len(schema))]
        writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
        batch.clear()
    writer.close()

    days = sorted({d for d,_ in by_day_contract})
    selected = {}
    for i, day in enumerate(days):
        current_contracts = {c for d,c in by_day_contract if d == day}
        if i == 0:
            # No complete prior session exists at the history boundary. Use the
            # nearest listed expiration and flag this initial choice as provisional.
            selected[day] = min(current_contracts, key=lambda c: definitions[
                next(iid for iid, info in definitions.items() if info['contract'] == c)]['expiration'])
            continue
        prior = days[i-1]
        # Causal roll selection: the prior completed trading session's volume
        # leader determines today's active contract. If it has expired/disappeared,
        # choose the highest prior-session-volume contract available today.
        selected[day] = max(current_contracts, key=lambda c:(by_day_contract.get((prior,c),0),c))
    roll_rows=[]
    for prior, current in zip(days,days[1:]):
        if selected[prior] != selected[current]:
            old, new = selected[prior], selected[current]
            # Paired-minute evidence is queried by the contracts' instrument IDs below.
            old_ids=[iid for iid,d in definitions.items() if d['contract']==old]
            new_ids=[iid for iid,d in definitions.items() if d['contract']==new]
            left=datetime.combine(current-timedelta(days=1),datetime.min.time(),NY).replace(hour=18).astimezone(timezone.utc)
            right=datetime.combine(current,datetime.min.time(),NY).replace(hour=17).astimezone(timezone.utc)
            lo_ns=int(left.timestamp()*NANO); hi_ns=int(right.timestamp()*NANO)
            paired=set()
            if old_ids and new_ids:
                placeholders_old=','.join('?' for _ in old_ids); placeholders_new=','.join('?' for _ in new_ids)
                q=f'SELECT a.ts FROM bars a JOIN bars b ON a.ts=b.ts WHERE a.ts>=? AND a.ts<? AND a.iid IN ({placeholders_old}) AND b.iid IN ({placeholders_new})'
                paired={r[0] for r in con.execute(q,(lo_ns,hi_ns,*old_ids,*new_ids))}
            roll_rows.append(dict(from_date=prior.isoformat(),to_date=current.isoformat(),old_contract=old,new_contract=new,
                                  volume_old=by_day_contract[prior,old],volume_new=by_day_contract[prior,new],
                                  paired_minute_count=len(paired),artificial_cross_contract_return_used=False))
    measure_rows=[]; session_rows=[]
    for day in days:
        contract=selected[day]
        local_start=datetime.combine(day-timedelta(days=1),datetime.min.time(),NY).replace(hour=18)
        local_end=datetime.combine(day,datetime.min.time(),NY).replace(hour=17)
        ids=[iid for iid,d in definitions.items() if d['contract']==contract]
        placeholders=','.join('?' for _ in ids)
        start_ns=int(local_start.astimezone(timezone.utc).timestamp()*NANO)
        end_ns=int(local_end.astimezone(timezone.utc).timestamp()*NANO)
        rows=[(ns_dt(ts),op,hi,lo,cl,vol,iid) for ts,op,hi,lo,cl,vol,iid in con.execute(
            f'SELECT ts,op,hi,lo,cl,vol,iid FROM bars WHERE ts>=? AND ts<? AND iid IN ({placeholders}) ORDER BY ts',
            (start_ns,end_ns,*ids))] if ids else []
        expected=(local_end.astimezone(timezone.utc)-local_start.astimezone(timezone.utc)).total_seconds()/60
        stamps=[r[0] for r in rows]
        inside=[t for t in stamps if local_start.astimezone(timezone.utc)<=t<local_end.astimezone(timezone.utc)]
        if len(inside)!=len(rows): rejected['outside_nominal_eth_window'] += len(rows)-len(inside)
        utc_days={local_start.astimezone(timezone.utc).date().isoformat(),
                  (local_end.astimezone(timezone.utc)-timedelta(microseconds=1)).date().isoformat()}
        states=[provider_conditions.get(x) for x in utc_days]
        condition=';'.join(f'{d}:{provider_conditions[d]}' for d in sorted(utc_days) if d in provider_conditions and provider_conditions[d]!='available')
        condition_missing=any(x is None for x in states)
        if condition_missing:
            condition=(condition+';' if condition else '')+'missing_condition_metadata'
        # OHLCV is sparse for no-trade minutes; this exact-grid screen is conservative only,
        # and is not an exchange-calendar completeness assertion.
        complete=(len(inside)==int(expected) and all((b-a).total_seconds()==60 for a,b in zip(inside,inside[1:])))
        session_rows.append(dict(trading_date=day.isoformat(),selected_contract=contract,
            observed_minute_bars=len(inside),nominal_minutes=int(expected),provider_condition=condition or 'available_for_session_utc_days',
            session_open_utc=local_start.astimezone(timezone.utc).isoformat(),session_close_utc=local_end.astimezone(timezone.utc).isoformat(),
            utc_offset_at_open=str(local_start.utcoffset()),utc_offset_at_close=str(local_end.utcoffset()),
            nominal_minutes_without_trade_bar=max(int(expected)-len(inside),0),
            full_nominal_grid='yes' if complete else 'no',calendar_status='UNREVIEWED',
            acceptance='REJECTED_DEGRADED_OR_MISSING_PROVIDER_DAY' if condition else ('CANDIDATE_FULL_GRID_CALENDAR_UNREVIEWED' if complete else 'INCOMPLETE_OR_SHORT_SESSION_CALENDAR_UNREVIEWED')))
        if complete and not condition:
            prices=[r[4]/1e9 for r in rows]
            opens=[r[1]/1e9 for r in rows]
            rets=[math.log(prices[0]/opens[0])]+[math.log(b/a) for a,b in zip(prices,prices[1:])]
            rv=math.fsum(x*x for x in rets)
            bpv=(math.pi/2)*math.fsum(abs(a*b) for a,b in zip(rets,rets[1:]))
            pos=math.fsum(x*x for x in rets if x>0); neg=math.fsum(x*x for x in rets if x<0)
            rq=(len(rets)/3)*math.fsum(x**4 for x in rets)
            measure_rows.append(dict(trading_date=day.isoformat(),contract=contract,n=len(rets),rv=rv,bpv=bpv,
                                     jump=max(rv-bpv,0.0),positive_semivariance=pos,negative_semivariance=neg,quarticity=rq))

    with (OUT/'coverage-by-session.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(session_rows[0]));w.writeheader();w.writerows(session_rows)
    with (OUT/'rolls.csv').open('w',newline='') as f:
        fields=list(roll_rows[0]) if roll_rows else ['from_date','to_date','old_contract','new_contract','volume_old','volume_new','paired_minute_count','artificial_cross_contract_return_used']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(roll_rows)
    with (OUT/'volatility-by-session.csv').open('w',newline='') as f:
        fields=list(measure_rows[0]) if measure_rows else ['trading_date','contract','n','rv','bpv','jump','positive_semivariance','negative_semivariance','quarticity']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(measure_rows)

    condition_dates=sorted(warnings)
    summary=dict(status='FAIL_ACCEPTANCE_CALENDAR_AND_SOURCE_LIMITATIONS',
        source='Databento Historical API GLBX.MDP3 / ohlcv-1m / quarterly NQ raw_symbol outrights',
        approval_plan_sha256='8c2dcea828fa59a01f0de998f02ea3e432b1f25b119ba79fbbf6eacc0ff87ab4',
        complete_chunks=len(manifests),raw_ohlcv_rows=raw_rows,deduplicated_exact_overlap_rows=exact_dups,
        output_rows= sum(1 for _ in []) , output_parquet=str(parquet_path.relative_to(ROOT)),
        earliest_request=min(m['request']['start'] for _,_,m in chunk_info),latest_request_end=max(m['request']['end'] for _,_,m in chunk_info),
        retained_usable_session_candidates=len(measure_rows),observed_trading_dates=len(days),roll_count=len(roll_rows),
        roll_boundaries=roll_rows,rejected_observations=dict(rejected),degraded_provider_dates=condition_dates,
        degraded_provider_conditions={k:sorted(v) for k,v in sorted(warnings.items())},
        source_condition_inconsistencies=condition_inconsistencies,
        session_acceptance_counts=dict(Counter(r['acceptance'] for r in session_rows)),
        source_manifest_provenance=provenance,
        checks=dict(raw_checksums='PASS',ohlcv_fixed_point_integrity='PASS' if not rejected else 'REVIEW',
                    cross_chunk_duplicates='PASS_EXACT_ONLY',contract_roll_selection='CANDIDATE_VOLUME_RULE',
                    roll_return_handling='PASS_NO_CROSS_CONTRACT_RETURN',dst='NOT_ACCEPTED_WITHOUT_DATED_CME_CALENDAR',
                    holidays_early_closes='NOT_ACCEPTED_WITHOUT_DATED_CME_CALENDAR',minute_completeness='NOT_PROVEN_BY_OHLCV_ABSENCE'),
        actual_provider_billing='UNVERIFIED; account billing endpoint was unauthorized',
        cumulative_quoted_cost_usd='26.666735831644',conservative_estimated_retry_total_usd='27.390109136697',hard_cap_usd='85.00',
        unresolved_limitations=[
            'No authoritative day-by-day CME historical schedule is retained for 2010-06-06 through 2026-10-06; DST, holidays, and early closes therefore remain unaccepted.',
            'Databento UTC-day condition metadata is provider-level and does not prove minute-level completeness; absent OHLCV bars can mean no trades.',
            'Degraded condition dates must be rejected pending source review; condition metadata cannot establish all individual missing intervals.',
            'Provider billing/account credits could not be verified; quote-based cumulative estimate stays below the approved $85 ceiling.',
            'Volatility CSV includes only 1,380-minute regular-grid candidate sessions and excludes degraded days; it does not certify the full history.',
            'The first session has no prior-session volume buffer; its initial nearest-expiration selection is provisional.',
        ],artifacts=[str((OUT/'coverage-by-session.csv').relative_to(ROOT)),str((OUT/'rolls.csv').relative_to(ROOT)),
                    str((OUT/'volatility-by-session.csv').relative_to(ROOT)),str(parquet_path.relative_to(ROOT))])
    import pyarrow.parquet as parquet
    summary['output_rows']=parquet.ParquetFile(parquet_path).metadata.num_rows
    summary['consolidated_parquet_sha256']=sha(parquet_path)
    observed_times=parquet.read_table(parquet_path,columns=['timestamp_utc'])['timestamp_utc']
    summary['earliest_observed_bar_utc']=observed_times[0].as_py().isoformat()
    summary['latest_observed_bar_utc']=observed_times[-1].as_py().isoformat()
    con.close(); dbpath.unlink()
    (OUT/'acceptance-report.json').write_text(json.dumps(summary,indent=2)+'\n')
    report=['# Full-history Databento NQ acceptance report','',f"**{summary['status']}**",'',
        f"The approved acquisition retained {len(manifests)} complete chunks, {raw_rows:,} raw OHLCV rows, and {summary['output_rows']:,} deduplicated quarterly-outright bars from {days[0]} through {days[-1]}. Raw checksums and exact overlap reconciliation passed.", '',
        f"Causal volume selection uses the prior completed session to choose the next session's contract and produced {len(roll_rows)} candidate roll boundaries. The first session uses the nearest listed expiration because no prior history buffer exists. The independent return calculations only use within-contract returns; no roll-spread return is introduced. {len(measure_rows):,} regular-grid session candidates have RV, BPV, jump proxy, signed semivariances, and quarticity in the companion CSV.", '',
        f"Provider condition or source-history evidence was degraded/inconsistent on {len(condition_dates)} distinct UTC dates. Sessions overlapping those dates are rejected and excluded from the volatility table. The cached discovery snapshot and final chunk manifest disagree for {len(condition_inconsistencies)} date(s).", '',
        'Acceptance remains FAIL because the repository has no authoritative dated CME schedule covering this full span. Consequently historical DST transitions, holidays, early closes, and short-session completeness cannot be distinguished reliably from provider gaps or ordinary no-trade minutes. The raw data and candidate dataset are preserved for review; they are not certified as a complete research-ready session panel.', '',
        f"Cost: current quotes reconcile to ${summary['cumulative_quoted_cost_usd']}; conservatively including retained interrupted attempts projects ${summary['conservative_estimated_retry_total_usd']} against the approved $85 ceiling. Actual account billing and credits remain unverified.", '',
        'No forecasting models or execution changes were made.']
    (OUT/'acceptance-report.md').write_text('\n'.join(report)+'\n')
    print(json.dumps({k:summary[k] for k in ('status','complete_chunks','raw_ohlcv_rows','output_rows','deduplicated_exact_overlap_rows','observed_trading_dates','retained_usable_session_candidates','roll_count','degraded_provider_dates')},indent=2))


if __name__ == '__main__':
    main()
