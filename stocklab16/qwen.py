from __future__ import annotations
import json, os, re, hashlib
from pathlib import Path
from .common import ROOT

ALLOWED={'profile','promotion','governance','earnings','capital','dividend','disruption','orders','partnership','macro','unclear'}
class QwenHints:
    def __init__(self,limit=6):
        self.limit=int(os.getenv('QWEN_DAILY_LIMIT',limit)); self.used=0; self.model=None; self.tok=None
        self.cache_path=ROOT/'data'/'qwen_cache.json'; self.cache={}
        if self.cache_path.exists():
            try:self.cache=json.loads(self.cache_path.read_text(encoding='utf-8'))
            except Exception:self.cache={}
    def save(self):
        self.cache_path.parent.mkdir(parents=True,exist_ok=True); self.cache_path.write_text(json.dumps(self.cache,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def _load(self):
        if self.model is not None:return True
        if os.getenv('ENABLE_QWEN','1')!='1':return False
        try:
            from transformers import AutoTokenizer,AutoModelForCausalLM
            self.tok=AutoTokenizer.from_pretrained('Qwen/Qwen3-0.6B'); self.model=AutoModelForCausalLM.from_pretrained('Qwen/Qwen3-0.6B',device_map='cpu',low_cpu_mem_usage=True); return True
        except Exception as exc:
            print('Qwen unavailable',exc); return False
    def hint(self,title,excerpt=''):
        text=(title+'\n'+excerpt[:700]).strip(); key=hashlib.sha256(text.encode()).hexdigest()
        if key in self.cache:return self.cache[key]
        if self.used>=self.limit or not self._load():return None
        self.used+=1
        prompt='''你是財經新聞分類器。只使用下面證據，不補寫未知事實。\n允許 category: profile,promotion,governance,earnings,capital,dividend,disruption,orders,partnership,macro,unclear。\n只輸出 JSON：{"category":"...","evidence":"從證據逐字複製的短片段"}\n證據：'''+text
        try:
            msgs=[{'role':'user','content':prompt}]; templ=self.tok.apply_chat_template(msgs,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            inputs=self.tok([templ],return_tensors='pt'); out=self.model.generate(**inputs,max_new_tokens=96,do_sample=False,pad_token_id=self.tok.eos_token_id)
            ans=self.tok.decode(out[0][inputs.input_ids.shape[1]:],skip_special_tokens=True); m=re.search(r'\{.*?\}',ans,re.S); obj=json.loads(m.group(0)) if m else None
            if obj and obj.get('category') in ALLOWED and obj.get('evidence') in text:self.cache[key]=obj; self.save(); return obj
        except Exception as exc: print('Qwen hint failed',exc)
        self.cache[key]=None; self.save(); return None
