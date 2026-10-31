import json,os,subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
from stocklab193.budget import reserve,save_results,limits,load
from stocklab193.calendar_update import parse_year
from stocklab193.notebook_flow import prepare_job,verify_job,ready_location
from stocklab16.qwen import QwenHints
ROOT=Path(__file__).resolve().parents[1]

def test_default_budget_is12day6run(monkeypatch):
    monkeypatch.delenv('QWEN_DAILY_LIMIT',raising=False);monkeypatch.delenv('QWEN_RUN_LIMIT',raising=False)
    assert limits()['day']==12 and limits()['run']==6

def test_six_per_round_shared_twelve_per_day(tmp_path,monkeypatch):
    monkeypatch.setenv('QWEN_DAILY_LIMIT','12');monkeypatch.setenv('QWEN_RUN_LIMIT','6')
    a,_,s=reserve(tmp_path,[str(i) for i in range(20)],'2026-10-30','morning');assert len(a)==6
    b,_,_=reserve(tmp_path,['x'+str(i) for i in range(20)],'2026-10-30','morning');assert not b
    b,_,_=reserve(tmp_path,['x'+str(i) for i in range(20)],'2026-10-30','evening');assert len(b)==6
    c,_,_=reserve(tmp_path,['other'],'2026-10-30','manual');assert not c
    c,_,_=reserve(tmp_path,['other'],'2026-10-31','morning');assert c==['other']

def test_cached_success_not_counted_and_none_not_evidence(tmp_path):
    reserve(tmp_path,['a','b'],'2026-10-30','r')
    save_results(tmp_path,{'a':{'real':'result'},'b':None})
    a,c,_=reserve(tmp_path,['a','b','c'],'2026-10-30','r')
    assert a==['c'] and list(c)==['a']
    a,c,_=reserve(tmp_path,['b'],'2026-10-30','new-r');assert a==['b']

def test_adapter_and_base_share_same_counter(tmp_path):
    from stocklab192.runtime import reserve as adapter_reserve
    reserve(tmp_path,[str(i) for i in range(6)],'2026-10-30')
    a,_=adapter_reserve(tmp_path,['adapter1'],'2026-10-30');assert a==[]

def test_hard_caps_and_invalid_budget(monkeypatch):
    monkeypatch.setenv('QWEN_DAILY_LIMIT','9999');monkeypatch.setenv('QWEN_RUN_LIMIT','999');monkeypatch.setenv('QWEN_BATCH_SECONDS','9999')
    assert limits()=={'day':24,'run':12,'seconds':1200}
    monkeypatch.setenv('QWEN_RUN_LIMIT','not-a-number')
    with pytest.raises(ValueError):limits()

def test_batch_calls_one_worker_and_preserves_cached(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_QWEN','1');calls=[]
    def worker(cmd,**kwargs):
        calls.append(cmd);p=json.loads(Path(cmd[-2]).read_text())
        Path(cmd[-1]).write_text(json.dumps({x['key']:{'category':'partnership','evidence':'合作仍在討論'} for x in p['requests']}))
        return SimpleNamespace(returncode=0,stderr='')
    monkeypatch.setattr(subprocess,'run',worker)
    q=QwenHints(root=tmp_path);rows=[{'title':f'{i}公司合作仍在討論'} for i in range(8)]
    out=q.batch(rows)
    assert len(calls)==1 and len([x for x in out if x])==6
    q2=QwenHints(root=tmp_path);out2=q2.batch(rows)
    assert len(calls)==1 and q2.cached==6

def test_batch_timeout_keeps_completed_rows(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_QWEN','1')
    def worker(cmd,**kwargs):
        row=json.loads(Path(cmd[-2]).read_text())['requests'][0]
        Path(cmd[-1]).write_text(json.dumps({row['key']:{'category':'partnership','evidence':'合作仍在討論'}}))
        raise subprocess.TimeoutExpired(cmd,10)
    monkeypatch.setattr(subprocess,'run',worker)
    q=QwenHints(root=tmp_path);out=q.batch([{'title':f'{i}公司合作仍在討論'} for i in range(3)])
    assert out[0] and not out[1] and q.used==3 and q.failed
    assert load(q.path,{})['attempts']==3

def test_calendar_empty_wrong_year_rejected():
    with pytest.raises(ValueError):parse_year({'data':[]},2027)
    with pytest.raises(ValueError):parse_year({'data':[['2026/01/01','元旦']]},2027)

def test_calendar_start_end_sessions_not_holidays():
    rows=[['2027/01/01','開國紀念日'],['2027/01/04','國曆新年開始交易日'],['2027/02/03','農曆春節前最後交易日'],['2027/02/04','市場無交易，僅辦理交割'],['2027/02/05','農曆除夕']]
    p=parse_year({'data':rows},2027)
    assert '2027-01-04' not in p['closed'] and '2027-02-03' not in p['closed'] and '2027-02-04' in p['closed']

def test_ready_handoff_not_in_memory(tmp_path):
    ready=prepare_job(tmp_path,'job',ROOT/'examples/smoke.jsonl','smoke','program-hash')
    assert ready['counts']=={'train':16,'validation':4,'test':4}
    p=ready_location(tmp_path);new=verify_job(p,'program-hash');assert new['identity']==ready['identity']
    again=prepare_job(tmp_path,'job',ROOT/'examples/smoke.jsonl','smoke','program-hash');assert again==ready

def test_handoff_detects_modified_data(tmp_path):
    ready=prepare_job(tmp_path,'job',ROOT/'examples/smoke.jsonl','smoke','program-hash')
    p=Path(ready['data_dir'])/'train.jsonl';p.write_text(p.read_text()+'\n')
    with pytest.raises(ValueError,match='已變更'):verify_job(ready_location(tmp_path),'program-hash')

def test_handoff_version_wrong_and_reviewed_synthetic(tmp_path):
    prepare_job(tmp_path,'job',ROOT/'examples/smoke.jsonl','smoke','abc')
    with pytest.raises(ValueError,match='同一套'):verify_job(ready_location(tmp_path),'wrong')
    with pytest.raises(ValueError,match='合成'):prepare_job(tmp_path,'real',ROOT/'examples/smoke.jsonl','reviewed','abc')

def test_cpu_classifier_no_qwen(tmp_path):
    pytest.importorskip('sklearn')
    from stocklab193.lightweight import fit,predict
    ready=prepare_job(tmp_path,'job',ROOT/'examples/smoke.jsonl','smoke','abc');out=tmp_path/'lite.json'
    r=fit(ready['data_dir'],out,allow_synthetic=True)
    assert r['Qwen_required'] is False and r['synthetic_smoke_only'] is True
    result=predict(out,['公司公布月營收年增10%'])
    assert result[0]['category'] in r['classes'] and result[0]['not_calibrated_probability']

def test_ready_failure_does_not_write_arbitrary_paths(tmp_path):
    with pytest.raises(ValueError):prepare_job(tmp_path,'../outside',ROOT/'examples/smoke.jsonl','smoke','abc')
    assert not (tmp_path/'jobs').exists()


def test_round_robin_rotate_day_windows_without_return_targets():
    from stocklab193.budget import fair_round_robin
    from datetime import datetime
    from zoneinfo import ZoneInfo
    queues=[[str(i)+'a',str(i)+'b'] for i in range(20)]
    a,oa=fair_round_robin(queues,datetime(2026,10,30,8,tzinfo=ZoneInfo('Asia/Taipei')))
    b,ob=fair_round_robin(queues,datetime(2026,10,30,21,tzinfo=ZoneInfo('Asia/Taipei')))
    assert len(set(x[:-1] for x in a[:20]))==20 and set(a)==set(b)
    assert oa!=ob and a[:6]!=b[:6]
