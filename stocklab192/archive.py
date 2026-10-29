"""CPU-only import of uploaded repository ZIP into a PRIVATE review queue.
Does not trust old model outputs as gold, does not unzip user paths, no data upload.
"""
from pathlib import Path
import zipfile,json,hashlib
from .schema import digest,save_jsonl,timestamp

def import_archive(path,out,max_snapshots=400,max_bytes=80_000_000):
    records={};excluded=0;read=0;n=0
    with zipfile.ZipFile(path) as z:
        for info in sorted(z.infolist(),key=lambda x:x.filename):
            name=info.filename
            if '/data/snapshots/' not in name or not name.endswith('.json') or '/demo/' in name:continue
            n+=1
            if n>max_snapshots:break
            if info.file_size>8_000_000 or read+info.file_size>max_bytes:continue
            read+=info.file_size
            try:p=json.loads(z.read(info))
            except (ValueError,UnicodeError):continue
            if p.get('demo') or p.get('mode')=='demo':continue
            cutoff=p.get('generated_at')
            try:timestamp(cutoff)
            except (ValueError,TypeError):continue
            for s in p.get('stocks',[]):
                for e in s.get('news',[]):
                    text=(str(e.get('title',''))+'\n'+str(e.get('excerpt',''))).strip()
                    try:
                        published=e['published_at'];available=e.get('available_at',published)
                        if max(timestamp(published),timestamp(available))>timestamp(cutoff):raise ValueError('future')
                    except (KeyError,ValueError,TypeError):excluded+=1;continue
                    key=digest({'symbol':s.get('symbol'),'text':text})
                    if key in records:continue
                    records[key]={'id':key[:24],'decision_at':cutoff,'event_cluster':'REVIEW_'+key[:16],
                      'issuer':{'symbol':s.get('symbol'),'name':s.get('name'),'sector':s.get('sector')},
                      'documents':[{'id':'d1','text':text,'published_at':published,'available_at':available,
                       'source_kind':'archived_headline','language':'zh','training_allowed':False,'source_url':e.get('source_url') or e.get('url')}],
                      'review':{'approved':False,'reviewer':'','cluster_verified':False},'gold':None,'synthetic':False,
                      'provenance':{'archive_path':name,'old_score_not_used':True}}
    save_jsonl(out,list(records.values()))
    return {'candidate_records':len(records),'excluded_time_inconsistent':excluded,'snapshots_scanned':n,
      'training_ready':0,'note':'請核對來源授權、相同事件分組、時間、公司與答案；舊分數沒有當作標籤。'}
