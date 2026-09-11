"""Immutable run files; existing user snapshots are never overwritten by upgrades."""
from __future__ import annotations
import hashlib,re
from pathlib import Path
from .common import ROOT,now,read_json,write_json

def settings_file(name,root=ROOT):
    p=root/'config'/f'{name}.json'
    return p if p.is_file() else root/'config'/f'{name}.default.json'

def store(payload,root=ROOT):
    root=Path(root);day=payload['as_of'];stamp=now().strftime('%Y%m%dT%H%M%S%f')
    manifest=read_json(root/'data/manifest.json',{}) or {};rows=manifest.get('snapshots',[])
    previous=next((r for r in rows if r.get('date')==day),None)
    count=int((previous or {}).get('run_count',0))+1
    payload={**payload,'run_count':count};rel=f'data/snapshots/{day}/run-{stamp}.json';p=root/rel
    if p.exists():raise FileExistsError(p)
    write_json(p,payload);sha=hashlib.sha256(p.read_bytes()).hexdigest()
    runs=list((previous or {}).get('runs',[]))
    if previous and previous.get('path') and not any(r.get('path')==previous['path'] for r in runs):
        runs.append({k:v for k,v in previous.items() if k!='runs'})
    row={'date':day,'path':rel,'sha256':sha,'stock_count':len(payload.get('stocks',[])),
         'generated_at':payload['generated_at'],'run_count':count,'mode':payload.get('mode','live')}
    runs.append(dict(row));row['runs']=runs
    rows=[r for r in rows if r.get('date')!=day]+[row];rows.sort(key=lambda r:r['date'],reverse=True)
    write_json(root/'data/manifest.json',{'version':'16.1.2','latest':rows[0]['date'],'snapshots':rows})
    latest=read_json(root/'data/latest.json',{}) or {}
    if day>=latest.get('as_of',''):write_json(root/'data/latest.json',payload)
    return row

def validate_snapshot(payload):
    errors=[];day=payload.get('as_of','')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):return ['invalid as_of']
    for stock in payload.get('stocks',[]):
        dates=[]
        for r in stock.get('candles',[]):
            d=r.get('date','');dates.append(d)
            if d>day:errors.append(f"{stock.get('symbol')}: future candle {d}")
        if dates!=sorted(set(dates)):errors.append('candles not unique/sorted')
        for e in stock.get('news',[]):
            from .common import dt
            for k in ['published_at','available_at']:
                if e.get(k):
                    try:
                        from .common import TZ
                        if dt(e[k]).astimezone(TZ).date().isoformat()>day:errors.append(f'future news {k}')
                    except Exception:errors.append(f'invalid news {k}')
    def walk(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in {'actual_return','future_return','is_correct','realized_pnl','answer'}:errors.append('forbidden outcome '+k)
                walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(payload)
    return errors
