from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
import copy,json,hashlib,subprocess
import pytest,yaml
from stocklab16.events import analyze,aggregate,group_items,extract_metrics,issuer_relation,validate_hint
from stocklab16.common import ROOT,read_json,write_json,now
from stocklab16.decision import decide,technical_report
from stocklab16.indicators import enrich
from stocklab16.storage import store,validate_snapshot,settings_file
from stocklab16.migrate import upgrade,run as migrate
from stocklab16.stage import stage
from stocklab16.qwen import QwenHints
from stocklab16.build import run as build,peer_percentiles

DAY='2026-09-10';CUTOFF=DAY+'T23:59:59+08:00'
def article(title,**kw):return {'title':title,'published_at':DAY+'T10:00:00+08:00',**kw}
def meta(name='群聯',symbol='8299.TWO',sector='半導體'):return {'name':name,'symbol':symbol,'sector':sector}
def event(title,m=None,**kw):return analyze(article(title,**kw),m or meta(),CUTOFF)
def sample():return read_json(ROOT/'data/demo/latest.json')

@pytest.mark.parametrize('name,symbol,sector,title,category,score',[
 ('群聯','8299.TWO','半導體','群聯8月營收年增377%、再創新高','monthly_revenue',29.6),
 ('信驊','5274.TWO','半導體','Factset：信驊(5274-TW)EPS預估上修至194.98元，目標價為22500元','analyst_forecast',7.7),
 ('中信金','2891.TW','金融','Factset：中信金(2891-TW)EPS預估上修至4.31元，目標價為73.5元','analyst_forecast',7.7),
 ('中華電','2412.TW','通信','中華電聯名卡贈500點','promotion',0),
 ('中華電','2412.TW','通信','中華電股東會開超過18小時','governance',0),
 ('中華電','2412.TW','通信','中華電個股概覽','profile',0),
])
def test_user_cases(name,symbol,sector,title,category,score):
    e=event(title,meta(name,symbol,sector));assert e['category']==category;assert e['impact_score']==score

@pytest.mark.parametrize('title,key,value',[
 ('群聯8月營收年增377%','revenue_yoy',377),
 ('群聯8月營收年減12.5%','revenue_yoy',-12.5),
 ('群聯8月營收月增3.2%','revenue_mom',3.2),
 ('群聯營收為10億元','revenue_amount',10),
 ('Factset 群聯EPS預估上修至19.5元','eps',19.5),
 ('Factset 群聯EPS由18元上修至19.5元','eps_prior',18),
 ('Factset 群聯EPS由18元上修至19.5元','eps',19.5),
 ('Factset 群聯目標價由500元上修至550元','target',550),
 ('群聯毛利率為32.8%','margin',32.8),
])
def test_numeric_spans(title,key,value):
    m=extract_metrics(article(title))[key];assert m['value']==value;assert m['quote'] in title;assert m['evidence_id']=='e1'

def test_missing_eps_baseline_never_fabricated():
    e=event('Factset 群聯EPS預估上修至19.5元，目標價為800元');assert not any(m['key']=='eps_prior' for m in e['metrics']);assert e['increment_type']=='direction_only';assert '舊預估' in e['summary']
def test_real_revision_uses_percentage():
    e=event('Factset 群聯EPS由10元上修至12元');assert e['derived_metrics'][0]['value']==20;assert e['impact_score']==13.2
def test_financial_kpis_not_manufacturing():
    e=event('Factset 中信金EPS預估上修至4.31元，目標價為73.5元',meta('中信金','2891.TW','金融'))
    assert '信用成本' in e['watch_metric'];assert '毛利' not in e['watch_metric'];assert e['derived_metrics'][0]['value']==17.05
def test_target_pair_is_not_current_pe():
    e=event('Factset 信驊EPS預估上修至194.98元，目標價為22500元',meta('信驊','5274.TWO'))
    assert e['derived_metrics'][0]['value']==115.4;assert '不是目前本益比' in e['derived_metrics'][0]['assumption']
def test_unknown_issuer_has_zero_weight():
    e=event('另一家公司EPS上修至8299元');assert not e['included'];assert e['impact_score']==0

def test_same_score_can_have_different_useful_content():
    a=event('Factset 信驊EPS預估上修至194.98元，目標價為22500元',meta('信驊','5274.TWO'))
    b=event('Factset 中信金EPS預估上修至4.31元，目標價為73.5元',meta('中信金','2891.TW','金融'))
    assert a['impact_score']==b['impact_score'];assert a['watch_metric']!=b['watch_metric'];assert a['invalidation']!=b['invalidation']
@pytest.mark.parametrize('key',['published_at','available_at'])
def test_future_evidence_rejected(key):
    with pytest.raises(ValueError):event('群聯營收年增10%',**{key:'2026-09-11T00:00:00+08:00'})
@pytest.mark.parametrize('hint',[None,{}, {'category':'orders','evidence':'虛構金額'}, {'category':'promotion','evidence':''}])
def test_hallucinated_hint_not_accepted(hint):assert not validate_hint(hint,[{'text':'群聯合作'}])
def test_qwen_cannot_erase_specific_numeric_event():
    e=analyze(article('群聯8月營收年增377%'),meta(),CUTOFF,{'category':'partnership','evidence':'群聯8月營收'})
    assert e['category']=='monthly_revenue'
def test_copies_not_new_events():
    items=group_items([article('群聯8月營收年增377% - A'),article('群聯8月營收年增377% - B')],meta());assert len(items)==1;assert len(items[0]['copies'])==1
def test_distinct_numbers_not_merged():
    items=group_items([article('群聯8月營收年增377%'),article('群聯8月營收年增30%')],meta());assert len(items)==2
def test_opposite_revisions_not_merged():
    items=group_items([article('Factset 群聯EPS預估上修至10元'),article('Factset 群聯EPS預估下修至10元')],meta());assert len(items)==2
def test_news_factor_not_sum_of_raw_scores():
    e=event('群聯8月營收年增377%');a=aggregate([e,e]);assert a['score']==aggregate([e])['score'];assert a['score']<70

def test_empty_factor_not_fabricated():
    d=decide({'symbol':'X','candles':[],'news':[],'facts':{}},DAY);assert d['code']=='insufficient';assert all(f['score'] is None for f in d['factors'])
def test_score_reconciles_exactly():
    for s in sample()['stocks']:
        d=s['decision'];calc=max(0,min(100,50+sum(f['contribution'] for f in d['factors'])-d['risk_deduction']-d['missing_deduction']))
        assert abs(calc-d['score'])<=.06

def test_wrong_flow_date_is_missing():
    s=copy.deepcopy(sample()['stocks'][0]);s['facts']['flow_date']='2000-01-01';d=decide(s,DAY);assert next(f for f in d['factors'] if f['key']=='flow')['score'] is None

def test_financial_valuation_not_semiconductor_pe():
    s=next(s for s in sample()['stocks'] if s['symbol']=='2891.TW');d=decide(s,DAY);assert next(f for f in d['factors'] if f['key']=='valuation')['score'] is None

def test_etf_never_single_company_buy():
    s=next(s for s in sample()['stocks'] if s['symbol']=='0050.TW');d=decide(s,DAY);assert d['code']=='insufficient';assert 'ETF' in d['label']
def test_new_cross_vs_already_above():
    rows=[{'date':DAY,'k':60,'d':50,'macd':2,'signal':1},{'date':DAY,'k':70,'d':55,'macd':3,'signal':2}]
    t=technical_report(rows);assert t['kd_cross']=='above';assert t['macd_cross']=='above'
def test_volume_ratio_excludes_today():
    rows=[{'volume':100} for _ in range(5)]+[{'volume':300}];assert technical_report(rows)['volume_ratio']==3

def test_pe_group_needs_real_industry_sample():
    stocks=[{'facts':{'pe':10+i,'issuer_sector':'A' if i<4 else 'B'}} for i in range(7)];peer_percentiles(stocks);assert all('pe_peer_percentile' not in s['facts'] for s in stocks)
def test_pe_group_with_five():
    stocks=[{'facts':{'pe':10+i,'issuer_sector':'A'}} for i in range(5)];peer_percentiles(stocks);assert stocks[0]['facts']['pe_peer_percentile']==0;assert stocks[-1]['facts']['pe_peer_percentile']==100

def test_snapshots_are_append_only(tmp_path):
    a=store(sample(),tmp_path);before=(tmp_path/a['path']).read_bytes();b=store(sample(),tmp_path)
    assert a['path']!=b['path'];assert b['run_count']==2;assert (tmp_path/a['path']).read_bytes()==before
    manifest=read_json(tmp_path/'data/manifest.json');assert len(manifest['snapshots'][0]['runs'])==2

def test_backfill_does_not_roll_back_latest(tmp_path):
    a=store(sample(),tmp_path);latest=(tmp_path/'data/latest.json').read_bytes()
    old=read_json(ROOT/'data/demo/snapshots/2025-08-15.json');store(old,tmp_path)
    assert (tmp_path/'data/latest.json').read_bytes()==latest

def test_future_candles_rejected():
    p=sample();p['stocks'][0]['candles'][-1]['date']='2099-01-01';assert validate_snapshot(p)
def test_demo_integrity():
    for row in read_json(ROOT/'data/demo/manifest.json')['snapshots']:
        p=ROOT/row['path'];assert not validate_snapshot(read_json(p));assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
def test_no_future_date_build():
    with pytest.raises(ValueError):build((now().date()+timedelta(days=1)).isoformat())

def test_migration_preserves_original(tmp_path):
    old=sample();old['version']='16.0';path=tmp_path/'data/snapshots/old.json';write_json(path,old)
    write_json(tmp_path/'data/manifest.json',{'latest':DAY,'snapshots':[{'date':DAY,'path':'data/snapshots/old.json'}]})
    before=path.read_bytes();report=migrate(tmp_path);assert path.read_bytes()==before;assert report[0]['status']=='recomputed'
    p=read_json(tmp_path/report[0]['result']);assert p['mode']=='retrospective_reanalysis';assert not validate_snapshot(p)
def test_custom_stocks_overrides_default(tmp_path):
    p=tmp_path/'config/stocks.json';write_json(p,{'stocks':[]});assert settings_file('stocks',tmp_path)==p

def test_qwen_disabled_no_subprocess(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_QWEN','0');monkeypatch.setattr(subprocess,'run',lambda *a,**kw:pytest.fail('Worker started'))
    q=QwenHints(root=tmp_path);assert q.hint('群聯合作') is None;assert q.used==0

def test_qwen_budget_and_cache(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_QWEN','1');monkeypatch.setenv('QWEN_DAILY_LIMIT','1000')
    calls=[]
    def worker(cmd,**kw):
        calls.append(cmd);write_json(Path(cmd[-1]),{'category':'partnership','evidence':'合作條件仍在洽談'});return SimpleNamespace(returncode=0,stderr='')
    monkeypatch.setattr(subprocess,'run',worker)
    q=QwenHints(root=tmp_path)
    for i in range(10):q.hint(f'{i} 群聯合作條件仍在洽談')
    assert q.used==6;assert len(calls)==6
    q2=QwenHints(root=tmp_path);q2.hint('0 群聯合作條件仍在洽談');assert q2.cached==1;q2.hint('new 群聯合作條件仍在洽談');assert q2.used==0

def test_qwen_timeout_stops_retries(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_QWEN','1')
    def worker(*args,**kw):raise subprocess.TimeoutExpired('worker',120)
    monkeypatch.setattr(subprocess,'run',worker);q=QwenHints(root=tmp_path);assert q.hint('群聯合作條件仍在洽談') is None
    q.hint('群聯另外合作');assert q.used==1;assert read_json(q.path)['attempts']==1

def test_staging_tutorial_and_private_data(tmp_path):
    target=stage(ROOT,tmp_path/'site');assert (target/'tutorial.html').is_file();assert read_json(target/'runtime.json')['mode']==('production' if (read_json(ROOT/'data/manifest.json',{}) or {}).get('snapshots') else 'demo');assert not (target/'data/system').exists()
def test_workflow_yaml():
    for p in (ROOT/'.github/workflows').glob('*.yml'):
        y=yaml.load(p.read_text(),Loader=yaml.BaseLoader);assert y['name'];assert 'on' in y;assert y['jobs']
def test_tutorial_is_linked_and_packaged():
    html=(ROOT/'index.html').read_text();assert 'tutorial.html' in html
    stage_code=(ROOT/'stocklab16/stage.py').read_text();assert 'tutorial.html' in stage_code


def test_eps_no_spaces_and_simplified_forecast_token():
    from stocklab16.events import extract_metrics
    for title in ['富邦金分析師EPS預估下修至8.2元，目標價為108元','富邦金分析師EPS预估下修至8.2元，目標價為108元']:
        metrics=extract_metrics({'title':title,'id':'fixture','published_at':'2026-09-10T10:00:00+08:00'})
        assert metrics['eps']['value']==8.2
        assert metrics['target']['value']==108
