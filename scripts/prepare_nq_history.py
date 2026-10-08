"""Metadata-only, resumable full-history NQ acquisition preparation.
Never calls timeseries or batch endpoints. Credentials are never serialized.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
UTC=timezone.utc
NY=ZoneInfo('America/New_York')
SCHEMAS=('definition','ohlcv-1m')
MAX_COST=Decimal('85.00')

def iso(t): return t.isoformat()
def parse(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    tmp.replace(path)
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def credentials():
    key=os.environ.get('DATABENTO_API_KEY')
    if not key: raise RuntimeError('No local Databento credential available')
    return key

def client():
    import databento as db
    for name in ('databento','httpx','httpcore','urllib3'): logging.getLogger(name).setLevel(logging.CRITICAL)
    return db.Historical(key=credentials())

def request(start,end,schema):
    symbols=contracts(start,end)
    if schema=='definition':
        start=start.replace(hour=0,minute=0,second=0,microsecond=0)
        end=(end-timedelta(microseconds=1)).replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
    return dict(dataset='GLBX.MDP3',symbols=symbols,stype_in='raw_symbol',schema=schema,start=iso(start),end=iso(end))

def contracts(start,end):
    """Quarterly raw outright symbols spanning the chunk plus a roll successor."""
    candidates=[]
    for year in range(start.year-1,end.year+2):
        for month,code in ((3,'H'),(6,'M'),(9,'U'),(12,'Z')):
            first=date(year,month,1)
            expiry=first+timedelta(days=(4-first.weekday())%7+14)
            if expiry>=start.astimezone(NY).date()-timedelta(days=1):
                candidates.append((expiry,f'NQ{code}{year%10}'))
    candidates.sort()
    chosen=candidates[:3]
    if len(chosen)<2: raise ValueError('Need overlapping quarterly NQ contracts for chunk')
    return [symbol for _,symbol in chosen]

def all_quarterly_symbols(first,last):
    values=[]
    for y in range(first.year,last.year+2):
        for code in ('H','M','U','Z'): values.append(f'NQ{code}{y%10}')
    return sorted(set(values))

def chunks(first,last,days=90,buffer_days=7):
    """Core intervals contiguous at Sunday 18:00 NY; seven-day causal overlap.
    First core starts at the independently confirmed earliest NQ minute.
    """
    start=first; result=[]
    while start<last:
        proposed=(start.astimezone(NY)+timedelta(days=days)).astimezone(UTC)
        end=min(proposed,last)
        buffer=(start.astimezone(NY)-timedelta(days=buffer_days)).astimezone(UTC)
        fetch=max(first,buffer)
        reqs={s:request(fetch,end,s) for s in SCHEMAS}
        identity=digest(reqs)
        result.append(dict(chunk_id=identity[:16],request_sha256=identity,core_start=iso(start),core_end=iso(end),fetch_start=iso(fetch),fetch_end=iso(end),requests=reqs))
        start=end
    return result

def cached(out,name,operation):
    p=out/'metadata'/f'{name}.json'
    if p.exists(): return json.loads(p.read_text())['response']
    value=operation()
    write(p,dict(observed_at=iso(datetime.now(UTC)),response=value))
    return value

def discover(out):
    c=client()
    bounds=cached(out,'dataset-range',lambda:c.metadata.get_dataset_range(dataset='GLBX.MDP3'))
    earliest=parse(bounds['schema']['ohlcv-1m']['start'])
    day_end=earliest+timedelta(days=1)
    probe=dict(dataset='GLBX.MDP3',symbols=['NQM0'],stype_in='raw_symbol',schema='ohlcv-1m')
    def count(a,b):
        kwargs=dict(probe,start=iso(a),end=iso(b))
        return cached(out,'first-block-'+digest(kwargs),lambda:c.metadata.get_record_count(**kwargs))
    total=count(earliest,day_end)
    if total<=0: raise RuntimeError('Earliest dataset day has no confirmed NQM0 outright records; extend discovery explicitly')
    lo=earliest; hi=day_end
    while (hi-lo)>timedelta(minutes=10):
        mid=lo+timedelta(minutes=(int((hi-lo).total_seconds()//120)//10)*10)
        if count(lo,mid)>0: hi=mid
        else: lo=mid
    first=lo
    parent_before=dict(dataset='GLBX.MDP3',symbols=['NQ.FUT'],stype_in='parent',schema='ohlcv-1m',start=iso(earliest),end=iso(first))
    before=cached(out,'parent-before-first',lambda:c.metadata.get_record_count(**parent_before)) if first>earliest else 0
    if before: raise RuntimeError('NQ parent observations precede confirmed first outright; investigate before estimating')
    # Deliberately use provider schema availability, not the workstation clock.
    available=min(parse(bounds['schema'][s]['end']) for s in SCHEMAS)
    local_day=available.astimezone(NY).date()
    # Sample ends in ordinary October, with no holiday exception on this date.
    while True:
        close=datetime.combine(local_day,datetime.min.time(),NY).replace(hour=17).astimezone(UTC)
        if local_day.weekday()<5 and close<=available: break
        local_day-=timedelta(days=1)
    conditions=cached(out,'latest-conditions',lambda:c.metadata.get_dataset_condition(dataset='GLBX.MDP3',start_date=(local_day-timedelta(days=3)).isoformat(),end_date=local_day.isoformat()))
    last_probe=dict(dataset='GLBX.MDP3',symbols=['NQZ6'],stype_in='raw_symbol',schema='ohlcv-1m',start=iso(close-timedelta(minutes=10)),end=iso(close))
    last_count=cached(out,'latest-last-block',lambda:c.metadata.get_record_count(**last_probe))
    if last_count<=0: raise RuntimeError('Latest candidate session has no confirmed final-minute NQZ6 observation')
    summary=dict(dataset_range_start=iso(earliest),earliest_nq_10minute_block_start=iso(first),exact_first_bar_timestamp='PENDING_RAW_DOWNLOAD',earliest_probe=probe,earliest_day_record_count=total,earliest_trading_date=(first.astimezone(NY).date()+timedelta(days=1)).isoformat(),provider_available_through=iso(available),latest_complete_session=local_day.isoformat(),latest_complete_session_end=iso(close),latest_final_10minute_block_records=last_count,latest_conditions=conditions,discovery_limitations=['Earliest NQ outright availability confirmed to a ten-minute metadata block, not an exact one-minute timestamp or downloaded definition.','Latest close reviewed against ordinary October schedule; historical holiday calendars remain a separate validation gate.'])
    write(out/'discovery.json',summary)
    return first,close,summary

def estimate_chunk(out,chunk):
    c=client(); estimates={}; sizes={}; counts={}
    for schema,kwargs in chunk['requests'].items():
        try:
            estimate=cached(out,'cost-'+digest(kwargs),lambda kw=kwargs:c.metadata.get_cost(**kw))
            amount=Decimal(str(estimate))
            if not amount.is_finite() or amount<0: raise ValueError('Invalid provider cost estimate')
            estimates[schema]=str(amount)
            sizes[schema]=cached(out,'size-'+digest(kwargs),lambda kw=kwargs:c.metadata.get_billable_size(**kw))
            counts[schema]=cached(out,'count-'+digest(kwargs),lambda kw=kwargs:c.metadata.get_record_count(**kw))
        except ValueError:
            raise
        except Exception as error:
            raise RuntimeError(f'Metadata estimate failed: chunk={chunk["chunk_id"]} schema={schema} error={type(error).__name__}') from None
    total=sum(Decimal(x) for x in estimates.values())
    row=dict(chunk,estimates_usd=estimates,estimated_bytes=sizes,estimated_records=counts,total_cost_usd=str(total))
    write(out/'chunks'/f'{chunk["chunk_id"]}.json',row)
    return row

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'results/databento-history-preparation')
    ap.add_argument('--discovery-only',action='store_true')
    args=ap.parse_args(); out=args.output.resolve()
    if not out.is_relative_to(ROOT/'results'): raise ValueError('Generated estimates must remain under Git-ignored results/')
    first,last,discovery=discover(out)
    print(json.dumps(discovery,indent=2),flush=True)
    plan=chunks(first,last)
    write(out/'requests.json',dict(chunks=plan,schemas=SCHEMAS,billable_download_authorized=False))
    if args.discovery_only: return
    # Two workers, each with its own SDK client. Cache every successful metadata response.
    rows=[]
    with ThreadPoolExecutor(max_workers=1) as pool:
        for i,row in enumerate(pool.map(lambda x:estimate_chunk(out,x),plan),1):
            rows.append(row)
            if i%10==0 or i==len(plan): print(f'Estimated {i}/{len(plan)} chunks',flush=True)
    c=client(); full={}
    for schema in SCHEMAS:
        kwargs=request(first,last,schema)
        kwargs['symbols']=all_quarterly_symbols(first,last)
        full[schema]=cached(out,'full-'+digest(kwargs),lambda kw=kwargs:dict(cost_usd=c.metadata.get_cost(**kw),records=c.metadata.get_record_count(**kw),billable_bytes=c.metadata.get_billable_size(**kw)))
    total=sum(Decimal(r['total_cost_usd']) for r in rows)
    by_schema={s:str(sum(Decimal(str(r['estimates_usd'][s])) for r in rows)) for s in SCHEMAS}
    estimated_bytes={s:sum(int(r['estimated_bytes'][s]) for r in rows) for s in SCHEMAS}
    estimated_records={s:sum(int(r['estimated_records'][s]) for r in rows) for s in SCHEMAS}
    result=dict(version=1,prepared_at=iso(datetime.now(UTC)),status='AWAITING_EXPLICIT_USER_COST_APPROVAL' if total<=MAX_COST else 'OVER_HARD_COST_LIMIT',billable_download_authorized=False,hard_maximum_cost_usd='85.00',discovery=discovery,core_days=90,overlap_calendar_days=7,schemas=SCHEMAS,selection='Explicit quarterly NQ raw_symbol outrights, with overlapping expirations for volume rolls; excludes spreads and unrelated outrights.',chunks=rows,total_cost_usd=str(total),cost_by_schema_usd=by_schema,estimated_bytes_by_schema=estimated_bytes,estimated_records_by_schema=estimated_records,full_range_without_chunk_overlap=full,limitations=['Provider estimate, not a guaranteed invoice or provider-enforced cap.','Costs include repeated seven-day buffers and whole-UTC-day definitions.','No existing licensed trial reuse credit assumed; no bulk/subscription discount guessed.','Metadata responses are checkpointed with observation timestamps; re-estimate if scope/account/pricing changes.','Historical calendars, general independent acceptance, and cross-chunk causal state require review before dataset acceptance.'])
    result['approval_sha256']=digest(result)
    write(out/'plan.json',result)
    print(json.dumps(dict(total_cost_usd=str(total),cost_by_schema_usd=by_schema,chunks=len(rows),approval_sha256=result['approval_sha256'],plan=str(out/'plan.json')),indent=2),flush=True)

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('Metadata preparation stopped:',str(e) if isinstance(e,RuntimeError) else type(e).__name__,'(successful responses retained)',flush=True)
        raise SystemExit(1) from None
