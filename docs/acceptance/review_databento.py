"""Independent offline acceptance arithmetic. No backtester production imports.
Run from repository root: .venv/bin/python docs/acceptance/review_databento.py
"""
import csv
import hashlib
import json
import math
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
import databento as db

ROOT = Path(__file__).resolve().parents[2]
ID = '20261007T233046211545Z'
RAW = ROOT / 'data/raw/databento/NQ' / ID
NORM = ROOT / 'data/normalized/databento/NQ' / ID
REPORT = ROOT / 'results/databento-acceptance' / ID
OUT = Path(__file__).parent
ET = ZoneInfo('America/New_York')
UTC = timezone.utc

def load(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def stamp(ns):
    seconds, nanos = divmod(int(ns), 10**9)
    assert nanos == 0
    return datetime.fromtimestamp(seconds, UTC)

def local(day, hhmm):
    return datetime.fromisoformat(f'{day}T{hhmm}').replace(tzinfo=ET).astimezone(UTC)

checks = []
def check(name, value, detail=None):
    checks.append(dict(check=name, passed=bool(value), detail=detail))

manifest, meta = load(RAW/'manifest.json'), load(NORM/'metadata.json')
files = {str(p.relative_to(ROOT)): sha(p) for p in [*RAW.iterdir(), *NORM.iterdir(), *REPORT.iterdir(), ROOT/'calendars/nq-2026-09-validation.json', ROOT/'calendars/sources/review.md'] if p.is_file()}
check('raw manifest hashes', all(sha(RAW/n)==h for n,h in manifest['files'].items()))
check('sidecar source and normalized hashes', sha(RAW/'manifest.json')==meta['raw_manifest_sha256'] and sha(NORM/'bars.csv')==meta['normalized_sha256'] and all(sha(RAW/n)==h for n,h in meta['source_hashes'].items()))
raws = {}
for schema in ('definition','ohlcv-1m','statistics'):
    retained = [json.loads(x) for x in (RAW/f'{schema}.jsonl').read_text().splitlines()]
    store = db.DBNStore.from_file(RAW/f'{schema}.dbn.zst')
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp)/'decoded.jsonl'
        store.to_json(p, pretty_px=False, pretty_ts=False, map_symbols=False)
        decoded=[json.loads(x) for x in p.read_text().splitlines()]
    check(f'{schema} DBN independently decoded equals retained JSONL', decoded==retained, len(retained))
    check(f'{schema} metadata untruncated', not store.metadata.partial and not store.metadata.not_found and store.metadata.limit is None)
    raws[schema]=retained
rows=list(csv.DictReader((NORM/'bars.csv').open()))
raw_index={(int(r['hd']['instrument_id']),int(r['hd']['ts_event'])):r for r in raws['ohlcv-1m']}
check('raw OHLCV keys unique',len(raw_index)==len(raws['ohlcv-1m']))
contracts={c['contract']:c for c in meta['contracts']}
idmap={c['instrument_id']:c['contract'] for c in meta['contracts']}
for c, info in contracts.items():
    versions=[r for r in raws['definition'] if r['hd']['instrument_id']==info['instrument_id']]
    initial=min(versions,key=lambda r:max(int(r['hd']['ts_event']),int(r['ts_recv'])))
    expiry_ns=int(initial['expiration'])
    seconds,nanos=divmod(expiry_ns,10**9)
    expiry=datetime.fromtimestamp(seconds,UTC)
    available_ns=max(int(initial['hd']['ts_event']),int(initial['ts_recv']))
    available=datetime.fromtimestamp(available_ns//10**9,UTC)+timedelta(microseconds=((available_ns%10**9)+999)//1000)
    check(f'{c} raw definition economics expiry and causal availability',
          nanos==0 and initial['raw_symbol']==info['raw_symbol'] and initial['instrument_class']=='F'
          and initial['security_type']=='FUT' and initial['exchange']=='XCME' and initial['currency']=='USD'
          and int(initial['min_price_increment'])==250000000 and int(initial['unit_of_measure_qty'])==20000000000
          and expiry.isoformat()==info['expiration'] and available.isoformat()==info['available_at']
          and available<datetime.fromisoformat(manifest['request']['start']),
          dict(expiration=expiry.isoformat(),available_at=available.isoformat(),versions=len(versions)))
normalized={}
errors=[]
carried=0
last={}
for row in rows:
    t=datetime.fromisoformat(row['timestamp']); c=row['contract']; ident=int(row['instrument_id'])
    check_key=(c,t)
    if check_key in normalized: errors.append(['duplicate',c,str(t)])
    normalized[check_key]=row
    if row['bar_state']=='TRADED':
        ns=int(row['source_ts_event_ns']); source=raw_index.get((ident,ns))
        valid=source is not None and stamp(ns)==t and idmap[ident]==c and row['raw_symbol']==contracts[c]['raw_symbol'] and row['published']=='True'
        valid=valid and all(Decimal(row[k])==Decimal(source[k])/10**9 for k in ('open','high','low','close')) and Decimal(row['volume'])==Decimal(source['volume'])
        if not valid: errors.append(['raw mismatch',c,str(t)])
        last[c]=Decimal(row['close'])
    else:
        carried+=1
        valid=row['bar_state']=='NO_TRADE' and row['published']=='False' and not row['source_ts_event_ns'] and Decimal(row['volume'])==0 and all(Decimal(row[k])==last.get(c) for k in ('open','high','low','close'))
        valid=valid and (ident,int(t.timestamp())*10**9) not in raw_index
        if not valid: errors.append(['carry mismatch',c,str(t)])
check('all normalized OHLCV timestamp ID symbol and carries',not errors,dict(rows=len(rows),traded=len(rows)-carried,carried=carried,errors=errors[:20]))
cal=load(ROOT/'calendars/nq-2026-09-validation.json')
sessions=[]; previous_volumes=None; active='NQU26'; rolls=[]; arithmetic=[]; coverage=[]; boundary_samples=[]
existing={r['trading_date']:r for r in load(REPORT/'volatility.json')['records']}
selected_keys=set()
for day in cal['dates']:
    d=datetime.fromisoformat(day).date()
    opened=local(d-timedelta(days=1),'18:00'); closed=local(day,'17:00')
    rth=local(day,'09:30'); post=local(day,'16:00')
    grid=[opened+timedelta(minutes=i) for i in range(1380)]
    check(f'{day} EDT and 23-hour schedule',opened.astimezone(ET).utcoffset()==timedelta(hours=-4) and closed-opened==timedelta(minutes=1380))
    daily={}
    for c,definition in contracts.items():
        expiry=datetime.fromisoformat(definition['expiration'])
        eligible=[t for t in grid if t<expiry]
        present=[normalized[(c,t)] for t in eligible if (c,t) in normalized]
        counts=Counter(r['bar_state'] for r in present)
        missing=[t.isoformat() for t in eligible if (c,t) not in normalized]
        daily[c]=sum(int(Decimal(r['volume'])) for r in present)
        coverage.append(dict(day=day,contract=c,eligible_minutes=len(eligible),observed=len(present),states=dict(counts),missing_minutes=len(missing),missing_first=missing[:3]))
    ordered=sorted(contracts,key=lambda c:contracts[c]['expiration'])
    ix=ordered.index(active)
    if previous_volumes and ix+1<len(ordered) and previous_volumes[ordered[ix+1]]>previous_volumes[active]:
        candidate=ordered[ix+1]
        pair=next(t for t in grid if all(normalized.get((c,t),{}).get('bar_state')=='TRADED' for c in (active,candidate)))
        old=normalized[(active,pair)]; new=normalized[(candidate,pair)]
        rolls.append(dict(timestamp=pair.isoformat(),old_contract=active,new_contract=candidate,old_open=float(old['open']),new_open=float(new['open']),price_difference=float(new['open'])-float(old['open']),previous_session_volumes=previous_volumes))
        active=candidate
        check('roll obtains traded pair at session open',pair==opened)
    chosen=[raw_index[(contracts[active]['instrument_id'],int(t.timestamp())*10**9)] for t in grid]
    selected_keys.update((active,t) for t in grid)
    returns=[]; segments=[]; prev=None
    for t,bar in zip(grid,chosen):
        o=float(Decimal(bar['open'])/10**9); close=float(Decimal(bar['close'])/10**9)
        returns.append(math.log(close/(o if prev is None else prev)))
        prev=close
        segments.append('OVERNIGHT' if t<rth else 'RTH' if t<post else 'POST_RTH')
        if t in (opened,rth-timedelta(minutes=1),rth,post-timedelta(minutes=1),post,closed-timedelta(minutes=1)):
            boundary_samples.append(dict(timestamp=t.isoformat(),local=t.astimezone(ET).isoformat(),contract=active,segment=segments[-1],raw_ohlcv={k:str(Decimal(bar[k])/10**9) for k in ('open','high','low','close')},volume=int(bar['volume']),log_return=returns[-1]))
    rv=math.fsum(r*r for r in returns)
    bpv=math.pi/2*math.fsum(abs(returns[i]*returns[i-1]) for i in range(1,len(returns)) if segments[i]==segments[i-1])
    values=dict(rv_1m=rv,bpv=bpv,jump=max(rv-bpv,0),rs_positive=math.fsum(r*r for r in returns if r>0),rs_negative=math.fsum(r*r for r in returns if r<0),quarticity=len(returns)/3*math.fsum(r**4 for r in returns))
    for name in ('OVERNIGHT','RTH','POST_RTH'):
        values['rv_'+name.lower()]=math.fsum(r*r for r,s in zip(returns,segments) if s==name)
    for k in (5,15):
        coarse=[]
        for name in ('OVERNIGHT','RTH','POST_RTH'):
            rr=[r for r,s in zip(returns,segments) if s==name]
            coarse.extend(math.fsum(rr[i:i+k]) for i in range(0,len(rr)-k+1,k))
        values[f'rv_{k}m']=math.fsum(r*r for r in coarse)
    expected=existing[day]
    differences={k:values[k]-expected[k] for k in values}
    matches=all(math.isclose(values[k],expected[k],rel_tol=1e-10,abs_tol=1e-16) for k in values)
    check(f'{day} independently recalculated measurements',matches,differences)
    check(f'{day} active raw complete',len(chosen)==1380 and expected['session_complete'] and expected['contract']==active)
    arithmetic.append(dict(day=day,contract=active,n=len(returns),values=values,difference_from_retained=differences))
    sessions.append(dict(day=day,active=active,volumes=daily,first_return=returns[0]))
    previous_volumes=daily
reported_rolls=load(REPORT/'provider-audit.json')['rolls']
check('independent volume selection matches retained roll',len(rolls)==len(reported_rolls) and all(all(r[k]==s[k] for k in ('old_contract','new_contract','old_open','new_open','price_difference')) and datetime.fromisoformat(s['timestamp'])==datetime.fromisoformat(r['timestamp']) for r,s in zip(rolls,reported_rolls)))
# Expiry and out-of-session observations are checked directly against raw timestamps.
outside=[]; after_expiry=[]
for (ident,ns),bar in raw_index.items():
    if ident not in idmap: continue
    t=stamp(ns); c=idmap[ident]
    if t>=datetime.fromisoformat(contracts[c]['expiration']): after_expiry.append([c,t.isoformat()])
    if (c,t) not in normalized: outside.append([c,t.isoformat()])
check('all selected-panel raw records retained',not outside,outside[:20])
check('raw parent records reconcile with selected panel',len(raws['ohlcv-1m'])==len(rows)-carried+meta['excluded_non_nearby_or_non_outright'])
valid_keys=set()
for item in coverage:
    d=datetime.fromisoformat(item['day']).date()
    start=local(d-timedelta(days=1),'18:00')
    valid_keys.update((item['contract'],start+timedelta(minutes=i)) for i in range(item['eligible_minutes']))
check('all normalized timestamps inside eligible sessions',set(normalized)<=valid_keys)
check('missing states reconcile with absent eligible slots',len(valid_keys-set(normalized))==meta['states']['NO_TRADE_UNPRICED']==69 and all(c=='NQH27' for c,t in valid_keys-set(normalized)))
check('no selected-panel raw bars at or after expiry',not after_expiry,after_expiry[:20])
request=load(RAW/'request.json')
result=dict(status='PASS' if all(c['passed'] for c in checks) else 'FAIL',scope='Independent retained-data review, not independent market-source certification',checks=checks,all_offline_checks_pass=all(c['passed'] for c in checks),hashes=files,states=meta['states'],coverage=coverage,sessions=sessions,rolls=rolls,measurements=arithmetic,boundary_samples=boundary_samples,request_snapshot_download_complete=request['download_complete'],final_manifest_download_complete=manifest['download_complete'])
(OUT/'databento-2026-10-07-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(checks=len(checks),passed=sum(c['passed'] for c in checks),failures=[c for c in checks if not c['passed']],rolls=rolls,coverage=coverage),indent=2))

raise SystemExit(0 if result["all_offline_checks_pass"] else 1)
