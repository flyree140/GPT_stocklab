from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,copy
import pytest
from stocklab194.global_sources import INSTRUMENTS,GlobalCollector,parse_feed,parse_yahoo,parse_fred,close_boundary
from stocklab194.global_rules import summarize_market,currency_crosses,risk_regime,classify_event,stock_exposures,assemble
from stocklab194.global_refresh import run
from stocklab16.common import write_json
AT=datetime.fromisoformat('2026-11-06T18:00:00+08:00')
LOOK={s['key']:s for s in INSTRUMENTS}
def spec(key,values=None,end=None):
 s=copy.deepcopy(LOOK[key]);end=end or ('2026-11-05' if s['region']=='US' or s['kind'] in ('fx','dollar_index') else '2026-11-06')
 dates=[];d=datetime.fromisoformat(end)
 while len(dates)<65:
  if d.weekday()<5:dates.append(d.date().isoformat())
  d-=timedelta(days=1)
 dates.reverse();values=values or [100+i*.1 for i in range(len(dates))]
 dates=dates[-len(values):]
 s['bars']=[dict(date=d,value=v,available_at=AT.isoformat(),observed_at=AT.isoformat(),session_complete_after=close_boundary(d,s).isoformat()) for d,v in zip(dates,values)]
 return s

def event(title='US election policy tariff proposal',**extra):
 return dict(id='test',title=title,url='https://example.org/a',publisher='Test source',excerpt='',published_at='2026-11-06T01:00:00+08:00',available_at=AT.isoformat(),**extra)

def qpayload(s,day='2026-11-05',value=100):
 stamp=datetime.fromisoformat(day+'T09:30:00').replace(tzinfo=__import__('zoneinfo').ZoneInfo(s['timezone'])).timestamp()
 return json.dumps({'chart':{'result':[{'meta':{'symbol':s['symbol']},'timestamp':[stamp],
  'indicators':{'quote':[{'close':[value]}]}}],'error':None}}).encode()

def test_us_dst_cutoff():
 s=LOOK['NASDAQ']
 assert close_boundary('2026-11-05',s).astimezone(timezone.utc).hour==21
 assert close_boundary('2026-10-29',s).astimezone(timezone.utc).hour==20

def test_no_us_close_before_market_finish():
 s=LOOK['NASDAQ'];r=parse_yahoo(qpayload(s,'2026-11-06'),s,'2026-11-06T23:45:00+08:00');assert r==[]

def test_index_needs_no_volume():
 s=LOOK['NASDAQ'];r=parse_yahoo(qpayload(s),s,AT.isoformat());assert len(r)==1 and r[0]['value']==100

def test_future_bar_not_used():
 s=LOOK['NASDAQ'];assert parse_yahoo(qpayload(s,'2026-11-09'),s,AT.isoformat())==[]

def test_wrong_symbol_rejected():
 with pytest.raises(ValueError,match='symbol'):parse_yahoo(qpayload(LOOK['NASDAQ']),LOOK['SPX'],AT.isoformat())

@pytest.mark.parametrize('v',[float('nan'),float('inf'),-3,0,None])
def test_bad_price_dropped(v):assert parse_yahoo(qpayload(LOOK['SPX'],value=v),LOOK['SPX'],AT.isoformat())==[]

def test_fx_inverse_not_negative_approximation():
 m=summarize_market(spec('USDTWD',[32,32,32,32,32,33]),AT.isoformat())
 assert m['local_appreciation_1d_pct']==round((32/33-1)*100,4)
 assert '貶值' in m['direction_label'] and m['change_1d_pct']>0

def test_fx_appreciation():
 m=summarize_market(spec('USDJPY',[150,150,150,150,150,148]),AT.isoformat());assert m['local_appreciation_1d_pct']>0 and '升值' in m['direction_label']

def test_fx_cross_aligned_formula():
 a=summarize_market(spec('USDTWD',[32,32,32,32,32,31]),AT.isoformat())
 b=summarize_market(spec('USDJPY',[150,150,150,150,150,153]),AT.isoformat())
 x=currency_crosses([a,b])[0];assert x['twd_appreciation_5d_pct']==round(((32/150)/(31/153)-1)*100,4)

def test_cross_missing_window():
 a=summarize_market(spec('USDTWD',[32]),AT.isoformat());b=summarize_market(spec('USDJPY',[150]),AT.isoformat());assert currency_crosses([a,b])[0]['status']=='insufficient'

def test_yields_use_bp():
 m=summarize_market(spec('US10Y',[4.,4.,4.,4.,4.,4.15]),AT.isoformat());assert m['change_1d_bp']==15 and m['change_1d_pct'] is None

def test_fred_missing_values_and_future():
 b=b'observation_date,DGS10\n2026-11-03,.\n2026-11-04,4.5\n2026-11-09,4.6\n'
 rs=parse_fred(b,LOOK['US10Y'],AT.isoformat());assert len(rs)==1 and rs[0]['value']==4.5 and rs[0]['available_at']==AT.isoformat()

def test_us_local_day_not_taiwan_day():
 m=summarize_market(spec('NASDAQ'),AT.isoformat());assert m['price_date']=='2026-11-05' and m['status']=='recent'

def test_old_quote_not_safe():
 m=summarize_market(spec('NASDAQ',end='2026-10-20'),AT.isoformat());assert m['status']=='stale' and not m['usable']

def test_future_observed_data_rejected():
 s=spec('SPX');s['bars'][-1]['available_at']='2026-12-01T00:00:00+08:00'
 m=summarize_market(s,AT.isoformat());assert m['rejected_records']==1 and m['price_date']<s['bars'][-1]['date']

def test_us_three_indices_do_not_count_three_countries():
 ms=[summarize_market(spec(k,[100]*5+[95]),AT.isoformat()) for k in ['SPX','NASDAQ','SOX']]
 risk=risk_regime(ms);assert risk['stressed_regions']==['US'] and risk['new_risk_multiplier'] is None

def test_cross_market_stress():
 ms=[summarize_market(spec(k,[100]*5+[95]),AT.isoformat()) for k in ['SPX','NIKKEI','KOSPI']]
 risk=risk_regime(ms);assert risk['code']=='cross_market_stress' and risk['new_risk_multiplier']==.5

def test_missing_all_not_zero_risk():assert risk_regime([])['new_risk_multiplier'] is None

def test_fx_shock_only_uncertainty_not_company_direction():
 ms=[summarize_market(spec(k,[100]*6),AT.isoformat()) for k in ['SPX','NIKKEI','KOSPI']]
 ms.append(summarize_market(spec('USDTWD',[32]*5+[33]),AT.isoformat()))
 r=risk_regime(ms);assert r['code']=='elevated' and any(x['kind']=='fx_volatility' for x in r['signals'])

@pytest.mark.parametrize('title,stage',[
 ('US election result lifts policy expectations','election_report'),
 ('US election winner proposes tariffs','proposal'),
 ('Election policy tariff takes effect','effective_claim'),
 ('Tariff proposal suspended by court','suspended_or_disputed'),
 ('Election campaign promise on tariffs','campaign_promise'),
])
def test_election_not_law(title,stage):
 e=classify_event(event(title),AT.isoformat());assert e['policy_stage']==stage and e['legal_effect_verified'] is False and e['effective_at'] is None

def test_future_news_excluded():
 e=event();e['published_at']='2026-11-07T00:00:00+08:00';assert classify_event(e,AT.isoformat()) is None

def test_no_invented_stock_exposure():
 ev=classify_event(event(),AT.isoformat());s=stock_exposures([{'symbol':'TEST.TW','name':'Test','sector':'半導體'}],[ev],[],AT.isoformat())[0]
 assert s['measured_net_exposure'] is None and all(x['net_company_direction']=='unknown' for x in s['channels'])

def test_future_profile_not_imported():
 ps={'TEST.TW':[{'claim':'USD revenue','source_url':'https://example.org','available_at':'2027-01-01T00:00:00+08:00','published_at':AT.isoformat(),'reviewed':True}]}
 assert stock_exposures([{'symbol':'TEST.TW'}],[],[],AT.isoformat(),ps)[0]['reviewed_exposure_documents']==[]

def test_rss_html_clean_and_time_kept():
 b=b'<rss><channel><item><title>US election policy</title><link>https://example.org/a</link><pubDate>Fri, 06 Nov 2026 07:00:00 GMT</pubDate><description><![CDATA[<script>bad()</script><p>Test policy introduction with more than forty characters, and it is not the title.</p>]]></description></item></channel></rss>'
 x=parse_feed(b,{'name':'test'},AT.isoformat())[0];assert 'bad()' not in x['excerpt'] and x['available_at']==AT.isoformat() and x['training_allowed'] is False

def test_atom_feed():
 b=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Fed rate decision</title><link href="https://example.org/a"/><updated>2026-11-06T07:00:00Z</updated><summary>Test policy introduction with more than forty characters, and it is not the title.</summary></entry></feed>'
 assert len(parse_feed(b,{'name':'test'},AT.isoformat()))==1

def test_dtd_refused():
 with pytest.raises(ValueError):parse_feed(b'<!DOCTYPE x><rss/>',{'name':'test'},AT.isoformat())

def test_collector_limit_and_cache(tmp_path):
 write_json(tmp_path/'config/global-research.json',{'max_quote_requests':1,'max_news_requests':0})
 calls=[]
 def get(url,**kw):calls.append(url);return qpayload(LOOK['SPX'])
 c=GlobalCollector(tmp_path,fetcher=get,clock=lambda:AT);q,e=c.collect();assert len(calls)==1 and len(q)==19
 c=GlobalCollector(tmp_path,fetcher=get,clock=lambda:AT);q,e=c.collect()
 assert c.report()['sources'][0]['state']=='cache'
 assert q[0]['bars'][0]['observed_at']==AT.isoformat()

def test_failure_never_fabricates(tmp_path):
 def bad(*a,**k):raise TimeoutError('offline')
 c=GlobalCollector(tmp_path,fetcher=bad,clock=lambda:AT);q,e=c.collect()
 assert c.quote_requests==19 and c.news_requests==8 and not e and all(not x['bars'] for x in q)
 assert all(x['state']=='failed' for x in c.status)

def test_append_only_no_original_mutation(tmp_path):
 snap={'generated_at':'2026-11-06T15:00:00+08:00','stocks':[{'symbol':'TEST.TW','name':'Test'}]}
 p=tmp_path/'data/latest.json';write_json(p,snap);before=p.read_bytes()
 payload=run(tmp_path,clock=lambda:AT,network=False)
 assert p.read_bytes()==before and payload['qwen_calls']==0 and payload['risk']['code']=='insufficient'
 with pytest.raises(FileExistsError):run(tmp_path,clock=lambda:AT,network=False)

def test_production_rejects_demo(tmp_path):
 write_json(tmp_path/'data/latest.json',{'generated_at':AT.isoformat(),'demo':True})
 with pytest.raises(ValueError,match='合成'):run(tmp_path,clock=lambda:AT,network=False)

def test_future_source_rejected(tmp_path):
 write_json(tmp_path/'data/latest.json',{'generated_at':'2027-01-01T00:00:00+08:00'})
 with pytest.raises(ValueError,match='future'):run(tmp_path,clock=lambda:AT,network=False)

def test_timezone_korea_close_is_taipei_1430_plus_buffer():
 ready=close_boundary('2026-11-06',LOOK['KOSPI']).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Taipei'))
 assert (ready.hour,ready.minute)==(15,15)

def test_empty_or_future_feed_not_counted():
 b=b'<rss><channel><item><title>US election news</title><link>https://example.org/a</link><pubDate>Fri, 06 Nov 2099 07:00:00 GMT</pubDate></item></channel></rss>'
 assert parse_feed(b,{'name':'test'},AT.isoformat())==[]

def test_weekend_bar_excluded():
 s=LOOK['NASDAQ'];assert parse_yahoo(qpayload(s,'2026-10-31'),s,AT.isoformat())==[]

def test_no_stress_never_claims_buy_signal():
 ms=[summarize_market(spec(k,[100]*6),AT.isoformat()) for k in ['SPX','NIKKEI','KOSPI']]
 r=risk_regime(ms);assert r['new_risk_multiplier']==1 and r['bottom_probability'] is None and not r['calibrated']

def test_taiwan_word_is_not_ai_topic():
 e=classify_event(event('Taiwan dollar moves on yen trading'),AT.isoformat())
 assert 'us_tech' not in {t['key'] for t in e['topics']}
