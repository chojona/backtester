from dataclasses import replace
from datetime import timedelta
import json
import math

import pytest

from backtester.rolls import SelectedBar
from backtester.sessions import SessionCalendar
from backtester.volatility_charts import prepare_sessions, render_charts, aggregate_ohlcv, _chart_payload
from conftest import make_bar


def selected(bars):
    return [SelectedBar(b, replace(b, open=b.open+100, close=b.close+100,
                                  high=b.high+100, low=b.low+100)) for b in bars]


def test_chart_returns_and_prices_use_raw_constituents():
    a = make_bar(opening=100, close=100*math.exp(.01))
    b = make_bar(a.end, opening=a.close, close=a.close*math.exp(-.02))
    groups = prepare_sessions(selected([a,b]), SessionCalendar())
    points = groups[0]['points']
    assert points[0]['close'] == a.close  # not adjusted research close
    assert points[0]['return'] == pytest.approx(.01)
    assert points[1]['return'] == pytest.approx(-.02)
    assert groups[0]['last'].observed_rv == pytest.approx(.0005)


def test_chart_gaps_and_unknowns_are_not_zero_returns():
    a = make_bar()
    b = make_bar(a.end+timedelta(minutes=1), opening=100, close=101)
    c = replace(make_bar(b.end), coverage_state='UNKNOWN')
    group = prepare_sessions(selected([a,b,c]), SessionCalendar())[0]
    points = group['points']
    assert points[1]['close'] is None and points[1]['record'] is None
    assert points[-1]['return'] is None and points[-1]['close'] is None
    assert group['last'].rv_1m is None


def test_chart_rolls_are_separate_and_future_does_not_change_prefixes():
    a = make_bar()
    b = make_bar(a.end, opening=1000,contract='ESH27')
    groups = prepare_sessions(selected([a,b]), SessionCalendar())
    assert len(groups) == 2
    assert groups[1]['points'][0]['return'] == 0
    assert groups[0]['points'] == prepare_sessions(selected([a]),SessionCalendar())[0]['points']


def test_chart_empty_input_rejected():
    with pytest.raises(ValueError,match='No completed bars'):
        prepare_sessions([],SessionCalendar())


def test_chart_export_preserves_nulls_and_local_assets(tmp_path):
    pytest.importorskip('matplotlib')
    groups = prepare_sessions(selected([make_bar()]),SessionCalendar())
    out = tmp_path/'charts'
    index = render_charts(groups,out,data_hash='fixture-only',calendar_source='synthetic test calendar')
    page = index.read_text()
    import re
    sources=re.findall(r'<script[^>]*src="([^"]+)"',page)
    assert sources and all(not source.startswith(('http:', 'https:')) for source in sources)
    assert 'id="session"' in page and 'assets/volatility_chart_ui.js' in page
    assert 'OHLC' in page and 'id="trading"' in page
    assert 'id="returns"' in page and 'id="profile"' in page
    assert '<p>' not in page and 'class="notice"' not in page
    assert 'data-interval="5"' in page
    assert (out/'overview/sampling.png').stat().st_size > 10000
    assert (out/'overview/sampling.svg').exists()
    assert 'id="overview-sampling"' in page
    assert (out/'assets/lightweight-charts-5.1.0.js').stat().st_size > 100000
    assert (out/'assets/lightweight-charts-LICENSE.txt').exists()
    import hashlib
    vendor=json.loads((out/'assets/lightweight-charts-source.json').read_text())
    assert hashlib.sha256((out/'assets/lightweight-charts-5.1.0.js').read_bytes()).hexdigest()==vendor['javascript_sha256']
    assert len(list((out/'sessions').glob('*-ohlcv.png'))) == 1
    saved = json.loads((out/'measurements.json').read_text())
    assert saved['records'][0]['rv_1m'] is None
    assert saved['records'][0]['observed_rv'] == 0
    assert saved['data_sha256'] == 'fixture-only'
    with pytest.raises(FileExistsError):
        render_charts(groups,out,data_hash='fixture-only',calendar_source='synthetic test calendar')


def test_ohlcv_aggregation_uses_exact_source_fields_and_volume():
    from datetime import date
    from backtester.sessions import local_at
    start=local_at(date(2026,1,4),'18:00')
    bars=[make_bar(start+timedelta(minutes=i),opening=100+i,high=103+i,
                   low=99+i,close=101+i,volume=10+i) for i in range(5)]
    group=prepare_sessions(selected(bars),SessionCalendar())[0]
    aggregated=aggregate_ohlcv(group['points'],5)
    assert aggregated == [[int(start.timestamp()*1000),100,107,99,105,60]]
    assert len(aggregate_ohlcv(group['points'],1)) == 5
    assert aggregate_ohlcv(group['points'],15) == []
    payload=_chart_payload([group])
    assert payload['sessions'][0]['bars']['5'] == aggregated
    assert payload['sessions'][0]['series'][0][1] == pytest.approx(math.log(101/100)*1e4)


def test_ohlcv_aggregation_never_bridges_gaps_unknowns_or_segments():
    from datetime import date
    from backtester.sessions import local_at
    start=local_at(date(2026,1,5),'09:25')
    bars=[make_bar(start+timedelta(minutes=i)) for i in range(15)]
    # Last 5m block is clean, first has a gap, second has unknown coverage.
    bars.pop(1)
    bars[5]=replace(bars[5],coverage_state='UNKNOWN')
    group=prepare_sessions(selected(bars),SessionCalendar())[0]
    result=aggregate_ohlcv(group['points'],5)
    assert len(result)==1 and result[0][0]==int((start+timedelta(minutes=10)).timestamp()*1000)
    assert aggregate_ohlcv(group['points'],15)==[]
    with pytest.raises(ValueError):
        aggregate_ohlcv(group['points'],2)


def test_native_chart_timeframe_replaces_price_and_volume_data(tmp_path):
    import shutil,subprocess
    from pathlib import Path
    from conftest import day_bars
    node=shutil.which('node')
    if not node: pytest.skip('Optional chart-controller test requires Node.js')
    groups=prepare_sessions(selected(day_bars(calendar=SessionCalendar(breaks=[]))),SessionCalendar(breaks=[]))
    payload=_chart_payload(groups)
    dataset=tmp_path/'chart-data.json'
    dataset.write_text(json.dumps(payload))
    adapter=Path(__file__).resolve().parents[1]/'backtester/volatility_chart_data.js'
    script=r"""
const assert=require('node:assert/strict');
const fs=require('node:fs');
const D=require(process.argv[1]);
const session=JSON.parse(fs.readFileSync(process.argv[2],'utf8')).sessions[0];
const before=JSON.stringify(session);
const received={};
const apis=Object.fromEntries(['candles','ohlc','volume'].map(key=>[key,{setData:points=>{received[key]=points}}]));
for(const [minutes,count] of [[1,1380],[5,276],[15,92],[1,1380]]){
 const result=D.applyTimeframe(session,minutes,apis);
 assert.equal(result.count,count);
 for(const key of Object.keys(apis))assert.equal(received[key].length,count);
 assert.deepEqual(received.candles,received.ohlc);
 assert.equal(received.volume[0].time,received.ohlc[0].time);
 assert.equal(received.volume.reduce((n,p)=>n+p.value,0),13800);
 assert.equal(received.ohlc[0].time,session.bars[String(minutes)][0][0]/1000);
}
assert.equal(JSON.stringify(session),before);
assert.throws(()=>D.timeframe(session,2));
const runs=D.runs([[1000,1],[2000,2],[2000,null],[4000,3],[5000,null],[6000,4]],1);
assert.deepEqual(runs,[[{time:1,value:1},{time:2,value:2}],[{time:4,value:3}],[{time:6,value:4}]]);
assert.equal(D.exactAt(runs[0],1.5),undefined); // do not substitute a future observation
assert.equal(D.exactAt(runs[0],2).value,2);
assert.equal(D.timeKey({year:2026,month:9,day:14}),'2026-09-14');
"""
    result=subprocess.run([node,'-e',script,str(adapter),str(dataset)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
