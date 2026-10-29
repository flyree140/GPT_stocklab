"""One CPU model load for <=6 events, killed by parent after 720s."""
from pathlib import Path
import json,sys,time
from .schema import MODEL_ID,MODEL_REVISION,prompt_messages,check_gold
from .deployment import download_adapter

def main():
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    p=json.loads(Path(sys.argv[1]).read_text());rows=p['requests']
    if not 0<len(rows)<=6:raise ValueError('max 6 requests per worker')
    local=download_adapter(p['repo'],p['revision'],Path('.cache/adapter192')/p['revision'])
    torch.set_num_threads(2)
    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(MODEL_ID,revision=MODEL_REVISION,device_map='cpu',torch_dtype=torch.float32,trust_remote_code=False)
    model=PeftModel.from_pretrained(model,local,is_trainable=False);model.eval()
    output={};start=time.monotonic()
    for r in rows:
        if time.monotonic()-start>540:break
        text=tok.apply_chat_template(prompt_messages(r),tokenize=False,add_generation_prompt=True,enable_thinking=False)
        inp=tok(text,return_tensors='pt',add_special_tokens=False)
        if inp.input_ids.shape[1]>2048:output[r['cache_key']]=None;continue
        with torch.inference_mode():gen=model.generate(**inp,max_new_tokens=768,max_time=75,do_sample=False,pad_token_id=tok.eos_token_id)
        raw=tok.decode(gen[0][inp.input_ids.shape[1]:],skip_special_tokens=True).strip()
        try:obj=json.loads(raw)
        except json.JSONDecodeError:obj=None
        output[r['cache_key']]=obj if not check_gold(obj,r) else None
        Path(sys.argv[2]).write_text(json.dumps(output,ensure_ascii=False))
    Path(sys.argv[2]).write_text(json.dumps(output,ensure_ascii=False))
if __name__=='__main__':main()
