"""Execute a frozen history plan only after explicit human cost approval.
Resume skips hash-verified completed chunks. Partial chunks stop for review.
No normalization is attempted with an unreviewed historical calendar.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
from datetime import datetime,timezone

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


def completed(raw,chunk):
    if not raw.exists(): return False
    manifest=raw/'manifest.json'
    if not manifest.exists(): raise ValueError('Partial raw chunk retained; review failure and new costs before any retry: '+raw.name)
    row=json.loads(manifest.read_text())
    if not row.get('download_complete') or row['request']!=chunk['requests']['ohlcv-1m']:
        raise ValueError('Completed chunk request/status mismatch')
    required={'request.json',*(f'{s}.{ext}' for s in ('definition','ohlcv-1m') for ext in ('dbn.zst','jsonl'))}
    if set(row['files'])!=required: raise ValueError('Chunk manifest file set mismatch')
    for name,h in row['files'].items():
        if Path(name).name!=name or hash_file(raw/name)!=h: raise ValueError('Completed raw chunk hash mismatch')
    return True


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--approved-plan-sha256',required=True,help='Supply only after the human approves this plan and total')
    ap.add_argument('--approved-total-usd',required=True)
    ap.add_argument('--execute-approved-download',action='store_true',help='Explicit billable action; otherwise performs offline preflight only')
    args=ap.parse_args(); plan=json.loads(args.plan.read_text())
    verify_plan(plan,args.approved_plan_sha256,args.approved_total_usd)
    root=ROOT/'data/raw/databento/NQ/full-history'/plan['approval_sha256'][:16]
    # Fail before a network call if any retained chunk is partial/corrupt.
    remaining=[row for row in plan['chunks'] if not completed(root/row['chunk_id'],row)]
    print(f'{len(plan["chunks"])-len(remaining)} complete chunks verified; {len(remaining)} remaining',flush=True)
    if not args.execute_approved_download:
        print('OFFLINE PREFLIGHT ONLY: no network calls or billable downloads')
        return
    gateway=HistoricalGateway(client=client())
    # Reprice every remaining request before any time-series call. Never increase the approved ceiling.
    estimates={}
    for row in remaining:
        p=row['requests']['ohlcv-1m']
        req=DownloadRequest(row['fetch_start'],row['fetch_end'],symbols=tuple(p['symbols']),stype_in=p['stype_in'],schemas=tuple(plan['schemas']))
        estimate=gateway.estimate(req)
        current=sum(Decimal(str(x['cost_usd'])) for x in estimate['requests'].values())
        if current>Decimal(row['total_cost_usd']):
            raise ValueError('Repriced chunk exceeds final approved estimate; no download made. Prepare and approve a new plan.')
        estimates[row['chunk_id']]=estimate
    write(ROOT/'results/databento-history-preparation'/'execution-approval.json',dict(approved_plan_sha256=args.approved_plan_sha256,approved_total_usd=args.approved_total_usd,started_at=datetime.now(timezone.utc).isoformat(),remaining_chunks=len(remaining),note='Local record of explicitly supplied human approval, not a provider-enforced invoice cap'))
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
