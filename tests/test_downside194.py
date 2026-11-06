from datetime import date,datetime,timedelta
import copy,json
import pytest
from stocklab194.downside import diagnose,size_addition
from stocklab194.refresh import run
from stocklab16.common import write_json
from stocklab17.calendar import is_session
END='2026-11-05';CUT='2026-11-05T17:00:00+08:00'
def bars():
 day=date(2026,7,1);days=[]
 while day<=date.fromisoformat(END):
  if is_session(day.isoformat()):days.append(day.isoformat())
  day+=timedelta(days=1)
 days=days[-70:];out=[]
 for i,d in enumerate(days):
  c=110+i*.2
  if i>=len(days)-9:c=120-(i-(len(days)-9))*3
  out.append({'date':d,'open':c+.5,'high':c+1,'low':c-1,'close':c,'volume':100000})
 return out

def test_falling_is_not_bottom():
 d=diagnose(bars(),CUT);assert d['state']=='falling' and not d['bottom_confirmed'] and d['bottom_probability'] is None
 assert d['research_stage']==0 and d['metrics']['return_5d_pct']<0

def test_rsi_low_is_not_buy():
 d=diagnose(bars(),CUT);assert d['metrics']['rsi14']<30 and d['add_plan']['auto_orders'] is False

def test_sharp_wick_is_not_confirmed_bottom():
 x=bars();x[-1].update(low=70,high=102,open=95,close=100)
 d=diagnose(x,CUT);assert d['state']=='rebound' and d['research_stage']==0

def test_missing_prices_no_bogus_point_estimate():
 d=diagnose([],CUT);assert d['state']=='missing' and d['metrics']=={}

def test_future_price_excluded():
 x=bars()+[{'date':'2026-11-06','open':1,'high':1,'low':1,'close':1,'volume':100}]
 d=diagnose(x,CUT);assert d['price_date']==END and d['metrics']['close']==bars()[-1]['close']

def test_incomplete_intraday_excluded():
 d=diagnose(bars(),'2026-11-05T12:00:00+08:00');assert d['price_date']=='2026-11-04'

def test_stale_never_add():
 d=diagnose(bars(),'2026-11-06T17:00:00+08:00');assert d['state']=='stale' and d['research_stage']==0

def test_corporate_action_does_not_become_collapse():
 x=bars();x[-3]['corporate_action']=True
 d=diagnose(x,CUT);assert d['state']=='corporate_action'

def test_no_flow_not_positive_flow():
 d=diagnose(bars(),CUT);assert next(x for x in d['checks'] if x['key']=='flow')['status']=='missing'

def test_relative_different_dates_not_compared():
 d=diagnose(bars(),CUT,market={'state':'neutral','price_date':'2026-11-04','metrics':{'return_5d_pct':10}})
 assert d['metrics']['relative_5d_pct'] is None

def test_prices_input_not_mutated():
 x=bars();prior=copy.deepcopy(x);diagnose(x,CUT);assert x==prior

def test_tiny_add_cannot_ignore_fee():
 r=size_addition(100,96,106,4000,4000,200,risk_fraction=.25)
 assert r['shares']==0 and r['status']=='cost_space_insufficient'

def test_existing_risk_exhausted_blocks_add():
 r=size_addition(100,96,130,4000,8000,200,existing_shares=30,current=102,risk_fraction=1)
 assert r['shares']==0 and r['existing_risk']>200

def test_positive_scenario_fits_caps():
 r=size_addition(100,96,130,100000,20000,1000,risk_fraction=.25)
 assert r['shares']>0 and r['stop_scenario_loss']<=250 and r['buy_cost']<=20000
 assert r['expected_return'] is None and not r['auto_orders']

@pytest.mark.parametrize('entry,stop,target',[(100,110,130),(0,0,100),(100,96,90)])
def test_invalid_price_input(entry,stop,target):
 assert size_addition(entry,stop,target,4000,4000,200)['shares']==0

def test_no_original_files_modified_by_sidecar(tmp_path):
 now=datetime.fromisoformat(CUT);snap={'generated_at':CUT,'as_of':END,'demo':False,'stocks':[{'symbol':'1234.TW','name':'測試','candles':bars(),'news':[]}]}
 write_json(tmp_path/'data/latest.json',snap);write_json(tmp_path/'data/market/TWII_INDEX.json',{'candles':bars()})
 before=(tmp_path/'data/latest.json').read_bytes()
 out=run(tmp_path,collect_news=False,fetch_prices=False,clock=lambda:now)
 assert (tmp_path/'data/latest.json').read_bytes()==before
 assert out['qwen_calls']==0 and not out['changed_saved_orders']
 assert (tmp_path/'data/context194/latest.json').exists()
 assert not (tmp_path/'data/system/qwen-state.json').exists()

def test_no_demo_as_real(tmp_path):
 write_json(tmp_path/'data/latest.json',{'demo':True,'generated_at':CUT})
 with pytest.raises(ValueError):run(tmp_path,False,False,clock=lambda:datetime.fromisoformat(CUT))

def test_source_future_rejected(tmp_path):
 write_json(tmp_path/'data/latest.json',{'demo':False,'generated_at':'2026-11-06T17:00:00+08:00'})
 with pytest.raises(ValueError):run(tmp_path,False,False,clock=lambda:datetime.fromisoformat(CUT))


def test_explicit_etf_fallback_never_renames_as_index(tmp_path):
 snap={'generated_at':CUT,'as_of':END,'demo':False,'stocks':[]}
 write_json(tmp_path/'data/latest.json',snap)
 write_json(tmp_path/'data/market/0050_TW.json',{'candles':bars()})
 out=run(tmp_path,False,False,clock=lambda:datetime.fromisoformat(CUT))
 assert out['market']['symbol']=='0050.TW'
 assert '非加權指數' in out['market']['name']
 assert any('不是加權指數' in x for x in out['errors'])

def test_no_fractional_existing_shares():
 assert size_addition(100,96,130,4000,8000,200,existing_shares=1.5)['status']=='invalid'


def test_missing_session_not_silently_compressed():
 x=bars();del x[-4]
 out=diagnose(x,CUT)
 assert out['state']=='missing' and out['missing_sessions']

def test_recovery_can_reach_nonzero_research_stage():
 x=bars()
 for i,r in enumerate(x):
  c=100+i*.6
  r.update(open=c-.2,high=c+.8,low=c-.8,close=c,volume=100000)
 out=diagnose(x,CUT,market={'state':'neutral','label':'平穩','price_date':END,'metrics':{'return_5d_pct':1}})
 assert out['state']=='reclaim' and out['research_stage']==2
 assert out['risk_budget_fraction_for_research']==.5
 assert not out['bottom_confirmed']

def test_market_crisis_reduces_not_increases_research_budget():
 x=bars()
 for i,r in enumerate(x):
  c=100+i*.6;r.update(open=c-.2,high=c+.8,low=c-.8,close=c,volume=100000)
 out=diagnose(x,CUT,market={'state':'falling','label':'急跌','price_date':END,'metrics':{'return_5d_pct':-10}})
 assert out['research_stage']==1 and out['risk_budget_fraction_for_research']==.25
