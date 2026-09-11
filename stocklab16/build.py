"""Daily bounded collector. Never commits empty success or overwrites old run files."""
from __future__ import annotations
import argparse,os,re,requests
from datetime import date
from .common import ROOT,now,read_json,write_json,dt
from .storage import settings_file,store,validate_snapshot
from .market import history,current_info,market_score
from .news import fetch as fetch_news
from .events import group_items,analyze,categorize
from .decision import decide
from .qwen import QwenHints

def load_stocks():return read_json(settings_file('stocks'),{}).get('stocks',[])
def favorite_metas(base):
    url=os.getenv('FAVORITES_FEED_URL','').strip();token=os.getenv('FAVORITES_READ_TOKEN','').strip()
    if not url or not token:return []
    try:
        r=requests.post(url,data={'action':'feed','token':token},timeout=20);r.raise_for_status();symbols=r.json().get('symbols',[])[:30]
    except Exception as exc:print('favorites unavailable:',type(exc).__name__);return []
    rows=read_json(ROOT/'data/universe.json',{}).get('instruments',[])+base;idx={x['symbol']:x for x in rows}
    return [idx[s] for s in symbols if s in idx]

def peer_percentiles(stocks):
    groups={}
    for s in stocks:
        f=s.get('facts',{});pe=f.get('pe');sector=f.get('issuer_sector')
        # Require data-provider industry, not broad cross-sector hand-picked labels.
        if sector and isinstance(pe,(int,float)) and pe>0:groups.setdefault(sector,[]).append(s)
    for sector,rows in groups.items():
        if len(rows)<5:continue
        for rank,s in enumerate(sorted(rows,key=lambda s:s['facts']['pe'])):
            s['facts'].update(pe_peer_percentile=rank/(len(rows)-1)*100,peer_count=len(rows),peer_sector=sector)

def run(as_of,force=False):
    day=date.fromisoformat(as_of);today=now().date()
    if day>today:raise ValueError('Future as_of is forbidden')
    historical=day<today
    base=load_stocks();metas=([] if historical else favorite_metas(base))+base
    metas=list({m['symbol']:m for m in metas}.values())[:max(1,min(30,int(os.getenv('DEEP_STOCK_LIMIT','20'))))]
    qwen=QwenHints();qwen.enabled=qwen.enabled and not historical
    benchmark=history('0050.TW',as_of,260);mscore=market_score(benchmark)
    cutoff=as_of+'T23:59:59+08:00' if historical else now().isoformat()
    built=[];failures=[]
    curated=read_json(ROOT/f'data/curated/{as_of}.json',{}) or {}
    for meta in metas:
        print('Fetching',meta['symbol'],flush=True)
        bars=history(meta['symbol'],as_of,520)
        if not bars:failures.append(meta['symbol']);continue
        facts=current_info(meta['symbol']) if not historical else {'source':'historical current facts disabled'}
        raw=fetch_news(meta['name'],meta['symbol'],as_of,3,8)+curated.get(meta['symbol'],[])
        safe=[]
        for item in raw:
            try:
                if max(dt(item['published_at']),dt(item.get('available_at') or item['published_at']))<=dt(cutoff):safe.append(item)
            except (ValueError,KeyError):continue
        grouped=group_items(safe,meta);events=[]
        for item in grouped:
            # Numeric, clear and low-value stories do not spend a generation call.
            hint=qwen.hint(item['title'],item.get('excerpt','')) if categorize(item) in ('unclear','partnership','capital','orders','macro') else None
            try:events.append(analyze(item,meta,cutoff,hint))
            except (ValueError,KeyError) as exc:print('Excluded event:',str(exc)[:120])
        built.append({**meta,'candles':bars,'facts':facts,'news':events,'market_score':mscore})
    if not built:raise RuntimeError('No usable price data; retaining all prior production files')
    peer_percentiles(built)
    for s in built:s['decision']=decide(s,as_of)
    top=[s['symbol'] for s in sorted(built,key=lambda x:x['decision']['score'],reverse=True) if s['decision']['code'] in ('conditional_buy','watch') and s['decision']['score']>=50][:5]
    payload={'version':'16.1.2','as_of':as_of,'generated_at':now().isoformat(),'stocks':built,'top_picks':top,
       'mode':'historical_reconstruction' if historical else 'live','demo':False,'qwen_used':qwen.used,'qwen_cache_hits':qwen.cached,
       'coverage':{'completed':len(built),'requested':len(metas),'failed':failures},
       'limitations':['歷史重建使用現存核心名單，存在存續偏誤','新聞只分析實際取得的標題／使用者節錄','法人與可比估值缺資料時保留缺值，不偽裝全市場完整健檢'],
       'note':'規則研究訊號，不是機率或交易指令。'}
    errs=validate_snapshot(payload)
    if errs:raise ValueError('; '.join(errs))
    row=store(payload)
    for s in built:
        p=ROOT/'data/market'/f"{s['symbol'].replace('.','_')}.json";old=read_json(p,{}) or {}
        if as_of>=old.get('as_of',''):
            merged={r['date']:r for r in old.get('candles',[])};merged.update({r['date']:r for r in s['candles']})
            write_json(p,{'symbol':s['symbol'],'as_of':as_of,'candles':[merged[d] for d in sorted(merged)]})
    print('Snapshot saved',row['path']);return payload
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--as-of',default=now().date().isoformat());args=p.parse_args();run(args.as_of)
