"""Offline acquisition-preparation invariants; no real credentials or network."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest
from scripts.prepare_nq_history import chunks, request, estimate_chunk, digest

UTC=timezone.utc

def test_chunk_cores_contiguous_and_bounded_across_dst():
    first=datetime(2026,2,22,23,tzinfo=UTC)
    last=datetime(2026,11,10,22,tzinfo=UTC)
    plan=chunks(first,last)
    assert plan[0]['core_start']==first.isoformat()
    assert plan[-1]['core_end']==last.isoformat()
    for i,row in enumerate(plan):
        start=datetime.fromisoformat(row['core_start']); end=datetime.fromisoformat(row['core_end'])
        fetch=datetime.fromisoformat(row['fetch_start'])
        assert fetch<=start<end and end-fetch<=timedelta(days=97,hours=1)
        assert row['request_sha256']==digest(row['requests'])
        assert row['requests']['ohlcv-1m']['stype_in']=='raw_symbol'
        symbols=row['requests']['ohlcv-1m']['symbols']
        assert 2 <= len(symbols) <= 3
        assert all(__import__('re').fullmatch(r'NQ[HMUZ]\d',symbol) for symbol in symbols)
        if i:
            assert plan[i-1]['core_end']==row['core_start']
            assert timedelta(days=6,hours=23)<=start-fetch<=timedelta(days=7,hours=1)
    assert {datetime.fromisoformat(r['core_start']).hour for r in plan}=={22,23}


def test_definition_request_expands_to_whole_utc_days():
    first=datetime(2026,9,13,22,tzinfo=UTC); last=datetime(2026,9,25,21,tzinfo=UTC)
    kw=request(first,last,'definition')
    assert kw['start']=='2026-09-13T00:00:00+00:00'
    assert kw['end']=='2026-09-26T00:00:00+00:00'
    assert request(first,last,'ohlcv-1m')['start']==first.isoformat()


def test_cost_checkpoints_resume_without_requery(tmp_path,monkeypatch):
    class Metadata:
        calls=0
        def get_cost(self,**kw):
            self.calls+=1
            return {'definition':.01,'ohlcv-1m':.1}[kw['schema']]
        def get_billable_size(self,**kw): return 100
        def get_record_count(self,**kw): return 10
    class Client:
        metadata=Metadata()
    c=Client()
    monkeypatch.setattr('scripts.prepare_nq_history.client',lambda:c)
    row=chunks(datetime(2026,9,13,22,tzinfo=UTC),datetime(2026,9,25,21,tzinfo=UTC))[0]
    assert estimate_chunk(tmp_path,row)['total_cost_usd']=='0.11'
    assert c.metadata.calls==2
    assert estimate_chunk(tmp_path,row)['total_cost_usd']=='0.11'
    assert c.metadata.calls==2


def test_invalid_cost_fails_closed(tmp_path,monkeypatch):
    class Metadata:
        def get_cost(self,**kw): return float('nan')
    class Client: metadata=Metadata()
    monkeypatch.setattr('scripts.prepare_nq_history.client',lambda:Client())
    row=chunks(datetime(2026,9,13,22,tzinfo=UTC),datetime(2026,9,25,21,tzinfo=UTC))[0]
    with pytest.raises(ValueError,match='Invalid provider cost'): estimate_chunk(tmp_path,row)


def test_preparation_has_no_billable_endpoint_calls():
    source=(Path(__file__).resolve().parents[1]/'scripts/prepare_nq_history.py').read_text()
    assert '.timeseries.' not in source and '.submit_job(' not in source


def test_acquisition_rejects_changed_scope_and_total():
    from scripts.acquire_nq_history import verify_plan
    chunk=chunks(datetime(2026,9,13,22,tzinfo=UTC),datetime(2026,9,25,21,tzinfo=UTC))[0]
    chunk.update(estimates_usd={'definition':.01,'ohlcv-1m':.1},total_cost_usd='0.11')
    plan=dict(chunks=[chunk],schemas=['definition','ohlcv-1m'],total_cost_usd='0.11')
    plan['approval_sha256']=digest(plan)
    verify_plan(plan,plan['approval_sha256'],'0.11')
    with pytest.raises(ValueError,match='exact final plan total'): verify_plan(plan,plan['approval_sha256'],'1')
    plan['chunks'][0]['fetch_end']='2026-09-26T21:00:00+00:00'
    with pytest.raises(ValueError,match='Plan changed'): verify_plan(plan,plan['approval_sha256'],'0.11')


def test_partial_chunk_never_automatically_retries(tmp_path):
    from scripts.acquire_nq_history import completed
    assert not completed(tmp_path/'absent',{})
    raw=tmp_path/'partial';raw.mkdir();(raw/'failure.json').write_text('{}')
    with pytest.raises(ValueError,match='Partial raw chunk retained'): completed(raw,{})


def test_acquisition_hard_maximum_is_enforced_before_any_download():
    from scripts.acquire_nq_history import verify_plan
    chunk=chunks(datetime(2026,9,13,22,tzinfo=UTC),datetime(2026,9,25,21,tzinfo=UTC))[0]
    chunk.update(estimates_usd={'definition':'40','ohlcv-1m':'46'},total_cost_usd='86')
    plan=dict(chunks=[chunk],schemas=['definition','ohlcv-1m'],total_cost_usd='86')
    plan['approval_sha256']=digest(plan)
    with pytest.raises(ValueError,match=r'hard \$85'):
        verify_plan(plan,plan['approval_sha256'],'86')
