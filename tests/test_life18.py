from stocklab18.prepare import parse_date,parse_quotes,verify_stock
from stocklab18.report import buy,sell,settle,scenario
from stocklab17.calendar import SEED
import math

def test_official_date_required():
    assert parse_quotes([{'Code':'2330','ClosingPrice':'100'}],'twse')=={}
def test_minguo():
    assert parse_date('115/10/20')=='2026-10-20'
    assert parse_date('20261020')=='2026-10-20'
    assert parse_date('bad') is None
    assert parse_date('2026-13-01') is None

def test_quote_matches_only_same_day():
    assert verify_stock({'date':'2026-10-20','close':100},{'date':'2026-10-19','close':100})['status']=='date_mismatch'
    assert verify_stock({'date':'2026-10-20','close':100},{'date':'2026-10-20','close':101})['status']=='price_mismatch'
    assert verify_stock({'date':'2026-10-20','close':100},{'date':'2026-10-20','close':100})['status']=='matched'
    assert verify_stock({'date':'2026-10-20','close':100},None)['status']=='unverified'

def test_minimum_commission():
    assert buy(1,100)['cash']==120.1
    assert sell(1,100)['cash']<80

def test_t_plus_two_holiday():assert settle('2026-09-24')=='2026-09-30'

def test_original_no_buys_no_profit():
    b={'date':'2026-09-11','open':100,'high':102,'low':99,'close':101,'volume':10000}
    r={'generated_at':'2026-09-10T20:00:00+08:00','symbol':'2881.TW','name':'富邦金','etf':False,'issues':[],'original_code':'watch','top_pick':True,'score':60}
    out=scenario('strict',[r],{'0050.TW':{'2026-09-11':b}},'2026-09-10','2026-10-20')
    assert out['equity']==8000 and out['net_pnl']==0 and len(out['trades'])==0

def test_no_future_information_used_for_entry():
    b={'date':'2026-09-11','open':100,'high':102,'low':99,'close':101,'volume':10000}
    r={'generated_at':'2026-09-11T10:00:00+08:00','symbol':'2881.TW','name':'富邦金','etf':False,'issues':[],'original_code':'watch','top_pick':True,'score':60}
    out=scenario('ranked',[r],{'0050.TW':{'2026-09-11':b},'2881.TW':{'2026-09-11':b}},'2026-09-10','2026-09-11')
    assert out['open_position'] is None


def test_nonfinite_official_prices_never_certify():
    for v in ['NaN','Infinity','-Infinity','0','-2']:
        assert parse_quotes([{'Code':'2330','Date':'20261020','ClosingPrice':v}],'twse')=={}
    for price in [float('nan'),float('inf'),0,-1,None]:
        assert verify_stock({'date':'2026-10-20','close':price},{'date':'2026-10-20','close':100})['status']=='unverified'
        assert verify_stock({'date':'2026-10-20','close':100},{'date':'2026-10-20','close':price})['status']=='unverified'
