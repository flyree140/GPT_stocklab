"""Non-destructive v16 -> v16.1 re-analysis. Old reports retain their bytes.
A re-analysis is explicitly retrospective, never backdated as an original signal.
Unsupported v14/v15 schemas are retained and listed, not guessed into trading data.
"""
from __future__ import annotations
import argparse,copy,hashlib
from .common import ROOT,read_json,now,write_json
from .storage import store,validate_snapshot
from .events import analyze
from .decision import decide

def upgrade(snapshot):
    if not isinstance(snapshot,dict) or not snapshot.get('stocks'):raise ValueError('no stocks')
    if not all('candles' in s and ('decision' in s or 'facts' in s) for s in snapshot['stocks']):
        raise ValueError('unsupported historical schema; keep original')
    p=copy.deepcopy(snapshot);p.update(version='16.1.2',mode='retrospective_reanalysis',generated_at=now().isoformat(),
       retrospective_notice='以16.1規則事後重算，非當年預先登記預測；原檔保留。')
    for s in p['stocks']:
        events=[]
        for e in s.get('news',[]):
            try:
                original={k:e[k] for k in ['id','title','excerpt','url','source_url','publisher','source','published_at','available_at','fetched_at','copies','evidence_level','official_document','verified_document'] if k in e}
                events.append(analyze(original,s,p['as_of']+'T23:59:59+08:00'))
            except (ValueError,KeyError):continue
        s['news']=events;s['decision']=decide(s,p['as_of'])
    p['top_picks']=[s['symbol'] for s in sorted(p['stocks'],key=lambda s:s['decision']['score'],reverse=True) if s['decision']['code'] in ['conditional_buy','watch'] and s['decision']['score']>=50][:5]
    errors=validate_snapshot(p)
    if errors:raise ValueError('; '.join(errors))
    return p

def run(root=ROOT):
    manifest=read_json(root/'data/manifest.json',{}) or {};log=[]
    # List copied before writes; store only appends new run files.
    for row in list(manifest.get('snapshots',[])):
        p=root/row.get('path','');raw=read_json(p,{}) or {}
        if str(raw.get('version','')).startswith('16.1'):continue
        before=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        try:
            result=store(upgrade(raw),root);log.append({'source':row['path'],'result':result['path'],'status':'recomputed'})
        except (ValueError,KeyError,TypeError) as exc:log.append({'source':row.get('path'),'status':'preserved_unconverted','error':str(exc)})
        if before and hashlib.sha256(p.read_bytes()).hexdigest()!=before:raise AssertionError('Original changed')
    write_json(root/'data/system/migration-report.json',{'generated_at':now().isoformat(),'rows':log})
    return log
if __name__=='__main__':print(run())
