"""Shared, persistent per-Taipei-day and per-workflow-run generation budget.
Counters reserve attempts before worker launch; partial/failed loads do not reset quota.
No paid API. Public runner eligibility is an account setting, not a property of this code.
"""
from __future__ import annotations
import os,json,tempfile,fcntl
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

def limits():
    def val(key,default,ceiling):
        try:n=int(os.getenv(key,str(default)))
        except ValueError:raise ValueError(key+' must be an integer')
        return max(0,min(n,ceiling))
    return {'day':val('QWEN_DAILY_LIMIT',12,24),'run':val('QWEN_RUN_LIMIT',6,12),
            'seconds':val('QWEN_BATCH_SECONDS',720,1200)}
def today():return datetime.now(ZoneInfo('Asia/Taipei')).date().isoformat()
def run_id():
    return str(os.getenv('GITHUB_RUN_ID') or os.getenv('STOCKLAB_RUN_KEY') or ('local-'+str(os.getpid())))
def load(p,default):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except FileNotFoundError:return default
@contextmanager
def locked(root):
    p=Path(root)/'.cache/qwen-shared.lock';p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=p.parent,delete=False) as f:
        json.dump(obj,f,ensure_ascii=False,allow_nan=False);tmp=Path(f.name)
    tmp.replace(p)
def reserve(root,keys,day=None,run_key=None,limit_override=None):
    day=day or today();rid=run_key or run_id();lim=limits();p=Path(root)/'data/system/qwen-state.json'
    if limit_override is not None:lim['day']=min(lim['day'],max(0,int(limit_override)))
    with locked(root):
        s=load(p,{}) or {};s.setdefault('cache',{})
        if s.get('day')!=day:s.update(day=day,attempts=0,runs={},attempted_run_keys={})
        s.setdefault('runs',{});s.setdefault('attempted_run_keys',{})
        unique=list(dict.fromkeys(keys));cached={k:s['cache'][k] for k in unique if s['cache'].get(k) is not None}
        left=min(max(0,lim['day']-int(s.get('attempts',0))),max(0,lim['run']-int(s['runs'].get(rid,0))))
        # Cache values are successes only. An invalid legacy None value is not evidence.
        attempted=set(s['attempted_run_keys'].get(rid,[]))
        chosen=[k for k in unique if k not in cached and k not in attempted][:left]
        s['attempted_run_keys'][rid]=list(dict.fromkeys([*attempted,*chosen]))
        s['attempts']=int(s.get('attempts',0))+len(chosen);s['runs'][rid]=int(s['runs'].get(rid,0))+len(chosen)
        s['budget_policy']='19.3-shared-day-run';write(p,s)
    return chosen,cached,{'day':day,'daily_limit':lim['day'],'per_run_limit':lim['run'],
        'attempts_today':s['attempts'],'attempts_in_workflow':s['runs'][rid],'reserved_now':len(chosen)}
def save_results(root,values):
    p=Path(root)/'data/system/qwen-state.json'
    with locked(root):
        s=load(p,{}) or {};s.setdefault('cache',{})
        s['cache'].update({k:v for k,v in values.items() if v is not None})
        s['cache']=dict(list(s['cache'].items())[-1000:]);write(p,s)


def fair_round_robin(queues, at=None):
    """Rotate ticker priority by Taipei day and morning/evening, never by outcomes."""
    at=at or datetime.now(ZoneInfo('Asia/Taipei'))
    if not queues:return [],0
    slot=at.date().toordinal()*2+(1 if at.hour>=12 else 0)
    offset=(slot*max(1,limits()['run']))%len(queues)
    rotated=queues[offset:]+queues[:offset]
    return [q[i] for i in range(max((len(q) for q in rotated),default=0)) for q in rotated if i<len(q)],offset
