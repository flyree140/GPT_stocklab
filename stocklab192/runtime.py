"""Six-factor sidecar + bounded own-adapter shadow inference.
Does not overwrite research snapshots or place real/simulated orders.
Shared data/system/qwen-state.json budget, with all attempts counted before worker.
"""
from __future__ import annotations
import os,json,time,tempfile,subprocess,sys,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import contextmanager
from .schema import digest,check_record,check_gold,MODEL_REVISION,SCHEMA_VERSION,prompt_hash,timestamp
from .features import six_factors
from .social import summarize


def read(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:return default

def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);tmp=Path(f.name)
    tmp.replace(path)

@contextmanager
def lock(path):
    import fcntl
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)


def reserve(root,keys,day,limit=6):
    path=Path(root)/'data/system/qwen-state.json';lockp=Path(root)/'.cache/qwen192.lock'
    with lock(lockp):
        state=read(path,{}) or {};state.setdefault('cache',{})
        if state.get('day')!=day:state.update(day=day,attempts=0)
        cached={k:state['cache'][k] for k in keys if k in state['cache']}
        remaining=max(0,min(6,int(limit))-int(state.get('attempts',0)))
        selected=[k for k in keys if k not in cached][:remaining]
        state['attempts']=int(state.get('attempts',0))+len(selected);atomic(path,state)
    return selected,cached


def cache_results(root,values):
    path=Path(root)/'data/system/qwen-state.json'
    with lock(Path(root)/'.cache/qwen192.lock'):
        state=read(path,{}) or {};state.setdefault('cache',{});state['cache'].update(values)
        state['cache']=dict(list(state['cache'].items())[-1000:]);atomic(path,state)


def make_record(stock,event,cutoff):
    text=(str(event.get('title',''))+'\n'+str(event.get('excerpt',''))[:900]).strip()
    if not text:return None
    record={'id':digest({'symbol':stock['symbol'],'text':text})[:24],'decision_at':cutoff,
      'issuer':{k:stock.get(k) for k in ('symbol','name','sector')},'documents':[{'id':'d1','text':text,
      'published_at':event.get('published_at'),'available_at':event.get('available_at',event.get('published_at')),
      'source_kind':event.get('source_assessment',{}).get('kind','headline'),'language':'mixed'}]}
    return None if check_record(record) else record


def run(root,allow_model=None):
    root=Path(root);snap=read(root/'data/latest.json')
    demo=False
    if not snap:snap=read(root/'data/demo/latest.json');demo=True
    if not snap:raise ValueError('缺少最新快照；先執行原每日流程')
    cutoff=snap.get('generated_at');timestamp(cutoff)
    day=datetime.now(ZoneInfo('Asia/Taipei')).date().isoformat()
    if timestamp(cutoff)>datetime.now(ZoneInfo('Asia/Taipei')):raise ValueError('拒絕未來快照')
    asof=snap.get('as_of');stocks=snap.get('stocks',[])
    if not stocks:raise ValueError('快照沒有股票')
    demo=demo or bool(snap.get('demo'))
    own=os.getenv('STOCKLAB_192_ENABLED','0')=='1' if allow_model is None else allow_model
    own=own and not demo and asof==day and os.getenv('SKIP_ADAPTER192','0')!='1'
    # Only explicit as-of facts are accepted; current_info with no release date is NOT backfilled.
    extra=read(root/f'.cache/features192/{asof}.json',{}) or {}
    outputs=[];requests=[]
    for stock in stocks[:30]:
        meta=extra.get(stock['symbol'],{})
        social=summarize(meta.get('social_posts',[]),cutoff,source_ok=meta.get('social_source_ok',False),
           baseline=meta.get('social_baseline',[]),collection_key=meta.get('collection_key','unset'))
        outputs.append({'symbol':stock['symbol'],'name':stock.get('name'),
            'factors':six_factors(stock,cutoff,social_summary=social,extra_facts=meta.get('facts',[])),'analyses':[]})
    # Round-robin prevents first ticker using the entire daily budget.
    for i in range(8):
        for stock in stocks[:30]:
            news=stock.get('news',[])
            if i>=len(news):continue
            event=news[i]
            if event.get('category') in ('profile','promotion','price_commentary'):continue
            rec=make_record(stock,event,cutoff)
            if rec:requests.append(rec)
    repo=os.getenv('STOCKLAB_ADAPTER_REPO','');revision=os.getenv('STOCKLAB_ADAPTER_REVISION','')
    model_status={'enabled_requested':own,'adapter_repo':repo,'adapter_revision':revision,'mode':'shadow_only',
       'daily_max_attempts':6,'attempts_this_run':0,'cache_hits':0,'note':'此面板不改寫既有分數、試買或成交帳'}
    results={}
    if own:
        if not repo or len(revision)!=40:raise ValueError('啟用自有模型前需填HF repo與40位commit SHA')
        keyed={digest({'schema':SCHEMA_VERSION,'prompt':prompt_hash(),'base':MODEL_REVISION,'adapter':revision,
          'repo':repo,'issuer':r['issuer'],'documents':r['documents']}):r for r in requests}
        chosen,cached=reserve(root,list(keyed),day)
        model_status.update(attempts_this_run=len(chosen),cache_hits=len(cached))
        results.update({keyed[k]['id']:v for k,v in cached.items() if v})
        if chosen:
            work=root/'.cache/adapter192-jobs';work.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=work) as td:
                inp=Path(td)/'input.json';out=Path(td)/'output.json'
                atomic(inp,{'repo':repo,'revision':revision,'requests':[{**keyed[k],'cache_key':k} for k in chosen]})
                vals={k:None for k in chosen}
                try:
                    proc=subprocess.run([sys.executable,'-m','stocklab192.worker',str(inp),str(out)],cwd=root,
                        timeout=720,capture_output=True,text=True)
                    if proc.returncode:raise RuntimeError('worker_failed')
                    payload=read(out,{}) or {}
                    for k,v in payload.items():
                        if k in vals and not check_gold(v,keyed[k]):vals[k]=v;results[keyed[k]['id']]=v
                    model_status['result']='completed_with_validation'
                except (subprocess.TimeoutExpired,RuntimeError,ValueError):
                    model_status['result']='timeout_or_model_failed; use existing rules, no auto retry'
                finally:cache_results(root,vals)
    else:model_status['result']='disabled_or_demo_or_historical; CPU factors only'
    index={s['symbol']:s for s in outputs}
    for r in requests:
        if r['id'] in results:index[r['issuer']['symbol']]['analyses'].append({'id':r['id'],'output':results[r['id']],
           'model_revision':revision,'automatically_changes_position':False})
    summary={'version':'19.2.0','as_of':asof,'cutoff':cutoff,'created_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
      'source_snapshot_sha256':digest(snap),'demo':demo,'model_status':model_status,'stocks':outputs,
      'limits':['社群只代表採樣範圍；公開不等於可訓練。','日期有效不等於來源數字已獨立認證。','未經前瞻驗證，不把adapter信心當預期報酬。']}
    dest=root/'data/research192';atomic(dest/(digest(summary)+'.json'),summary);atomic(dest/'latest.json',summary)
    print(json.dumps({'ok':True,'path':str(dest/'latest.json'),'stocks':len(outputs),'model':model_status},ensure_ascii=False));return summary

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');a=p.parse_args();run(a.root)
