"""Execute a frozen history plan only after explicit human cost approval.
Resume skips hash-verified completed chunks. Partial chunks stop for review.
No normalization is attempted with an unreviewed historical calendar.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from decimal import Decimal
import json
from math import isfinite
from pathlib import Path
from datetime import datetime,timezone
import shutil

from scripts.prepare_nq_history import ROOT,client,digest,write
from backtester.providers.databento import DownloadRequest,HistoricalGateway,hash_file


def verify_plan(plan,approved_hash,approved_total):
    payload={k:v for k,v in plan.items() if k!='approval_sha256'}
    if digest(payload)!=approved_hash or approved_hash!=plan['approval_sha256']:
        raise ValueError('Plan changed or approval hash does not match')
    amount=Decimal(str(approved_total))
    if Decimal(plan['total_cost_usd'])>Decimal('85.00'):
        raise ValueError('Final plan exceeds the hard $85 estimated cumulative cost limit')
    if not amount.is_finite() or amount!=Decimal(plan['total_cost_usd']):
        raise ValueError('Approve the exact final plan total')
    if not plan['chunks'] or tuple(plan['schemas'])!=('definition','ohlcv-1m'):
        raise ValueError('Unsupported or empty plan')
    for chunk in plan['chunks']:
        p=chunk['requests']['ohlcv-1m']
        req=DownloadRequest(chunk['fetch_start'],chunk['fetch_end'],symbols=tuple(p['symbols']),stype_in=p['stype_in'],schemas=tuple(plan['schemas']))
        expected={s:req.kwargs(s) for s in plan['schemas']}
        if expected!=chunk['requests'] or digest(expected)!=chunk['request_sha256']:
            raise ValueError('Chunk request differs from immutable estimated request')
        if Decimal(chunk['total_cost_usd'])!=sum(Decimal(str(v)) for v in chunk['estimates_usd'].values()):
            raise ValueError('Chunk cost does not reconcile')
    if amount!=sum(Decimal(r['total_cost_usd']) for r in plan['chunks']):
        raise ValueError('Plan total does not reconcile')


def completed(raw,chunk,allow_interrupted=False):
    if not raw.exists(): return False
    manifest=raw/'manifest.json'
    if not manifest.exists():
        marker=raw/'failure.json'
        if allow_interrupted and marker.exists() and json.loads(marker.read_text()).get('status') in ('INTERRUPTED_BY_USER','FAILED'):
            return False
        raise ValueError('Partial raw chunk retained; review failure and new costs before any retry: '+raw.name)
    row=json.loads(manifest.read_text())
    if not row.get('download_complete') or row['request']!=chunk['requests']['ohlcv-1m']:
        raise ValueError('Completed chunk request/status mismatch')
    required={'request.json',*(f'{s}.{ext}' for s in ('definition','ohlcv-1m') for ext in ('dbn.zst','jsonl'))}
    if set(row['files'])!=required: raise ValueError('Chunk manifest file set mismatch')
    for name,h in row['files'].items():
        if Path(name).name!=name or hash_file(raw/name)!=h: raise ValueError('Completed raw chunk hash mismatch')
    return True


def reprice(gateway,chunk):
    """Refresh the only billable dimension before download; other estimates stay frozen."""
    requests={}
    for schema,kwargs in chunk['requests'].items():
        cost=gateway.call('cost estimate',gateway.client.metadata.get_cost,**kwargs)
        if not isinstance(cost,(int,float)) or not isfinite(cost) or cost<0:
            raise ValueError('Invalid provider cost estimate')
        requests[schema]=dict(request=kwargs,cost_usd=cost,
                              billable_bytes=chunk['estimated_bytes'][schema],
                              records=chunk['estimated_records'][schema])
    total=sum(Decimal(str(value['cost_usd'])) for value in requests.values())
    return dict(provider='Databento',requests=requests,total_cost_usd=float(total),
                note='Current official metadata.get_cost; size and record counts retained from frozen plan')


def prior_attempt_cost(root,partial):
    """Conservatively charge each retained interrupted/failed request at its full estimate."""
    paths=list((root/'interrupted-attempts').glob('*/request.json')) if (root/'interrupted-attempts').exists() else []
    paths.extend(root/row['chunk_id']/'request.json' for row in partial)
    total=Decimal('0')
    for path in paths:
        request=json.loads(path.read_text())
        total+=Decimal(str(request['estimate']['total_cost_usd']))
    return total


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--approved-plan-sha256',required=True,help='Supply only after the human approves this plan and total')
    ap.add_argument('--approved-total-usd',required=True)
    ap.add_argument('--execute-approved-download',action='store_true',help='Explicit billable action; otherwise performs offline preflight only')
    ap.add_argument('--resume-interrupted-chunks',action='store_true',help='Resume only user-interrupted chunks after repricing and cumulative retry-cost checks')
    args=ap.parse_args(); plan=json.loads(args.plan.read_text())
    verify_plan(plan,args.approved_plan_sha256,args.approved_total_usd)
    root=ROOT/'data/raw/databento/NQ/full-history'/plan['approval_sha256'][:16]
    # Fail before a network call if any retained chunk is partial/corrupt.
    remaining=[row for row in plan['chunks'] if not completed(root/row['chunk_id'],row,args.resume_interrupted_chunks)]
    partial=[row for row in remaining if (root/row['chunk_id']).exists()]
    print(f'{len(plan["chunks"])-len(remaining)} complete chunks verified; {len(remaining)} remaining',flush=True)
    if not args.execute_approved_download:
        print('OFFLINE PREFLIGHT ONLY: no network calls or billable downloads')
        return
    gateway=HistoricalGateway(client=client())
    # Reprice every remaining request before any time-series call. Never increase the approved ceiling.
    estimates={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending={pool.submit(reprice,gateway,row):row for row in remaining}
        for i,future in enumerate(as_completed(pending),1):
            row=pending[future]; estimate=future.result()
            current=sum(Decimal(str(x['cost_usd'])) for x in estimate['requests'].values())
            if current!=Decimal(row['total_cost_usd']):
                raise ValueError('Repriced chunk differs from the approved estimate; no download made. Prepare and approve a new plan.')
            estimates[row['chunk_id']]=estimate
            if i%10==0 or i==len(remaining): print(f'Repriced {i}/{len(remaining)} remaining chunks',flush=True)
    completed_cost=sum(Decimal(str(json.loads((root/r['chunk_id']/'manifest.json').read_text())['estimate']['total_cost_usd'])) for r in plan['chunks'] if (root/r['chunk_id']/'manifest.json').exists())
    prior_partial_cost=prior_attempt_cost(root,partial)
    remaining_cost=sum(Decimal(str(e['total_cost_usd'])) for e in estimates.values())
    projected=completed_cost+prior_partial_cost+remaining_cost
    if projected>Decimal(plan['hard_maximum_cost_usd']):
        raise ValueError('Cumulative acquisition plus retry estimate exceeds the hard $85 limit; no further data requested')
    archive_paths={}
    for row in partial:
        source=root/row['chunk_id']
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        destination=root/'interrupted-attempts'/f"{row['chunk_id']}-{stamp}"
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(source),str(destination))
        archive_paths[row['chunk_id']]=str(destination.relative_to(ROOT))
    write(ROOT/'results/databento-history-preparation'/'execution-approval.json',dict(approved_plan_sha256=args.approved_plan_sha256,approved_total_usd=args.approved_total_usd,started_at=datetime.now(timezone.utc).isoformat(),remaining_chunks=len(remaining),completed_estimated_cost_usd=str(completed_cost),prior_interrupted_estimate_usd=str(prior_partial_cost),repriced_remaining_usd=str(remaining_cost),projected_cumulative_estimate_usd=str(projected),hard_maximum_cost_usd=plan['hard_maximum_cost_usd'],archived_interrupted_attempts=archive_paths,note='Local record of explicitly supplied human approval, not a provider-enforced invoice cap'))
    for i,row in enumerate(remaining,1):
        p=row['requests']['ohlcv-1m']
        req=DownloadRequest(row['fetch_start'],row['fetch_end'],symbols=tuple(p['symbols']),stype_in=p['stype_in'],schemas=tuple(plan['schemas']))
        metadata=gateway.metadata(req)
        # Gateway writes original compressed DBN, fixed-point JSONL, immutable request,
        # final hashed manifest; keeps failure markers/partial data without retry.
        gateway.download(req,root/row['chunk_id'],estimates[row['chunk_id']],metadata)
        print(f'Completed {i}/{len(remaining)} remaining chunks: {row["chunk_id"]}',flush=True)
    print('RAW_ACQUIRED_PENDING_CALENDAR_AND_ACCEPTANCE: no trading/forecasting performed')

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('Acquisition stopped:',type(e).__name__,str(e) if isinstance(e,ValueError) else '(provider diagnostics withheld)',flush=True)
        raise SystemExit(1) from None
