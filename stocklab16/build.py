from __future__ import annotations
import argparse, os
import requests
from datetime import date
from .common import ROOT,now,read_json,write_json,digest
from .market import history,current_info,market_score
from .news import fetch as fetch_news
from .events import group_items,analyze
from .decision import decide
from .qwen import QwenHints


def load_stocks(): return read_json(ROOT/'config'/'stocks.json',{}).get('stocks',[])

def favorite_metas(base):
    url=os.getenv('FAVORITES_FEED_URL','').strip(); token=os.getenv('FAVORITES_READ_TOKEN','').strip()
    if not url or not token:return []
    try:
        r=requests.post(url,data={'action':'feed','token':token},timeout=20); r.raise_for_status(); symbols=(r.json().get('symbols') or [])[:30]
    except Exception as exc:
        print('favorites feed unavailable',exc); return []
    universe=read_json(ROOT/'data'/'universe.json',{}).get('instruments',[]); by={x.get('symbol'):x for x in universe}; existing={x['symbol'] for x in base}; out=[]
    for symbol in symbols:
        if symbol in existing:continue
        u=by.get(symbol)
        if u:out.append({'symbol':symbol,'name':u.get('name',symbol),'sector':u.get('sector',''),'aliases':[]})
    return out

def peer_percentiles(stocks):
    vals=sorted((s['facts']['pe'],i) for i,s in enumerate(stocks) if s['facts'].get('pe') and s['facts']['pe']>0)
    n=len(vals)
    for rank,(_,idx) in enumerate(vals): stocks[idx]['facts']['pe_peer_percentile']=rank/max(1,n-1)*100

def run(as_of):
    base=load_stocks(); metas=(favorite_metas(base)+base)[:int(os.getenv('DEEP_STOCK_LIMIT','20'))]; qwen=QwenHints(); benchmark=history('0050.TW',as_of,260); mscore=market_score(benchmark)
    built=[]
    for meta in metas:
        bars=history(meta['symbol'],as_of,360); facts=current_info(meta['symbol']) if as_of==date.today().isoformat() else {'revenue_yoy':None,'eps':None,'pe':None}
        raw=fetch_news(meta['name'],meta['symbol'],as_of,3,8); grouped=group_items(raw,meta); events=[]
        for item in grouped:
            hint=None
            if item.get('title') and any(k in item['title'] for k in ('合作','訂單','營收','財報','股東會','增資','停工','聯名卡','5G','AI')):
                hint=qwen.hint(item['title'],item.get('excerpt',''))
            try: events.append(analyze(item,meta,as_of+'T23:59:59+08:00',hint))
            except Exception as exc: print('event skipped',exc)
        built.append({'symbol':meta['symbol'],'name':meta['name'],'kind':meta.get('kind','stock'),'sector':meta.get('sector',''),'candles':bars,'facts':facts,'news':events,'market_score':mscore})
    peer_percentiles(built)
    for s in built:s['decision']=decide(s,as_of)
    top=sorted([s for s in built if s['decision']['code'] in ('conditional_buy','watch')],key=lambda x:x['decision']['score'],reverse=True)[:5]
    generated=now().isoformat(timespec='seconds'); payload={'version':'16.0','as_of':as_of,'generated_at':generated,'stocks':built,'top_picks':[s['symbol'] for s in top],'qwen_used':qwen.used,'note':'研究與模擬用途，不構成投資建議。'}
    snap=ROOT/'data'/'snapshots'/f'{as_of}.json'; old=read_json(snap,{}) or {}; payload['run_count']=old.get('run_count',0)+1; write_json(snap,payload)
    manifest=read_json(ROOT/'data'/'manifest.json',{'snapshots':[]}) or {'snapshots':[]}; rows=[r for r in manifest.get('snapshots',[]) if r.get('date')!=as_of]; rows.append({'date':as_of,'path':f'data/snapshots/{as_of}.json','run_count':payload['run_count'],'stock_count':len(built),'generated_at':generated}); rows.sort(key=lambda r:r['date'],reverse=True); write_json(ROOT/'data'/'manifest.json',{'version':'16.0','latest':max(r['date'] for r in rows),'snapshots':rows})
    if not read_json(ROOT/'data'/'latest.json') or as_of>=read_json(ROOT/'data'/'latest.json',{}).get('as_of',''): write_json(ROOT/'data'/'latest.json',payload)
    for s in built:
        market_path=ROOT/'data'/'market'/f"{s['symbol'].replace('.','_')}.json"
        existing=read_json(market_path,{}) or {}
        if not existing.get('as_of') or as_of>=existing.get('as_of',''):
            write_json(market_path,{'symbol':s['symbol'],'as_of':as_of,'candles':s['candles']})
    print('built',as_of,'stocks',len(built),'qwen',qwen.used)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--as-of',default=date.today().isoformat()); args=p.parse_args(); run(args.as_of)
