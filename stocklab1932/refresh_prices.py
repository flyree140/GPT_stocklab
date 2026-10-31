"""Bounded CPU price refresh for EVERY previously registered symbol, rotating backlog.
It does not retrieve news/LLMs, rewrite original forecasts, or fabricate missing bars.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os,json,time
from stocklab16.market import history
from stocklab17.hygiene import clean_bars
from .developer import read
from .collection import write

def run(root,fetcher=history):
 root=Path(root);now=datetime.now(ZoneInfo('Asia/Taipei'));day=now.date().isoformat();wanted={'0050.TW'}
 for p in (root/'data/developer1932/signals').glob('*.json'):
  r=read(p,{})
  if not r.get('demo'):wanted.update(x['symbol'] for x in r.get('rows',[]))
 latest=read(root/'data/latest.json',{}) or {}
 wanted.update(s['symbol'] for s in latest.get('stocks',[]) if not latest.get('demo'))
 existing={};needed=[]
 for symbol in sorted(wanted):
  p=root/'data/market'/f"{symbol.replace('.','_')}.json";old=read(p,{}) or {};existing[symbol]=old
  # Latest deep pass already fetched this symbol: do not duplicate work.
  if old.get('as_of','')>=day:continue
  last=(old.get('candles') or [{}])[-1].get('date','')
  needed.append((last,symbol))
 cap=max(0,min(80,int(os.getenv('PRICE_REFRESH_LIMIT','40'))));selected=sorted(needed)[:cap];ok=[];failed=[]
 for _,symbol in selected:
  try:
   rows=fetcher(symbol,day,180)
   if not rows:raise ValueError('source returned no usable rows')
   merged={b['date']:b for b in existing[symbol].get('candles',[])};merged.update({b['date']:b for b in rows})
   clean,bad=clean_bars(list(merged.values()),cutoff=now.isoformat())
   if not clean:raise ValueError('all rows rejected')
   write(root/'data/market'/f"{symbol.replace('.','_')}.json",{'symbol':symbol,'as_of':day,'candles':clean,'refreshed_at':now.isoformat(),'price_only_no_llm':True})
   if bad:write(root/'data/quarantine'/f"{symbol.replace('.','_')}.json",bad)
   ok.append(symbol)
  except Exception as e:failed.append({'symbol':symbol,'reason':str(e)})
  time.sleep(.2)
 report={'at':now.isoformat(),'tracked_symbols':len(wanted),'limit':cap,'attempted':len(selected),'updated':ok,'failed':failed,'queued':len(needed)-len(selected),'no_fake_forward_fill':True}
 write(root/'data/developer1932/price_refresh.json',report);return report
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');a=p.parse_args();print(json.dumps(run(a.root),ensure_ascii=False))
