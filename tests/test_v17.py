import math
import pytest
from stocklab17.calendar import expected_close,is_session,covered
from stocklab17.hygiene import clean_bars
from stocklab17.planner import size_position,ledger,validate_account,history_reference
from stocklab17.audit import outcome,stats

def bar(day='2026-10-16',**kw):return {'date':day,'open':100,'high':102,'low':98,'close':101,'volume':1000,**kw}
@pytest.mark.parametrize('at,expected',[('2026-10-20T01:00:00+08:00','2026-10-19'),('2026-09-28T18:00:00+08:00','2026-09-24'),('2026-10-12T08:59:00+08:00','2026-10-08'),('2026-10-26T18:00:00+08:00','2026-10-23')])
def test_exchange_calendar(at,expected):assert expected_close(at)==expected
@pytest.mark.parametrize('day',['2026-09-20','2026-09-25','2026-09-28','2026-10-09','2026-10-26'])
def test_closed_days(day):assert not is_session(day)
def test_unverified_year():assert not covered('2027-01-02')
def test_quarantine():
    good,bad=clean_bars([bar('2026-09-20'),bar()]);assert len(good)==len(bad)==1
@pytest.mark.parametrize('kwargs',[{'volume':0},{'low':110},{'close':float('nan')}])
def test_invalid_price(kwargs):assert not clean_bars([bar(**kwargs)])[0]
def test_cutoff():assert not clean_bars([bar()], '2026-10-16T10:00:00+08:00')[0]
def test_fee_aware_size():
    z=size_position(156.5,153.5,164.5,{});assert z['quantity']==118;assert z['planned_stop_loss']<=500;assert z['buy_cash']<=20000
    assert -ledger(119,156.5,153.5,validate_account({}))['pnl']>500
    assert z['flat_scenario']['pnl']<0

def test_lot():assert size_position(156.5,153.5,164.5,{'lot_size':1000})['quantity']==0
@pytest.mark.parametrize('equity',[0,-100,math.nan,math.inf])
def test_invalid_account(equity):
    with pytest.raises(ValueError):size_position(156.5,153.5,164.5,{'equity':equity})
def test_sector_cap():
    assert size_position(156.5,153.5,164.5,{'holdings':[{'market_value':39900,'planned_risk':400,'sector':'金融'}]},sector='金融')['quantity']==0

def test_total_risk():
    assert size_position(156.5,153.5,164.5,{'holdings':[{'market_value':20000,'planned_risk':1499,'sector':'其他'}]})['quantity']==0

def test_max_positions():
    h=[{'market_value':1000,'planned_risk':20,'sector':'其他'}]*3
    assert size_position(156.5,153.5,164.5,{'holdings':h})['quantity']==0

def test_not_expected_return():
    r=history_reference([],{'symbol':'2881.TW','decision':{'code':'watch'}},'2026-10-20T01:00:00+08:00',5)
    assert r['n']==0 and r['mean_net'] is None and not r['strategy_match']

def test_pending():
    r={'entry_date':'2026-10-16','symbol':'2881.TW','etf':False};m={'2881.TW':{'2026-10-16':bar()}}
    assert outcome(r,m,['2026-10-16'],5,{'2026-10-16':bar()})['status']=='pending'

def test_corporate_action():
    r={'entry_date':'2026-10-16','symbol':'2881.TW','etf':False};m={'2881.TW':{'2026-10-16':bar(corporate_action=True)}}
    assert outcome(r,m,['2026-10-16'],1,{'2026-10-16':bar()})['status']=='corporate_action'

def test_empty():assert stats([],5)['mean_net'] is None
