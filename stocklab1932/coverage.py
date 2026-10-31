"""Bounded core+rotation coverage. 'Catalogued' never means 'analyzed'."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re,os

def select(core,favorites,catalog,limit=20,rotating=8,at=None):
 limit=max(1,min(30,int(limit)));rotating=max(0,min(int(rotating),limit));at=at or datetime.now(ZoneInfo('Asia/Taipei'))
 if at.tzinfo is None:raise ValueError('explicit timezone required')
 # two slots/day, ordered rotation (no use of future outcomes).
 local=at.astimezone(ZoneInfo('Asia/Taipei'));slot=local.date().toordinal()*2+(1 if local.hour>=13 else 0)
 seen=set();selected=[];reasons={}
 def add(rows,n,why):
  count=0
  for r in rows:
   sy=r.get('symbol','')
   if sy in seen or not re.fullmatch(r'(?:\d{4}|00\d{2,4})\.(?:TW|TWO)',sy):continue
   if count>=n or len(selected)>=limit:break
   selected.append(r);seen.add(sy);reasons[sy]=why;count+=1
  return count
 add(favorites,limit,'favorite_priority')
 add(core,max(0,limit-rotating-len(selected)),'core_priority')
 pool=sorted([r for r in catalog+core if r.get('symbol') not in seen],key=lambda r:r.get('symbol',''))
 pool=list({r.get('symbol'):r for r in pool}.values())
 offset=(slot*max(1,rotating))%len(pool) if pool else 0
 add(pool[offset:]+pool[:offset],limit-len(selected),'rotating_catalog')
 add(core,limit-len(selected),'core_fallback')
 return selected,{'catalog_count':len({r.get('symbol') for r in catalog if r.get('symbol')}),'requested_limit':limit,'rotating_slots':rotating,'slot':slot,'offset':offset,'selection':reasons,'unselected_not_analyzed':True,'note':'股票名錄≠當日分析；輪巡擴充覆蓋，不保證每天全市場完整分析。'}
