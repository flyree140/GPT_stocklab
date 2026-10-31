import json,hashlib,zipfile,io
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pytest
from stocklab1932.developer import register,evaluate,probe,sessions,run
from stocklab1932.coverage import select
from stocklab1932.foreign import defense
from stocklab1932.institutional import parse_twse,parse_tpex
from stocklab1932.collection import Collector,revenue_records,fetch_phrasebank
from stocklab1932.facts import observed_facts
from stocklab1932.archive import extract
TZ=ZoneInfo('Asia/Taipei')
CAL={'start':'2026-01-01','end':'2026-12-31','closed':[]}
CUT='2026-09-10T20:00:00+08:00'

def rows(n=22):
 dates=[];d=datetime(2026,8,10)
 while len(dates)<n:
  if d.weekday()<5:dates.append(d.date().isoformat())
  d+=timedelta(days=1)
 return [dict(date=d,open=100+i,high=104+i,low=98+i,close=101+i,volume=1000000) for i,d in enumerate(dates)]

def rec(at=CUT,registered='2026-09-10T21:00:00+08:00'):
 return {'generated_at':at,'registered_at':registered,'source_sha256':'a'*64,'mode':'live','rows':[{'symbol':'2330.TW','etf':False,'original_code':'avoid','original_label':'避開','score':20}]}

def market():
 return {s:{d:dict(date=d,open=100,high=103,low=98,close=102,volume=100000) for d in sessions(CUT,CAL,25)} for s in ['2330.TW','0050.TW']}

def test_next_open_after_cutoff():
 assert sessions(CUT,CAL,1)==['2026-09-11']
 assert sessions('2026-09-11T10:00:00+08:00',CAL,1)==['2026-09-14']

def test_no_weekday_guess_past_calendar():
 with pytest.raises(ValueError,match='calendar_pending'):sessions('2026-12-31T20:00:00+08:00',CAL,2)

def test_every_signal_even_avoid():
 r=evaluate([rec()],market(),CAL,'2026-10-30T20:00:00+08:00')
 assert len(r['rows'])==1 and r['rows'][0]['original_code']=='avoid'
 assert r['rows'][0]['outcomes']['5']['status']=='mature'
 assert r['rows'][0]['sample_mode']=='prospective_registered'

def test_retrospective_not_forward():
 r=evaluate([rec(registered='2026-10-30T20:00:00+08:00')],market(),CAL,'2026-10-30T20:00:00+08:00')
 assert r['rows'][0]['sample_mode']=='retrospective_reference'

def test_future_signal_not_in_results():
 assert not evaluate([rec()],market(),CAL,'2026-09-09T20:00:00+08:00')['rows']

def test_duplicate_same_entry_uses_last_preopen():
 a=rec();b=rec('2026-09-10T22:00:00+08:00','2026-09-10T23:00:00+08:00');b['source_sha256']='b'*64
 r=evaluate([a,b],market(),CAL,'2026-10-30T20:00:00+08:00')
 assert len(r['rows'])==1 and r['rows'][0]['source_sha256']=='b'*64

def test_unmatured_not_win():
 r=evaluate([rec()],market(),CAL,'2026-09-11T14:00:00+08:00')
 assert r['rows'][0]['outcomes']['5']['status']=='pending'
 assert r['summary']['prospective_registered']['5']['n']==0

def test_missing_bar_not_skipped():
 m=market();del m['2330.TW']['2026-09-11'];r=evaluate([rec()],m,CAL,'2026-10-30T20:00:00+08:00')
 assert r['rows'][0]['outcomes']['5']['status']=='missing_price'

def test_corporate_action_excludes_probe():
 m=market();m['2330.TW']['2026-09-11']['corporate_action']=True
 assert evaluate([rec()],m,CAL,'2026-10-30T20:00:00+08:00')['rows'][0]['outcomes']['1']['status']=='corporate_action'

def test_negative_after_cost_when_flat():
 m=market();m['2330.TW']['2026-09-11']['close']=100
 r=probe({'symbol':'2330.TW','etf':False},['2026-09-11'],m,10000,'2026-10-30T20:00:00+08:00')
 assert r['pnl']<0 and r['shares']>0 and r['not_actual_fill']

def test_register_all_and_immutable(tmp_path):
 s={'as_of':'2026-09-10','generated_at':CUT,'stocks':[{'symbol':'2330.TW','decision':{}},{'symbol':'2317.TW','decision':{}}]}
 raw=json.dumps(s).encode();a=register(s,'data/x.json',raw,tmp_path,CUT);b=register(s,'data/x.json',raw,tmp_path,'2026-10-30T00:00:00+08:00')
 assert len(a['rows'])==2 and a['registered_at']==b['registered_at']

def test_register_future_refused(tmp_path):
 with pytest.raises(ValueError):register({'generated_at':CUT},'x',b'x',tmp_path,'2026-09-09T00:00:00+08:00')

def test_coverage_no_future_rotation():
 core=[{'symbol':f'{2000+i}.TW'} for i in range(20)];cat=core+[{'symbol':f'{3000+i}.TWO'} for i in range(100)]
 a,meta=select(core,[],cat,20,8,datetime(2026,10,30,8,tzinfo=TZ));b,_=select(core,[],cat,20,8,datetime(2026,10,30,21,tzinfo=TZ))
 assert len(a)==20 and len({x['symbol'] for x in a})==20
 assert a[:12]==b[:12] and a[12:]!=b[12:] and meta['unselected_not_analyzed']

def test_favorites_not_dropped_by_rotation():
 a,_=select([], [{'symbol':'8299.TWO'}],[{'symbol':'2330.TW'}],20,8,datetime(2026,10,30,8,tzinfo=TZ))
 assert a[0]['symbol']=='8299.TWO'

def flows(bs,net=100):return [{'date':b['date'],'available_at':b['date']+'T18:00:00+08:00','foreign_net':net} for b in bs]

def test_foreign_proxy_not_real_cost():
 bs=rows(20);f=flows(bs);o=defense(bs,f,CUT)
 assert o['status']=='available' and not o['actual_institutional_cost'] and o['matched_sessions']==20
 assert o['value']==round(sum((b['high']+b['low']+b['close'])/3 for b in bs)/20,4)

def test_foreign_requires_missing_window():
 bs=rows(20);f=flows(bs);f.pop(2);assert defense(bs,f,CUT)['status']=='partial'

def test_foreign_future_availability_rejected():
 bs=rows(20);f=flows(bs);f[-1]['available_at']='2027-01-01T18:00:00+08:00';assert defense(bs,f,CUT)['status']=='stale'

def test_foreign_no_positive_not_line():assert defense(rows(20),flows(rows(20),-100),CUT)['value'] is None

def test_foreign_corporate_action_not_bridge():
 bs=rows(20);bs[-3]['corporate_action']=True;assert defense(bs,flows(bs),CUT)['status']=='corporate_action'

def test_twse_precise_date_fields():
 obj={'stat':'OK','date':'20261030','fields':['證券代號','外陸資買進股數(不含外資自營商)','外陸資賣出股數(不含外資自營商)','投信買賣超股數'],'data':[['2330','1,000','300','120']]}
 r=parse_twse(obj,'2026-10-30','2026-10-31T10:00:00+08:00');assert r[0]['foreign_net']==700 and r[0]['dealer_net'] is None
 with pytest.raises(ValueError):parse_twse(obj,'2026-10-29',CUT)

def test_tpex_not_twse_substitute():
 with pytest.raises(ValueError):parse_tpex([{'Code':'8299','Date':'20261030'}],'2026-10-30',CUT)

def test_real_revenue_draft_not_human_label():
 r=revenue_records([{'公司代號':'2330','公司名稱':'台積電','資料年月':'11509','營業收入-當月營收':'100'}],{'fetched_at':'2026-10-31T10:00:00+08:00','url':'https://openapi.twse.com.tw/x','sha256':'a'*64})[0]
 assert not r['synthetic'] and not r['review']['approved'] and not r['documents'][0]['training_allowed']
 assert r['decision_at'].startswith('2026-10-31') and r['gold']['price_direction']=='unknown'

def test_phrasebank_requires_license(tmp_path):
 with pytest.raises(ValueError,match='CC BY'):fetch_phrasebank(Collector(tmp_path),tmp_path)

def test_collector_never_arbitrary_host(tmp_path):
 with pytest.raises(ValueError):Collector(tmp_path).get('https://random.example/news')

def test_facts_observed_not_historical():
 s={'facts':{'available_at':'2026-10-31T00:00:00+08:00','eps':10,'pe':20}}
 assert observed_facts(s,CUT)==[]
 assert len(observed_facts(s,'2026-11-01T00:00:00+08:00'))==2

def test_archive_does_not_copy_old_model_answer(tmp_path):
 z=tmp_path/'a.zip';snap={'generated_at':CUT,'stocks':[{'symbol':'2330.TW','news':[{'title':'營收增加','published_at':'2026-09-10T09:00:00+08:00','impact_score':99,'mechanism':'舊胡說'}]}]}
 with zipfile.ZipFile(z,'w') as f:f.writestr('repo/data/snapshots/a.json',json.dumps(snap))
 out=tmp_path/'queue.jsonl';rep=extract(z,out);r=json.loads(out.read_text());assert not r['review']['approved'] and r['gold']['price_direction']=='unknown' and '舊胡說' not in out.read_text() and rep['selected']==1


def test_tpex_documented_english_field_aliases():
 row={'Date':'1151030','SecuritiesCompanyCode':'8299','Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference':'-1300','SecuritiesInvestmentTrustCompanies-Difference':'30','Dealers-Difference':'0'}
 out=parse_tpex([row],'2026-10-30','2026-10-30T18:00:00+08:00')
 assert out[0]['symbol']=='8299.TWO' and out[0]['foreign_net']==-1300 and out[0]['dealer_net']==0
