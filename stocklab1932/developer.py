"""Register EVERY analyzed symbol and evaluate outcomes, even abstentions.
Passive equal-budget probes are not original advice, causal attribution or a portfolio.
"""
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from statistics import mean,median
import json,hashlib,math
from stocklab17.calendar import parse_time,clock,is_session,covered
from stocklab17.hygiene import clean_bars
from stocklab192.schema import digest
from .collection import write
TZ=ZoneInfo('Asia/Taipei');HORIZONS=(1,5,10,20)
def read(p,default=None):
 try:return json.loads(Path(p).read_text())
 except (OSError,ValueError):return default

def sessions(at,cal,count):
 t=parse_time(at);d=t.date();out=[]
 for _ in range(180):
  day=d.isoformat()
  if not covered(day,cal):raise ValueError('calendar_pending:'+day)
  if is_session(day,cal) and clock(day)>t:out.append(day)
  if len(out)>=count:return out
  d+=timedelta(days=1)
 raise ValueError('insufficient_calendar')

def register(snapshot,source_path,source_bytes,root,registered_at):
 cutoff=snapshot['generated_at'];parse_time(cutoff)
 if parse_time(cutoff)>parse_time(registered_at):raise ValueError('future snapshot')
 sha=hashlib.sha256(source_bytes).hexdigest();rows=[]
 side=read(Path(root)/'data/research192/latest.json',{}) or {}
 if side.get('source_file_sha256')!=sha or side.get('cutoff')!=cutoff:side={}
 shadow={r['symbol']:r for r in side.get('stocks',[])}
 for stock in snapshot.get('stocks',[]):
  d=stock.get('decision',{});row={'symbol':stock['symbol'],'name':stock.get('name'),
   'original_label':d.get('label'),'original_code':d.get('code'),'score':d.get('score'),
   'top_pick':stock['symbol'] in snapshot.get('top_picks',[]),'factors':d.get('factors',[]),
   'model_at_signal':{'snapshot_version':snapshot.get('version'),'base_qwen_used':snapshot.get('qwen_used'),'adapter_shadow':side.get('model_status'),'valid_adapter_analyses':len(shadow.get(stock['symbol'],{}).get('analyses',[])),'adapter_changes_original_score':False},
   'news_ids':[e.get('id') for e in stock.get('news',[])],'news_categories':sorted({str(e.get('category','unclear')) for e in stock.get('news',[])}),
   'news_count':len(stock.get('news',[])),'quote_date':(stock.get('candles') or [{}])[-1].get('date'),
   'etf':stock.get('sector')=='ETF' or stock.get('type')=='etf','reasons':d.get('reasons',[]),'risks':d.get('risks',[])}
  rows.append(row)
 obj={'schema':'developer1932-1','source_path':source_path,'source_sha256':sha,'generated_at':cutoff,'registered_at':registered_at,'as_of':snapshot['as_of'],'mode':snapshot.get('mode'),'demo':bool(snapshot.get('demo')),'rows':rows}
 dest=Path(root)/'data/developer1932/signals'/f'{sha}.json'
 if not dest.exists():write(dest,obj)
 return read(dest)

def probe(row,days,market,budget,cutoff):
 # Full required calendar sequence: never skip an absent bar to invent a T+1 fill.
 if clock(days[-1],13,30)>parse_time(cutoff):return {'status':'pending','needed_until':days[-1]}
 index=market.get(row['symbol'],{});bars=[]
 for d in days:
  b=index.get(d)
  if b is None:return {'status':'missing_price','date':d}
  if b.get('corporate_action'):return {'status':'corporate_action','date':d}
  if b['high']==b['low']:return {'status':'uncertain_flat_bar','date':d}
  bars.append(b)
 fee=.001425;minimum=20;slip=.001;tax=.001 if row['etf'] else .003
 ep=round(bars[0]['open']*(1+slip),2);xp=round(bars[-1]['close']*(1-slip),2)
 qty=math.floor((budget-minimum)/ep)
 while qty>0 and qty*ep+max(minimum,qty*ep*fee)>budget:qty-=1
 if qty<1:return {'status':'budget_insufficient'}
 if qty>math.floor(bars[0]['volume']*.01):return {'status':'liquidity_cap'}
 cost=round(qty*ep+max(minimum,qty*ep*fee),2);gross=round(qty*xp,2);proceeds=round(gross-max(minimum,gross*fee)-gross*tax,2);pnl=round(proceeds-cost,2)
 return {'status':'mature','entry_date':days[0],'exit_date':days[-1],'shares':qty,'entry_proxy':ep,'exit_proxy':xp,'buy_cost':cost,'proceeds':proceeds,'pnl':pnl,
  'return_on_cost_pct':round(pnl/cost*100,5),'return_on_budget_pct':round(pnl/budget*100,5),'mfe_pct':round((max(b['high'] for b in bars)/ep-1)*100,5),'mae_pct':round((min(b['low'] for b in bars)/ep-1)*100,5),
  'not_actual_fill':True,'rule':'T+1 open proxy with slip; fixed horizon close; no intraday stops in passive probe'}

def evaluate(records,market,cal,cutoff,budget=100000):
 selected={};pending=[]
 for rec in records:
  if rec.get('demo') or parse_time(rec['generated_at'])>parse_time(cutoff):continue
  try:entry=sessions(rec['generated_at'],cal,1)[0]
  except ValueError as e:pending.append({'source_sha256':rec['source_sha256'],'status':str(e)});continue
  for row in rec['rows']:
   key=(entry,row['symbol']);candidate={**row,'entry_date':entry,'source_sha256':rec['source_sha256'],'generated_at':rec['generated_at'],'registered_at':rec['registered_at'],
     'sample_mode':'prospective_registered' if parse_time(rec['registered_at'])<clock(entry) and rec.get('mode')=='live' else 'retrospective_reference'}
   if key not in selected or parse_time(candidate['generated_at'])>parse_time(selected[key]['generated_at']):selected[key]=candidate
 result=[]
 for row in sorted(selected.values(),key=lambda r:(r['entry_date'],r['symbol'])):
  outcomes={}
  for h in HORIZONS:
   try:
    days=sessions(row['generated_at'],cal,h)
    r=probe(row,days,market,budget,cutoff)
    if r.get('status')=='mature':
     bench=probe({'symbol':'0050.TW','etf':True},days,market,budget,cutoff)
     r['benchmark_status']=bench['status'];r['excess_budget_pct']=round(r['return_on_budget_pct']-bench['return_on_budget_pct'],5) if bench['status']=='mature' else None
    outcomes[str(h)]=r
   except ValueError as e:outcomes[str(h)]={'status':'calendar_pending','message':str(e)}
  result.append({**row,'outcomes':outcomes})
 summaries={}
 for mode in ('prospective_registered','retrospective_reference'):
  summaries[mode]={}
  for h in HORIZONS:
   rs=[r for r in result if r['sample_mode']==mode and r['outcomes'][str(h)].get('status')=='mature'];vals=[r['outcomes'][str(h)] for r in rs]
   summaries[mode][str(h)]={'n':len(rs),'unique_entry_dates':len({r['entry_date'] for r in rs}),'symbols':len({r['symbol'] for r in rs}),
    'mean_net_return_on_budget_pct':mean([v['return_on_budget_pct'] for v in vals]) if vals else None,'median_net_return_on_cost_pct':median([v['return_on_cost_pct'] for v in vals]) if vals else None,
    'profitable_probe_fraction':sum(v['pnl']>0 for v in vals)/len(vals) if vals else None,'not_forecast_accuracy':True}
 return {'cutoff':cutoff,'budget_per_symbol':budget,'rows':result,'summary':summaries,'unavailable_entries':pending,
   'method':'每檔等額獨立T+1日K探針；含未買入／觀望／避開，不是原建議交易或真實投組',
   'warning':'同事件、同市場日期與重疊期間相依；不把所有觀察當獨立樣本，不把獲利比例當LLM準確率；不得年化短期樣本'}

def run(root,include_archive=False,cutoff=None):
 root=Path(root);now=cutoff or datetime.now(TZ).isoformat();cal=read(root/'data/calendar/latest.json') or read(root/'config/market-calendar.json') or read(root/'assets/paper-calendar.json')
 paths=['data/latest.json'];expected={}
 if include_archive:
  manifest=read(root/'data/manifest.json',{}) or {};paths=[]
  for e in manifest.get('snapshots',[]):
   for r in [e]+e.get('runs',[]):
    if r.get('path'):
     paths.append(r['path'])
     if r.get('sha256'):expected[r['path']]=r['sha256']
 for rel in sorted(set(paths)):
  p=(root/rel).resolve()
  if not p.is_relative_to(root.resolve()) or not p.is_file():continue
  if rel in expected and hashlib.sha256(p.read_bytes()).hexdigest()!=expected[rel]:raise ValueError('manifest source hash mismatch: '+rel)
  snap=read(p,{})
  if not snap or snap.get('demo') or snap.get('mode') in ('historical_reconstruction','reanalysis','recomputed') or snap.get('derived_from'):continue
  register(snap,rel,p.read_bytes(),root,now)
 records=[read(p) for p in (root/'data/developer1932/signals').glob('*.json')];records=[r for r in records if r]
 market={}
 for p in (root/'data/market').glob('*.json'):
  obj=read(p,{}) or {};bars,_=clean_bars(obj.get('candles',[]),cutoff=now);market[obj.get('symbol',p.stem.replace('_','.'))]={b['date']:b for b in bars}
 result=evaluate(records,market,cal,now)
 dest=root/'data/developer1932';write(dest/'outcomes.json',result)
 write(dest/'index.json',{'version':'19.3.2','updated_at':now,'registered_runs':len(records),'source_latest_sha256':hashlib.sha256((root/'data/latest.json').read_bytes()).hexdigest() if (root/'data/latest.json').exists() else None,'all_signals_registered':True,'outcomes_path':'data/developer1932/outcomes.json','history_not_same_as_personal_account':True})
 return result
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--include-archive',action='store_true');a=p.parse_args();r=run(a.root,a.include_archive);print(json.dumps({'registered_studies':len(r['rows']),'summary':r['summary']},ensure_ascii=False))
