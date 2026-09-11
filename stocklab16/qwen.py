"""Bounded local optional inference. No paid endpoints. All attempts count.
Cache keys include model revision and schema. Quota persists in data/system.
Worker is killed on timeout; disabled/old-date modes never start a worker.
"""
from __future__ import annotations
import json,os,hashlib,subprocess,sys,tempfile,time
from pathlib import Path
from .common import ROOT,now,read_json,write_json

class QwenHints:
    def __init__(self,limit=6,root=ROOT):
        self.root=Path(root);self.limit=max(0,min(6,int(os.getenv('QWEN_DAILY_LIMIT',limit))))
        self.used=0;self.cached=0;self.start=time.monotonic();self.failed=False
        self.enabled=os.getenv('ENABLE_QWEN','1')=='1'
        self.day=now().date().isoformat();self.path=self.root/'data/system/qwen-state.json'
        self.state=read_json(self.path,{}) or {};self.state.setdefault('cache',{})
        if self.state.get('day')!=self.day:self.state.update(day=self.day,attempts=0)
    def save(self):write_json(self.path,self.state)
    def hint(self,title,excerpt=''):
        if not self.enabled:return None
        text=(str(title)+'\n'+str(excerpt)[:700]).strip()
        revision=os.getenv('QWEN_REVISION','c1899de289a04d12100db370d81485cdf75e47ca')
        key=hashlib.sha256(('16.1.2|'+revision+'|'+text).encode()).hexdigest()
        if key in self.state['cache']:
            self.cached+=1;return self.state['cache'][key]
        if self.failed or self.state['attempts']>=self.limit or time.monotonic()-self.start>=720:return None
        self.state['attempts']+=1;self.used+=1;self.save()
        temp=self.root/'.cache/qwen-jobs';temp.mkdir(parents=True,exist_ok=True)
        inp=temp/(key+'.input.json');out=temp/(key+'.output.json')
        write_json(inp,{'text':text,'revision':revision})
        try:
            p=subprocess.run([sys.executable,'-m','stocklab16.qwen_worker',str(inp),str(out)],cwd=self.root,timeout=min(120,max(1,720-(time.monotonic()-self.start))),capture_output=True,text=True)
            if p.returncode:raise RuntimeError(p.stderr[-300:])
            obj=read_json(out);from .events import validate_hint
            if not validate_hint(obj,[{'text':text}]):obj=None
        except (subprocess.TimeoutExpired,RuntimeError,ValueError) as exc:
            print('Qwen fallback:',str(exc)[:180]);obj=None;self.failed=True
        finally:
            inp.unlink(missing_ok=True);out.unlink(missing_ok=True)
        self.state['cache'][key]=obj
        # Bound serialized cache to latest 1000 entries.
        self.state['cache']=dict(list(self.state['cache'].items())[-1000:]);self.save()
        return obj
