"""Reproducible archive-only advice audit. No network and no LLM.

Outputs explicitly separate original observations from hypothetical entry returns.
Stock/day rows are NOT independent trades or a compounded portfolio.
"""
from __future__ import annotations
import argparse,bisect,csv,hashlib,json,statistics,collections,math
from pathlib import Path
from datetime import datetime
from .calendar import TZ,clock,parse_time,covered,is_session,expected_close,SEED
from .hygiene import clean_bars

HORIZONS=(1,5,10,20)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def avg(xs):return statistics.mean(xs) if xs else None
def quantile(xs,q):
    if not xs:return None
    a=sorted(xs);f=(len(a)-1)*q;i=int(f);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(f-i)
def stats(rows,h):
    rr=[r for r in rows if r.get(f'h{h}',{}).get('status')=='mature'];vals=[r[f'h{h}'] for r in rr]
    def m(k):return avg([v[k] for v in vals if v.get(k) is not None])
    return {'n':len(rr),'entry_dates':len({r['entry_date'] for r in rr}),'symbols':len({r['symbol'] for r in rr}),
     'mean_gross':m('gross'),'mean_net':m('net'),'median_net':quantile([v['net'] for v in vals],.5),
     'p10_net':quantile([v['net'] for v in vals],.1),'p90_net':quantile([v['net'] for v in vals],.9),
     'win_rate_net':100*sum(v['net']>0 for v in vals)/len(vals) if vals else None,
     'mean_excess_gross':m('excess'),'mean_excess_net':m('excess_net'),'mean_mae':m('mae'),
     'best_net':max([v['net'] for v in vals],default=None),'worst_net':min([v['net'] for v in vals],default=None)}
def rank_values(xs):
    order=sorted(range(len(xs)),key=lambda i:xs[i]);r=[0.]*len(xs);i=0
    while i<len(xs):
        j=i+1
        while j<len(xs) and xs[order[j]]==xs[order[i]]:j+=1
        for k in range(i,j):r[order[k]]=(i+j-1)/2
        i=j
    return r
def correlation(x,y):
    if len(x)<3:return None
    a=statistics.mean(x);b=statistics.mean(y);den=math.sqrt(sum((v-a)**2 for v in x)*sum((v-b)**2 for v in y))
    return sum((v-a)*(w-b) for v,w in zip(x,y))/den if den else None

def outcome(r,market,sessions,h,bench):
    entry=r['entry_date'];i=bisect.bisect_left(sessions,entry);days=sessions[i:i+h]
    if len(days)<h:return {'status':'pending'}
    index=market.get(r['symbol'],{});bars=[index.get(day) for day in days]
    if any(b is None for b in bars):return {'status':'missing_price'}
    if any(b.get('corporate_action') for b in bars):return {'status':'corporate_action'}
    if any(b['high']==b['low'] for b in bars):return {'status':'untradable_flat_bar'}
    if any(not bench.get(d) for d in days):return {'status':'missing_benchmark'}
    if any(bench[d].get('corporate_action') for d in days):return {'status':'benchmark_corporate_action'}
    op=bars[0]['open'];cl=bars[-1]['close'];fee=.001425;slip=.001;tax=.001 if r['etf'] else .003
    net=(cl*(1-slip)*(1-fee-tax)/(op*(1+slip)*(1+fee))-1)*100
    bo=bench[days[0]]['open'];bc=bench[days[-1]]['close'];bn=(bc*(1-slip)*(1-fee-.001)/(bo*(1+slip)*(1+fee))-1)*100
    gross=(cl/op-1)*100;bg=(bc/bo-1)*100
    return {'status':'mature','entry_open':op,'exit_date':days[-1],'exit_close':cl,'gross':gross,'net':net,
     'benchmark_gross':bg,'benchmark_net':bn,'excess':gross-bg,'excess_net':net-bn,
     'mae':(min(b['low'] for b in bars)/op-1)*100,'mfe':(max(b['high'] for b in bars)/op-1)*100}

def run(root,out):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    market={};quarantine=[];market_hashes={}
    for p in sorted((root/'data/market').glob('*.json')):
        d=read(p);sy=d.get('symbol',p.stem.replace('_','.'));bars,issues=clean_bars(d.get('candles',[]))
        market[sy]={b['date']:b for b in bars};market_hashes[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
        for issue in issues:quarantine.append({'symbol':sy,'path':str(p.relative_to(root)),**issue})
    bench=market.get('0050.TW',{});sessions=sorted(bench)
    if not sessions:raise ValueError('No benchmark sessions: cannot align trades without inventing dates')
    manifest=read(root/'data/manifest.json');hasherrors=[];manifestpaths=set()
    for r in manifest.get('snapshots',[]):
        for row in [r]+r.get('runs',[]):
            path=row.get('path');manifestpaths.add(path)
            if not path or not (root/path).is_file():hasherrors.append({'path':path,'reason':'missing'});continue
            if row.get('sha256') and hashlib.sha256((root/path).read_bytes()).hexdigest()!=row['sha256']:hasherrors.append({'path':path,'reason':'hash_mismatch'})
    raw=[];inventory=[];excluded=[];eventcounts=collections.Counter();uniqueevents={};snap_hashes={};anomaly_snapshots=set();factorcounts=collections.Counter();versions=collections.Counter()
    for p in sorted((root/'data/snapshots').rglob('*.json')):
        path=str(p.relative_to(root));d=read(p);snap_hashes[path]=hashlib.sha256(p.read_bytes()).hexdigest()
        entry={'path':path,'as_of':d.get('as_of'),'generated_at':d.get('generated_at'),'version':d.get('version'),'demo':d.get('demo',False),'mode':d.get('mode'),'stock_count':len(d.get('stocks',[]))}
        inventory.append(entry)
        if path not in manifestpaths:excluded.append({**entry,'reason':'orphan_not_indexed'});continue
        if d.get('demo') or d.get('mode') in ('historical_reconstruction','reanalysis','recomputed') or d.get('reanalysis') or d.get('derived_from'):
            excluded.append({**entry,'reason':'demo_or_posthoc'});continue
        if any(e['path']==path for e in hasherrors):excluded.append({**entry,'reason':'integrity_failure'});continue
        if not d.get('generated_at'):excluded.append({**entry,'reason':'no_generation_timestamp'});continue
        at=parse_time(d['generated_at']);versions[str(d.get('version'))]+=1
        for s in d.get('stocks',[]):
            sy=s.get('symbol');ds=s.get('decision',{});bars=s.get('candles',[]);last=bars[-1] if bars else {};issues=[]
            if not last:issues.append('no_snapshot_price')
            elif not is_session(last['date']):issues.append('snapshot_last_price_non_trading_day');anomaly_snapshots.add(path)
            elif clock(last['date'],13,30)>at:issues.append('not_closed_when_generated')
            for e in s.get('news',[]):
                eventcounts['article_stock_observations']+=1
                eventcounts['title_only']+=e.get('source_assessment',{}).get('coverage')=='僅標題'
                eventcounts['verified']+=bool(e.get('source_assessment',{}).get('verified'))
                eventcounts['included']+=bool(e.get('included'))
                eventcounts['qwen_assisted']+='Qwen' in str(e.get('analysis_engine',e.get('engine',e.get('analyzer',''))))
                ek=(sy,e.get('id') or e.get('url') or e.get('title'));uniqueevents[ek]=e
                for k in ('published_at','available_at'):
                    try:
                        if parse_time(e[k])>at:issues.append('future_news')
                    except (ValueError,KeyError,TypeError):pass
            factors={f['key']:f.get('score') for f in ds.get('factors',[])}
            for k,v in factors.items():factorcounts[k+('_missing' if v is None else '_present')]+=1
            eligible=[day for day in sessions if day>last.get('date','') and clock(day)>at]
            entry_day=eligible[0] if eligible else None
            if entry_day is not None and not covered(entry_day):issues.append('calendar_outside_verified_audit_window')
            row={'symbol':sy,'name':s.get('name',sy),'sector':s.get('sector',''),'as_of':d['as_of'],'generated_at':d['generated_at'],'version':str(d.get('version')),
             'source_path':path,'source_sha256':snap_hashes[path],'entry_date':entry_day,'quote_date':last.get('date'),'quote':last.get('close'),
             'original_code':ds.get('code'),'original_label':ds.get('label'),'score':ds.get('score'),'coverage':ds.get('coverage'),
             'top_pick':sy in d.get('top_picks',[]),'factors':factors,'news_n':len(s.get('news',[])),
             'news_verified':sum(bool(e.get('source_assessment',{}).get('verified')) for e in s.get('news',[])),
             'new_investor':ds.get('new_investor'),'next_action':ds.get('next_action'),'invalidation':ds.get('invalidation'),
             'stop':ds.get('plan',{}).get('stop_reference'),'resistance':ds.get('plan',{}).get('resistance'),
             'original_plan':ds.get('plan',{}),'etf':sy.startswith('00'),'issues':list(set(issues))}
            raw.append(row)
    # Preserve last available advice BEFORE the same executable open; all earlier runs remain in raw CSV.
    selected={};pending={}
    for r in sorted(raw,key=lambda x:parse_time(x['generated_at'])):
        if r['entry_date']:selected[(r['entry_date'],r['symbol'])]=r
        else:pending[r['symbol']]=r
    rows=sorted(selected.values(),key=lambda x:(x['entry_date'],x['symbol']))
    for r in rows:
        for h in HORIZONS:r[f'h{h}']={'status':'invalid_signal'} if r['issues'] else outcome(r,market,sessions,h,bench)
    groups={
      'all':rows,'non_etf':[r for r in rows if not r['etf']], 'top5':[r for r in rows if r['top_pick']],
      'watch':[r for r in rows if r['original_code']=='watch'], 'neutral':[r for r in rows if r['original_code']=='neutral'],
      'avoid':[r for r in rows if r['original_code']=='avoid'], 'insufficient':[r for r in rows if r['original_code']=='insufficient'],
      'conditional_buy':[r for r in rows if r['original_code']=='conditional_buy']}
    for version in sorted(versions):groups['version_'+version]=[r for r in rows if r['version']==version and not r['etf']]
    for low,high in [(0,40),(40,50),(50,60),(60,101)]:groups[f'score_{low}_{high}']=[r for r in rows if low<=(r['score']or 0)<high and not r['etf']]
    summary={k:{str(h):stats(v,h) for h in HORIZONS} for k,v in groups.items()}
    daily=[]
    for day in sorted({r['entry_date'] for r in rows}):
        rs=[r for r in rows if r['entry_date']==day];item={'entry_date':day}
        for h in HORIZONS:
            valid=[r for r in rs if not r['etf'] and r[f'h{h}']['status']=='mature']
            xs=[r['score'] for r in valid];ys=[r[f'h{h}']['excess'] for r in valid]
            item[f'rank_ic_{h}']=correlation(rank_values(xs),rank_values(ys)) if len(valid)>=5 else None
            for k,sub in [('top5',[r for r in rs if r['top_pick']]),('all_non_etf',[r for r in rs if not r['etf']])]:item[f'{k}_h{h}']=stats(sub,h)
        daily.append(item)
    splits={};boundary='2026-10-01'
    for h in HORIZONS:
        # Purge early samples whose outcome crosses the time boundary. No parameter fitting.
        early=[r for r in rows if r['entry_date']<boundary and r[f'h{h}'].get('exit_date','9999')<boundary]
        late=[r for r in rows if r['entry_date']>=boundary]
        splits[str(h)]={'early':stats([r for r in early if r['top_pick']],h),'late':stats([r for r in late if r['top_pick']],h),
                       'purged_cross_boundary':sum(r['entry_date']<boundary and r[f'h{h}'].get('exit_date','')>=boundary for r in rows)}
    symbols=[]
    for sy in sorted(market):
        rr=[r for r in rows if r['symbol']==sy]
        symbols.append({'symbol':sy,'name':rr[0]['name'] if rr else sy,'top_count':sum(r['top_pick'] for r in rr),
           'original_buy_count':sum(r['original_code']=='conditional_buy' for r in rr),
           'label_counts':dict(collections.Counter(r['original_code'] for r in rr)),
           'all':{str(h):stats(rr,h) for h in HORIZONS},'top5':{str(h):stats([r for r in rr if r['top_pick']],h) for h in HORIZONS}})
    aggregate={'version':'17.0.0','source':'user-uploaded GPT_stocklab-main.zip; not independent exchange reconciliation',
      'analysis_date':datetime.now(TZ).isoformat(),'as_of':max(r['as_of'] for r in raw),'market_last_date':max(sessions),
      'start':min(r['as_of'] for r in raw),'end':max(r['as_of'] for r in raw),'snapshot_files':len(inventory),
      'eligible_snapshot_files':len(versions) and sum(versions.values()),'calendar_dates':len({r['as_of'] for r in raw}),
      'raw_stock_observations':len(raw),'decision_sessions':len({r['entry_date'] for r in rows}),'dedup_stock_sessions':len(rows),
      'pending_stocks':len(pending),'versions':dict(versions),'raw_labels':dict(collections.Counter(r['original_code'] for r in raw)),
      'dedup_labels':dict(collections.Counter(r['original_code'] for r in rows)),'quarantined_market_bars':len(quarantine),
      'quarantine_by_reason':dict(collections.Counter(r['reason'] for r in quarantine)),
      'snapshots_with_invalid_last_price':len(anomaly_snapshots),'integrity_errors':hasherrors,'excluded':excluded,
      'events':dict(eventcounts),'unique_stock_events':len(uniqueevents),'factor_availability':dict(factorcounts),
      'outcomes_status':{str(h):dict(collections.Counter(r[f'h{h}']['status'] for r in rows)) for h in HORIZONS},
      'summary':summary,'daily':daily,'by_symbol':symbols,'split_boundary':boundary,'purged_time_splits':splits,
      'rank_ic':{str(h):avg([d[f'rank_ic_{h}'] for d in daily if d[f'rank_ic_{h}'] is not None]) for h in HORIZONS},
      'assumptions':{'commission_per_side':.001425,'slippage_per_side':.001,'stock_sell_tax':.003,'equity_etf_sell_tax':.001,
        'entry':'latest recorded snapshot strictly before next available valid 09:00 regular-lot open; not 09:10 odd-lot execution',
        'exit':'Hth valid common trading session close, entry counts as day 1','benchmark':'0050 same entry/exit price dates',
        'corporate_actions':'exclude affected holding windows; data only supplies flags, not full entitlements',
        'no_portfolio':'overlapping hypothetical observations; no compounded return or portfolio drawdown is claimed',
        'cost_scope':'rate-based event study; excludes minimum fees; interactive tickets include adjustable minimum fees',
        'split_warning':'retrospective time partition, not untouched prospective out-of-sample performance'},
      'publication_warning':'generated_at and SHA256 are archive assertions, not proof of an external pre-trade publication timestamp'}
    write(out/'audit.json',{**aggregate,'records':rows,'pending':list(pending.values())})
    write(out/'source_manifest.json',{'snapshots':snap_hashes,'market':market_hashes,'original_archive_required':True})
    write(out/'quarantine.json',quarantine)
    write(out/'inventory.json',inventory)
    def csv_write(filename,data,fields):
        with (out/filename).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
            for r in data:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items() if k in fields})
    fields=['symbol','name','as_of','generated_at','source_path','source_sha256','version','quote_date','quote','entry_date','original_code','original_label','score','top_pick','news_n','news_verified','coverage','new_investor','next_action','invalidation','issues']
    csv_write('01_original_all_runs.csv',raw,fields)
    flat=[]
    for r in rows:
        for h in HORIZONS:flat.append({**r,'horizon':h,**r[f'h{h}']})
    csv_write('02_daily_advice_vs_outcome.csv',flat,fields+['horizon','status','entry_open','exit_date','exit_close','gross','net','benchmark_gross','excess','excess_net','mae','mfe'])
    csv_write('03_group_summary.csv',[{'group':g,'horizon':h,**v} for g,hh in summary.items() for h,v in hh.items()],['group','horizon']+list(stats([],1)))
    csv_write('04_quarantined_prices.csv',quarantine,['symbol','path','date','reason','bar'])
    csv_write('05_unresolved_latest_signals.csv',list(pending.values()),fields)
    return aggregate

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--out');a=p.parse_args()
    out=a.out or str(Path(a.root)/'data/evaluation');r=run(a.root,out)
    print(json.dumps({k:r[k] for k in ('start','end','eligible_snapshot_files','dedup_stock_sessions','decision_sessions','market_last_date','raw_labels','quarantined_market_bars','outcomes_status')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
