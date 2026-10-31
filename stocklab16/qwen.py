"""One local Qwen load per generation batch. Rules still analyze every fetched event."""
from __future__ import annotations
import hashlib,os,subprocess,sys,tempfile,time
from pathlib import Path
from .common import ROOT,read_json,write_json,now
from stocklab193.budget import reserve,save_results,limits,run_id

class QwenHints:
    def __init__(self,limit=None,root=ROOT):
        self.root=Path(root);self.enabled=os.getenv('ENABLE_QWEN','1')=='1';self.failed=False
        self.used=0;self.cached=0;self.limit=limit;self.path=self.root/'data/system/qwen-state.json'
        self.day=now().date().isoformat();self.start=time.monotonic();self.stats={};self.model_load_batches=0
    def _entry(self,item):
        text=(str(item.get('title',''))+'\n'+str(item.get('excerpt',''))[:700]).strip()
        rev=os.getenv('QWEN_REVISION','c1899de289a04d12100db370d81485cdf75e47ca')
        key=hashlib.sha256(('19.3-classifier|'+rev+'|'+text).encode()).hexdigest()
        return key,{'key':key,'text':text,'revision':rev}
    def batch(self,items):
        if not self.enabled or self.failed:return [None]*len(items)
        entries=[self._entry(x) for x in items];bykey=dict(entries)
        chosen,cached,self.stats=reserve(self.root,bykey,self.day,limit_override=self.limit)
        self.used+=len(chosen);self.cached+=len(cached);outcomes=dict(cached)
        if chosen:
            self.model_load_batches+=1
            work=self.root/'.cache/qwen-jobs';work.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=work) as td:
                inp=Path(td)/'input.json';out=Path(td)/'output.json'
                write_json(inp,{'requests':[bykey[k] for k in chosen],'wall_seconds':limits()['seconds'],
                    'revision':bykey[chosen[0]]['revision']})
                try:
                    proc=subprocess.run([sys.executable,'-m','stocklab16.qwen_worker',str(inp),str(out)],cwd=self.root,
                        timeout=max(1,limits()['seconds']),capture_output=True,text=True)
                    if proc.returncode:raise RuntimeError(proc.stderr[-300:])
                except (subprocess.TimeoutExpired,RuntimeError) as exc:
                    print('Qwen partial/fallback:',str(exc)[:160]);self.failed=True
                from .events import validate_hint
                payload=read_json(out,{}) or {}
                # Keep successful incremental output after timeout; never claim reserved=completed.
                for k in chosen:
                    obj=payload.get(k)
                    if validate_hint(obj,[{'text':bykey[k]['text']}]):outcomes[k]=obj
                save_results(self.root,{k:outcomes.get(k) for k in chosen})
        self.stats.update(model_load_batches=self.model_load_batches,validated_results=len(outcomes),cache_hits=self.cached)
        return [outcomes.get(k) for k,_ in entries]
    def hint(self,title,excerpt=''):
        return self.batch([{'title':title,'excerpt':excerpt}])[0]
