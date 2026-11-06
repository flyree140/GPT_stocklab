"""Separate, time-stamped evidence/downside sidecars; no order or snapshot rewrites."""
from __future__ import annotations
import argparse, hashlib
from pathlib import Path
from stocklab16.common import now, dt, read_json, write_json
from stocklab16.market import history
from stocklab16.taxonomy import group_items
from .evidence import Collector, relationship, topic_tags
from .downside import diagnose

CHANNELS={
 'ai_policy':('資料中心／AI政策風險','審批或資本支出變化 → 交付與收入認列時點風險 → 評價不確定性',
              '核對政策是建議／草案／已生效，以及公司實際客戶與收入曝險；不可直接寫成訂單取消'),
 'semiconductors':('海外半導體與台股連動假設','海外同業／ADR價格變化 → 風險偏好與折現 → 台股相關族群波動',
                   '價格連動不等於公司營收已衰退；需核對同業財測與公司資料'),
 'capital_flow':('資金與流動性壓力','外資與融資流向 → 買賣壓力／去槓桿 → 價格可能偏離短期基本面',
                 '用官方同日流向分辨個股與全市場；淨賣超不是外資真實成本'),
 'macro':('總體與法規曝險','政策／匯率／利率變化 → 成本、需求與折現率 → 依公司曝險判斷',
          '核對生效日期、實際曝險及避險政策；不預設所有公司方向相同'),
 'selloff':('市場已發生急跌','價格與市場廣度惡化 → 風險提高 → 評估止跌而不是把跌幅當買點',
             '這是結果描述，不能重複加成公司利空分，也不是已證明的下跌原因')}

def pathways(events):
 result=[]
 for key,(title,chain,missing) in CHANNELS.items():
  evidence=[e for e in events if key in {x['key'] for x in e.get('topics',[])}]
  if not evidence:continue
  result.append({'key':key,'title':title,'chain':chain,'basis':'報導議題＋研究假設，未證明因果',
   'needs_verification':missing,'evidence_ids':[e['id'] for e in evidence[:5]],
   'distinct_publishers':len({e.get('publisher') for e in evidence}),'independent_confirmations':None})
 return result

def run(root,collect_news=True,fetch_prices=True,collector=None,clock=None):
 root=Path(root);clock=clock or now;start=clock();snapshot_path=root/'data/latest.json'
 snap=read_json(snapshot_path,{}) or {}
 if not snap:raise ValueError('缺正式data/latest.json；不使用合成資料冒充今日市場')
 if snap.get('demo'):raise ValueError('正式研究拒絕合成快照，請先成功取得真實資料')
 if dt(snap['generated_at'])>start:raise ValueError('來源快照晚於目前時點')
 snapshot_hash=hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
 bench_path=root/'data/market/TWII_INDEX.json';bench=read_json(bench_path,{}) or {}
 benchmark_source='Yahoo Finance ^TWII日K；待與交易所複核'
 errors=[]
 if fetch_prices:
  rows=history('^TWII',start.date().isoformat(),160)
  if rows:
   bench={'symbol':'^TWII','as_of':start.date().isoformat(),'refreshed_at':clock().isoformat(),'candles':rows,'source':benchmark_source}
   write_json(bench_path,bench)
  else:errors.append('加權指數下載失敗；保留舊檔並檢查資料日，不補造新數字')
 collector=collector or Collector(root,clock=clock)
 current=collector.collect() if collect_news else []
 stocks=[]
 for old in snap.get('stocks',[]):
  symbol=old['symbol'];slug=symbol.replace('.','_')
  market_path=root/f'data/market/{slug}.json';market=read_json(market_path,{}) or {}
  bars=market.get('candles') or old.get('candles',[])
  seen=clock()
  # Only evidence actually observed before the sidecar calculation time.
  events=[]
  for e in old.get('news',[]):
   try:
    if dt(e.get('available_at') or e['published_at'])<=seen and 0<=(seen-dt(e['published_at'])).total_seconds()<=7*86400:events.append(e)
   except (ValueError,KeyError,TypeError):continue
  if collect_news:events=collector.enrich(events,old)
  grouped=group_items(events,old)
  for e in grouped:
   e.setdefault('content_status','provided_excerpt' if e.get('excerpt') else 'headline_only')
   e.setdefault('content_reason','舊快照保存的節錄' if e.get('excerpt') else '舊快照僅標題；本次未找到授權摘要')
   e.setdefault('topics',topic_tags(e.get('title','')+' '+e.get('excerpt','')))
   e['score_as_of']=old.get('analysis_at',snap.get('generated_at')) if 'impact_score' in e else None
  stocks.append({'symbol':symbol,'name':old.get('name',symbol),'sector':old.get('sector',''),
   'source_research_at':snap.get('generated_at'),'original_label':old.get('decision',{}).get('label'),
   'original_score':old.get('decision',{}).get('score'),'candles':bars,
   'price_source_sha256':hashlib.sha256(market_path.read_bytes()).hexdigest() if market_path.exists() else None,
   'events':grouped,'facts_at':old.get('facts',{}).get('available_at'),
   'original_research_unchanged':True})
 cutoff=clock().isoformat()
 market_diag=diagnose(bench.get('candles',[]),cutoff)
 benchmark_name='加權指數';benchmark_symbol='^TWII'
 # ^TWII providers may omit volume. Never fabricate volume to satisfy hygiene.
 # An explicitly named, contemporaneous ETF fallback is allowed only if clean.
 if market_diag['state'] in ('missing','stale'):
  fallback=read_json(root/'data/market/0050_TW.json',{}) or {}
  fdiag=diagnose(fallback.get('candles',[]),cutoff)
  if fdiag['state'] not in ('missing','stale','corporate_action'):
   errors.append('加權指數不足／落後；明確改用0050價格代理。不是加權指數，也不代表全市場廣度。')
   market_diag=fdiag;bench=fallback;benchmark_name='0050價格代理（非加權指數）';benchmark_symbol='0050.TW'
   benchmark_source='既有0050完整日K；不是加權指數／全市場資料'
 market_diag.update(symbol=benchmark_symbol,name=benchmark_name,price_source=bench.get('source',benchmark_source),
    breadth_status='未串接全市場同日漲跌家數，不用深度池冒充全市場')
 for s in stocks:
  from stocklab16.events import analyze
  updated=[]
  for event in s['events']:
   try:
    fresh=analyze(event,s,cutoff)
    fresh['original_score_at']=event.get('score_as_of')
    fresh['original_impact_score']=event.get('impact_score')
    fresh['current_analysis_mode']='CPU研究附檔，不修改原快照或冒稱Qwen重跑'
    updated.append(fresh)
   except (ValueError,KeyError):continue
  s['events']=updated
  from stocklab1932.institutional import attach
  try:flow,_=attach(root,s,cutoff)
  except Exception as exc:flow={'status':'missing','error':type(exc).__name__}
  s['downside']=diagnose(s['candles'],cutoff,market=market_diag,flow=flow)
  s['candles']=s['candles'][-80:]
  s['foreign_defense']=flow
  linked=[]
  for e in current:
   rel=relationship(s,e)
   if rel and e.get('topics'):linked.append({**e,'relation_assessment':rel})
  s['context_events']=linked[:8]
  s['missing']=['無完整即時報價；只用完整日K', '基本面／估值沒有因本次更新自動核實']
 market_events=[e for e in current if e.get('topics')][:35]
 payload={'version':'19.3.4','mode':'current_research_sidecar','generated_at':cutoff,
  'source_snapshot_at':snap.get('generated_at'),'source_snapshot_sha256':snapshot_hash,
  'market':market_diag,'market_candles':bench.get('candles',[])[-80:],
  'market_events':market_events,'pathways':pathways(market_events),
  'collection':collector.report(),'errors':errors,'stocks':stocks,
  'changed_original_labels':False,'changed_saved_orders':False,'qwen_calls':0,
  'note':'這是目前取得證據與價量的研究附檔；不能放回舊決策當作當時已知，也不重算原Qwen分數'}
 # Global context is a separate append-only sidecar. If it fails, keep local
 # analysis valid but report the failure; never substitute demo or suppress it.
 global_cfg=read_json(root/'config/global-research.json',{}) or {}
 if (collect_news or fetch_prices) and global_cfg.get('enabled',True):
  try:
   from .global_refresh import run as global_run
   global_payload=global_run(root,clock=clock)
   payload['global_context']={'path':'data/global194/latest.json','generated_at':global_payload['generated_at'],
    'risk':global_payload['risk'],'coverage':global_payload['coverage'],
    'source_snapshot_sha256':global_payload['source_snapshot_sha256']}
  except Exception as exc:
   payload['global_context']={'status':'failed','error':type(exc).__name__+': '+str(exc)[:240]}
 else:payload['global_context']={'status':'not_requested'}
 stamp=clock().strftime('%Y%m%dT%H%M%S%f')
 history_path=root/f'data/context194/runs/{stamp}.json'
 if history_path.exists():raise FileExistsError(history_path)
 write_json(history_path,payload);write_json(root/'data/context194/latest.json',payload)
 return payload

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--no-network',action='store_true');a=p.parse_args()
 result=run(Path(a.root).resolve(),collect_news=not a.no_network,fetch_prices=not a.no_network)
 print('Evidence/downside:',result['generated_at'],'stocks=',len(result['stocks']),'RSS=',result['collection']['rss_items'],'failures=',len(result['errors']))
