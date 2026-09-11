"""Child process; outer parent bounds model loading and generation wall time."""
import sys,json,re,os
from pathlib import Path

def main():
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    torch.set_num_threads(2)
    payload=json.loads(Path(sys.argv[1]).read_text());model_id='Qwen/Qwen3-0.6B'
    tokenizer=AutoTokenizer.from_pretrained(model_id,revision=payload['revision'],trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(model_id,revision=payload['revision'],device_map='cpu',low_cpu_mem_usage=True,trust_remote_code=False)
    model.eval()
    prompt='只根據提供證據分類，不補寫事實。只輸出JSON，category必須為profile,promotion,governance,monthly_revenue,analyst_forecast,reported_earnings,company_guidance,margin_change,capital,dividend,disruption,orders,partnership,macro,unclear之一。evidence為證據的逐字短片段。證據：'+payload['text']
    text=tokenizer.apply_chat_template([{'role':'user','content':prompt}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    inp=tokenizer(text,return_tensors='pt')
    with torch.inference_mode():
        output=model.generate(**inp,max_new_tokens=256,max_time=90,do_sample=False,pad_token_id=tokenizer.eos_token_id)
    ans=tokenizer.decode(output[0][inp.input_ids.shape[1]:],skip_special_tokens=True)
    match=re.search(r'\{[^{}]*\}',ans,re.S)
    obj=json.loads(match.group(0)) if match else None
    Path(sys.argv[2]).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
if __name__=='__main__':main()
