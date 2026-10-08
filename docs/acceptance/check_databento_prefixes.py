"""Exercise production prefix behavior against independent raw arithmetic.
Run from repository root: .venv/bin/python -m docs.acceptance.check_databento_prefixes
"""
import json
import math
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from backtester.cli import objects, read_config
from backtester.rolls import ContinuousSeries, RollConfig
from backtester.volatility import RealizedVolatility

ROOT=Path(__file__).resolve().parents[2]
ID='20261007T233046211545Z'
NORM=ROOT/'data/normalized/databento/NQ'/ID
args=SimpleNamespace(data=NORM/'bars.csv',symbol='NQ',contract=None,interval=1)
config=read_config(NORM/'research-config.json')
_,calendar,provider=objects(args,config)
bars,_=provider.load()
raw_records=[json.loads(x) for x in (ROOT/'data/raw/databento/NQ'/ID/'ohlcv-1m.jsonl').read_text().splitlines()]
raw={(r['hd']['instrument_id'],int(r['hd']['ts_event'])):r for r in raw_records}

def calculate(panel,cutoff):
    stream=RealizedVolatility(calendar)
    series=ContinuousSeries(calendar,RollConfig(**config['roll']))
    last=None
    for item in series.select(panel):
        if item.raw.end>cutoff: break
        last=stream.update(item.raw,as_of=cutoff)
    return asdict(last)

results=[]
for text in ('2026-09-14T13:30:00+00:00','2026-09-14T13:31:00+00:00','2026-09-14T20:01:00+00:00','2026-09-14T22:01:00+00:00','2026-09-15T13:31:00+00:00','2026-09-20T22:01:00+00:00'):
    cutoff=datetime.fromisoformat(text)
    full=calculate(bars,cutoff)
    truncated=calculate(tuple(b for b in bars if b.end<=cutoff),cutoff)
    perturbed=tuple(replace(b,open=b.open+100,high=b.high+100,low=b.low+100,close=b.close+100,volume=b.volume+10000 if b.bar_state=="TRADED" else 0) if b.end>cutoff else b for b in bars)
    future=calculate(perturbed,cutoff)
    contract=full['contract']; ident={'NQU26':42004177,'NQZ26':261401}[contract]
    opened=calendar.bounds(full['trading_date'])[0]
    rr=[]; segments=[]; previous=None; t=opened
    while t<cutoff:
        r=raw[(ident,int(t.timestamp())*10**9)]
        op=int(r['open'])/10**9; close=int(r['close'])/10**9
        rr.append(math.log(close/(op if previous is None else previous)));previous=close
        segments.append(calendar.classify(t).session)
        t+=timedelta(minutes=1)
    rv=math.fsum(r*r for r in rr)
    bpv=math.pi/2*math.fsum(abs(rr[i]*rr[i-1]) for i in range(1,len(rr)) if segments[i]==segments[i-1]) if len(rr)>1 else None
    expected=dict(rv_1m=rv,bpv=bpv,jump=max(rv-bpv,0) if bpv is not None else None,rs_positive=math.fsum(r*r for r in rr if r>0),rs_negative=math.fsum(r*r for r in rr if r<0),quarticity=len(rr)/3*math.fsum(r**4 for r in rr))
    arithmetic=all(full[k] is None if v is None else math.isclose(full[k],v,rel_tol=1e-10,abs_tol=1e-16) for k,v in expected.items())
    results.append(dict(cutoff=text,contract=contract,n=len(rr),full_equals_truncated=full==truncated,full_equals_future_perturbed=full==future,independent_raw_arithmetic_matches=arithmetic,independent_values=expected))
result=dict(passed=all(r['full_equals_truncated'] and r['full_equals_future_perturbed'] and r['independent_raw_arithmetic_matches'] for r in results),results=results)
(Path(__file__).parent/'databento-2026-10-07-prefixes.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

raise SystemExit(0 if result["passed"] else 1)
