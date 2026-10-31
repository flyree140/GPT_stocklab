import sys,json,copy,math,tempfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stocklab192.schema import *
from stocklab192.prepare import split_records
from stocklab192.features import technical,point_facts,six_factors
from stocklab192.social import summarize,fetch_author_feed
from stocklab192.train import budget_for,validate_parts
from stocklab192.runtime import reserve,cache_results,make_record
from stocklab192.tabular import partition
from stocklab192.deployment import validate_adapter

@pytest.fixture
def examples():return load_jsonl(ROOT/'examples/smoke.jsonl')

@pytest.fixture
def factor_example():return json.loads((ROOT/'examples/factors.synthetic.json').read_text())

def test_all_teaching_records_valid(examples):
    for r in examples:assert check_record(r,True)==[],(r['id'],check_record(r,True))

def test_no_unreviewed_training(examples):
    r=copy.deepcopy(examples[0]);r['review']['approved']=False
    assert check_record(r,True)

def test_training_rights_required(examples):
    r=copy.deepcopy(examples[0]);r['documents'][0]['training_allowed']=False
    assert check_record(r,True)

def test_no_future_evidence(examples):
    r=copy.deepcopy(examples[0]);r['documents'][0]['available_at']='2027-01-01T00:00:00Z'
    assert check_record(r)

def test_no_price_probability(examples):
    r=copy.deepcopy(examples[0]);r['gold']['price_direction']='up'
    assert check_record(r,True)

def test_numbers_not_fabricated(examples):
    r=copy.deepcopy(examples[0]);r['gold']['metrics'][0]['value']=999
    assert check_record(r,True)

def test_quote_required(examples):
    r=copy.deepcopy(examples[0]);r['gold']['evidence'][0]['quote']='not in source'
    assert check_record(r,True)

def test_account_outside_model(examples):
    r=copy.deepcopy(examples[0]);r['issuer']['capital']=5000
    assert check_record(r)

def test_prompt_excludes_gold(examples):
    msg=prompt_messages(examples[0]);d=json.loads(msg[-1]['content']);assert 'gold' not in d and 'review' not in d

def splits(examples):return split_records(examples,'2025-01-17T23:59:59+08:00','2025-01-21T23:59:59+08:00',allow_synthetic=True)

def test_ordered_split(examples):
    parts,rep=splits(examples);assert all(parts.values());validate_parts(parts,True)

def test_smoke_not_production(examples):
    parts,rep=splits(examples)
    with pytest.raises(ValueError):validate_parts(parts,False)

def test_shared_event_purged(examples):
    rows=copy.deepcopy(examples);rows[-1]['event_cluster']=rows[0]['event_cluster'];parts,rep=splits(rows)
    assert rep['purged'] and not any(r['event_cluster']==rows[0]['event_cluster'] for rs in parts.values() for r in rs)

def test_duplicate_doc_purged(examples):
    rows=copy.deepcopy(examples);rows[-1]['documents'][0]['text']=rows[0]['documents'][0]['text'];rows[-1]['gold']=rows[0]['gold']
    parts,rep=splits(rows);assert any('identical' in r['reason'] for r in rep['purged'])

def test_missing_factors_not_neutral(factor_example):
    f=six_factors(factor_example['stock'],factor_example['cutoff'])
    assert len(f)==6 and f['flow']['status']=='missing' and f['social']['status']=='missing'

def test_volume_uses_previous_not_current(factor_example):
    rows=copy.deepcopy(factor_example['stock']['candles']);rows[-1]['volume']=1e7
    result=technical(rows,factor_example['cutoff'])
    prev=sum(r['volume'] for r in rows[-21:-1])/20
    assert abs(result['values']['volume_ratio_previous20']-1e7/prev)<1e-9

def test_rsi_monotonic_up(factor_example):
    result=technical(factor_example['stock']['candles'],factor_example['cutoff']);assert result['values']['rsi14']==100

def test_future_bar_blocked(factor_example):
    rows=copy.deepcopy(factor_example['stock']['candles']);rows[-1]['available_at']='2099-01-01T00:00:00Z'
    result=technical(rows,factor_example['cutoff']);assert result['bar_count']==len(rows)-1 and result['rejected']

def test_volume_zero_rejected(factor_example):
    rows=copy.deepcopy(factor_example['stock']['candles']);rows[-1]['volume']=0
    assert technical(rows,factor_example['cutoff'])['rejected']

def test_released_financial_timestamp(factor_example):
    facts=copy.deepcopy(factor_example['facts']);facts[0]['available_at']='2099-01-01T00:00:00Z'
    assert point_facts(facts,'fundamental',factor_example['cutoff'])['status']=='missing'

def test_social_failure_not_zero(factor_example):
    x=summarize([],factor_example['cutoff']);assert x['status']=='missing' and x['values']=={}

def test_social_dedup_and_no_false_baseline(factor_example):
    posts=factor_example['social_posts'];x=summarize(posts+posts,factor_example['cutoff'],source_ok=True)
    assert x['values']['unique_posts']==12 and x['values']['duplicate_fraction']==.5 and x['values']['attention_robust_z'] is None

def test_likes_captured_later_not_backfilled(factor_example):
    p=copy.deepcopy(factor_example['social_posts']);p[0]['observed_at']='2099-01-01T00:00:00Z'
    x=summarize(p,factor_example['cutoff'],source_ok=True);assert x['values']['unique_posts']==11

def test_unverified_social_entity_rejected(factor_example):
    p=copy.deepcopy(factor_example['social_posts']);p[0]['issuer_verified']=False
    assert summarize(p,factor_example['cutoff'],source_ok=True)['values']['unique_posts']==11

def test_collector_needs_permission():
    with pytest.raises(ValueError):fetch_author_feed('example.com')

def test_quota_shared_and_failed_attempt_counts(tmp_path):
    keys=['a','b','c','d'];chosen,_=reserve(tmp_path,keys,'2026-10-28');assert len(chosen)==4
    cache_results(tmp_path,{k:None for k in chosen});chosen,cached=reserve(tmp_path,keys+['e','f','g'],'2026-10-28')
    assert chosen==['e','f'] and len(cached)==0  # failures counted, never cached as valid analysis
    assert reserve(tmp_path,['h'],'2026-10-28')[0]==[]
    assert len(reserve(tmp_path,['h'],'2026-10-29')[0])==1

def test_budget_upper_bound(tmp_path):
    assert len(reserve(tmp_path,[str(i) for i in range(20)],'2026-10-28',99)[0])==6

def test_small_training_budget():
    assert budget_for('smoke')['max_steps']==6;assert budget_for('reviewed')['max_records']==1000

def test_prompt_no_context_future(examples):
    stock={'symbol':'EXAMPLE','name':'X','sector':'teaching'};e={'title':'one','published_at':'2099-01-01T00:00:00Z','available_at':'2099-01-01T00:00:00Z'}
    assert make_record(stock,e,'2026-10-28T18:00:00+08:00') is None

def test_return_purge():
    base={'id':'a','decision_at':'2025-01-01T18:00:00+08:00','entry_at':'2025-01-02T09:00:00+08:00','label_end_at':'2025-02-10T13:30:00+08:00','features_available_at':'2025-01-01T17:00:00+08:00','event_cluster':'e','features':{'rsi14':50},'net_return_pct':2}
    parts,report=partition([base],'2025-01-31T23:59:59+08:00','2025-02-28T23:59:59+08:00','2025-03-31T23:59:59+08:00')
    assert not any(parts.values()) and report['rejected']

def test_unsafe_adapter_rejected(tmp_path):
    with pytest.raises(ValueError):validate_adapter(tmp_path)


def test_social_can_reuse_own_output_as_baseline(factor_example):
    from datetime import timedelta
    cutoff=factor_example['cutoff'];now=timestamp(cutoff);hist=[]
    for i,n in enumerate([5,7,9,11,13],start=1):
        hist.append({'cutoff':(now-timedelta(days=i)).isoformat(),
          'source_ok':True,'collection_key':'same','window_hours':24,
          'values':{'unique_posts':n}})
    result=summarize(factor_example['social_posts'],cutoff,source_ok=True,baseline=hist,collection_key='same')
    assert result['values']['baseline_windows']==5
    assert result['values']['attention_robust_z'] is not None

def test_social_cannot_mix_sampling_methods(factor_example):
    from datetime import timedelta
    now=timestamp(factor_example['cutoff'])
    hist=[{'cutoff':(now-timedelta(days=i)).isoformat(),'source_ok':True,
       'collection_key':'another-platform','window_hours':24,'unique_posts':i} for i in range(1,7)]
    result=summarize(factor_example['social_posts'],factor_example['cutoff'],source_ok=True,baseline=hist,collection_key='same')
    assert result['values']['baseline_windows']==0


def test_runtime_cpu_leaves_formal_snapshot_untouched(tmp_path):
    from stocklab192.runtime import run
    from datetime import datetime
    from zoneinfo import ZoneInfo
    snap={'as_of':'2025-01-01','generated_at':'2025-01-01T18:00:00+08:00','stocks':[{'symbol':'TEST','name':'測試','candles':[],'news':[]}]}
    d=tmp_path/'data';d.mkdir();p=d/'latest.json';p.write_text(json.dumps(snap));before=p.read_bytes()
    result=run(tmp_path,allow_model=False)
    assert p.read_bytes()==before
    assert result['model_status']['attempts_this_run']==0
    assert (d/'research192/latest.json').is_file()
    assert not (d/'system/qwen-state.json').exists()
