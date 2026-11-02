"""Regression for the same-day as_of/stale-candle bug; no network access."""
import json
from pathlib import Path
from datetime import datetime
from stocklab1932.refresh_prices import run, TZ

CAL={'start':'2026-01-01','end':'2026-12-31','closed':[]}
NOW=datetime.fromisoformat('2026-11-02T15:00:00+08:00')

def put(root, rel, payload):
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(payload),encoding='utf8');return p

def bar(day='2026-11-02',**kw):
    return dict(date=day,open=100,high=105,low=95,close=102,volume=10000,**kw)

def setup(root, symbol='2317.TW', last='2026-10-30', as_of='2026-11-02'):
    put(root,'config/market-calendar.json',CAL)
    put(root,'data/latest.json',{'demo':False,'generated_at':'2026-11-02T08:30:00+08:00','stocks':[{'symbol':symbol}]})
    put(root,'data/market/0050_TW.json',{'symbol':'0050.TW','as_of':'2026-11-02','candles':[bar()]})
    return put(root,'data/market/'+symbol.replace('.','_')+'.json',{'symbol':symbol,'as_of':as_of,'custom':'preserved','candles':[bar(last)]})

def test_same_day_asof_does_not_skip_missing_day(tmp_path):
    p=setup(tmp_path);calls=[]
    def fetch(s,d,n):calls.append((s,d,n));return [bar()]
    out=run(tmp_path,fetch,current=NOW,sleep_fn=lambda _:None)
    assert out['updated']==['2317.TW'] and calls[0][0]=='2317.TW'
    assert json.loads(p.read_text())['latest_complete_date']=='2026-11-02'

def test_actual_complete_day_skips_network(tmp_path):
    setup(tmp_path,last='2026-11-02',as_of='2026-10-30')
    def fail(*_):raise AssertionError('no request expected')
    out=run(tmp_path,fail,current=NOW,sleep_fn=lambda _:None)
    assert out['attempted']==0 and out['already_fresh']==2

def test_noon_requires_friday_not_partial_monday(tmp_path):
    p=setup(tmp_path);now=datetime.fromisoformat('2026-11-02T12:17:00+08:00')
    def fetch(s,*_):return [bar('2026-10-30'),bar()]
    out=run(tmp_path,fetch,current=now,sleep_fn=lambda _:None)
    assert out['required_close_date']=='2026-10-30'
    assert out['by_symbol']['2317.TW']['state']=='fresh'

def test_utc_clock_resolves_to_taipei(tmp_path):
    setup(tmp_path);out=run(tmp_path,lambda *_:[bar()],current=datetime.fromisoformat('2026-11-02T07:00:00+00:00'),sleep_fn=lambda _:None)
    assert out['at'].endswith('+08:00') and out['required_close_date']=='2026-11-02'

def test_stale_provider_never_claims_updated(tmp_path):
    setup(tmp_path);calls=[]
    def fetch(*args):calls.append(args);return [bar('2026-10-30')]
    a=run(tmp_path,fetch,current=NOW,sleep_fn=lambda _:None);b=run(tmp_path,fetch,current=NOW,sleep_fn=lambda _:None)
    assert a['updated']==[] and a['by_symbol']['2317.TW']['state']=='source_lag' and len(calls)==2

def test_failed_request_keeps_existing_bytes(tmp_path):
    p=setup(tmp_path);before=p.read_bytes()
    out=run(tmp_path,lambda *_:[],current=NOW,sleep_fn=lambda _:None)
    assert p.read_bytes()==before and out['failed']

def test_future_bar_rejected(tmp_path):
    p=setup(tmp_path)
    out=run(tmp_path,lambda *_:[bar('2026-11-03')],current=NOW,sleep_fn=lambda _:None)
    assert out['updated']==[] and '2026-11-03' not in [b['date'] for b in json.loads(p.read_text())['candles']]

def test_old_history_not_truncated_metadata_preserved(tmp_path):
    p=setup(tmp_path);run(tmp_path,lambda *_:[bar()],current=NOW,sleep_fn=lambda _:None)
    data=json.loads(p.read_text());assert len(data['candles'])==2 and data['custom']=='preserved'

def test_old_rotating_stock_is_still_refreshed(tmp_path):
    setup(tmp_path,last='2026-11-02')
    put(tmp_path,'data/market/8299_TWO.json',{'symbol':'8299.TWO','as_of':'2026-11-02','candles':[bar('2026-10-29')]})
    out=run(tmp_path,lambda *_:[bar()],current=NOW,sleep_fn=lambda _:None)
    assert '8299.TWO' in out['updated']

def test_budget_leaves_explicit_backlog(tmp_path,monkeypatch):
    setup(tmp_path);put(tmp_path,'data/market/8299_TWO.json',{'symbol':'8299.TWO','candles':[bar('2026-10-29')]})
    monkeypatch.setenv('PRICE_REFRESH_LIMIT','1')
    out=run(tmp_path,lambda *_:[bar()],current=NOW,sleep_fn=lambda _:None)
    assert out['attempted']==1 and out['queued']==1

def test_zero_limit_no_fake_success(tmp_path,monkeypatch):
    setup(tmp_path);monkeypatch.setenv('PRICE_REFRESH_LIMIT','0')
    out=run(tmp_path,lambda *_:[bar()],current=NOW,sleep_fn=lambda _:None)
    assert out['state']=='partial' and out['queued']==1

def test_calendar_outside_coverage_fails_closed(tmp_path):
    setup(tmp_path);out=run(tmp_path,lambda *_:[bar()],current=datetime.fromisoformat('2027-01-05T15:00:00+08:00'))
    assert out['state']=='calendar_missing' and not out['updated']

def test_naive_time_refused(tmp_path):
    import pytest
    with pytest.raises(ValueError):run(tmp_path,current=datetime(2026,11,2))

def test_provisional_data_refused(tmp_path):
    p=setup(tmp_path);before=p.read_bytes()
    out=run(tmp_path,lambda *_:[bar(is_final=False)],current=NOW,sleep_fn=lambda _:None)
    assert p.read_bytes()==before and out['quarantined']==1

def test_no_private_browser_data_or_llm(tmp_path):
    setup(tmp_path);out=run(tmp_path,lambda *_:[bar()],current=NOW,sleep_fn=lambda _:None)
    assert out['no_model_calls'] and not out['intraday_execution_supported']
    assert not (tmp_path/'data/system/qwen-state.json').exists()

def test_workflow_timezone_and_model_limits_unchanged():
    import yaml
    root=Path(__file__).resolve().parents[1]
    wf=yaml.load((root/'.github/workflows/market-refresh.yml').read_text(),Loader=yaml.BaseLoader)
    assert [r['cron'] for r in wf['on']['schedule']]==['17 1,4,6,8 * * 1-5','47 13 * * 1-5']
    assert wf['concurrency']['group']=='stocklab16-data' and wf['jobs']['refresh']['env']['ENABLE_QWEN']=='0'
    assert 'Refresh market data (no Qwen)' in (root/'.github/workflows/pages.yml').read_text()
    daily=(root/'.github/workflows/daily-update.yml').read_text()
    assert "QWEN_DAILY_LIMIT || '12'" in daily and "QWEN_RUN_LIMIT || '6'" in daily


def test_provisional_old_file_does_not_count_as_fresh(tmp_path):
    p=setup(tmp_path);data=json.loads(p.read_text());data['candles'].append(bar(is_final=False));p.write_text(json.dumps(data))
    out=run(tmp_path,lambda *_:[bar()],current=NOW,sleep_fn=lambda _:None)
    assert out['updated']==['2317.TW']
    assert json.loads(p.read_text())['candles'][-1].get('is_final') is not False

def test_old_provisional_cannot_hide_provider_lag(tmp_path):
    p=setup(tmp_path);data=json.loads(p.read_text());data['candles'].append(bar(provisional=True));p.write_text(json.dumps(data))
    out=run(tmp_path,lambda *_:[bar('2026-10-30')],current=NOW,sleep_fn=lambda _:None)
    assert out['by_symbol']['2317.TW']['state']=='source_lag'
    assert out['by_symbol']['2317.TW']['latest_complete_date']=='2026-10-30'
