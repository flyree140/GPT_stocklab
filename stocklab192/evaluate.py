"""Compare base vs adapter on identical held-out inputs. This is not a PnL test."""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
from collections import Counter
from .schema import load_jsonl,save_jsonl,check_record,check_gold,prompt_messages,digest,verify_adapter,timestamp

def macro_f1(truth,pred):
    labels=sorted(set(truth))
    if not labels:return None
    vals=[]
    for label in labels:
        tp=sum(a==b==label for a,b in zip(truth,pred))
        fp=sum(a!=label and b==label for a,b in zip(truth,pred));fn=sum(a==label and b!=label for a,b in zip(truth,pred))
        vals.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    return sum(vals)/len(vals)

def metric_tuples(out):
    rows=out.get('metrics',[]) if isinstance(out,dict) else []
    def freeze(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
    return {tuple(freeze(m.get(k)) for k in ('name','value','unit','period')) for m in rows if isinstance(m,dict)}

def score_predictions(records,predictions):
    index={p['id']:p for p in predictions};truths={k:[] for k in ('category','relation','reported_status','fundamental_direction')};preds={k:[] for k in truths}
    valid=grounded=metric_exact=longer=0;counts=Counter()
    for r in records:
        raw=index.get(r['id'],{});g=r['gold'];o=raw.get('output');errs=check_gold(o,r)
        valid+=int(not errs);counts['items']+=1
        if isinstance(o,dict):
            es=o.get('evidence',[]);docs={d['id']:d['text'] for d in r['documents']}
            ok=isinstance(es,list) and bool(es) and all(isinstance(e,dict) and isinstance(e.get('quote'),str) and len(e['quote'])>=3 and isinstance(e.get('doc_id'),str) and e.get('doc_id') in docs and e['quote'] in docs[e['doc_id']] for e in es)
            grounded+=int(ok);metric_exact+=int(metric_tuples(o)==metric_tuples(g))
            longer+=int(o.get('longer_horizon',{}).get('eligible_for_review')==g['longer_horizon']['eligible_for_review']) if isinstance(o.get('longer_horizon'),dict) else 0
        for k in truths:
            truths[k].append(g[k]);preds[k].append(o.get(k,'INVALID') if isinstance(o,dict) else 'INVALID')
    n=len(records)
    return {'n':n,'schema_and_constraints_pass_rate':valid/n if n else None,
            'verbatim_evidence_pass_rate':grounded/n if n else None,
            'metric_set_exact_match':metric_exact/n if n else None,'longer_review_flag_accuracy':longer/n if n else None,
            'macro_f1':{k:macro_f1(truths[k],preds[k]) for k in truths},
            'human_review_still_required':['mechanism truth/causal strength','financial metric unit/period','overconfident unsupported assertions'],
            'profitability_validated':False}

def compare(adapter,data,out,limit=8,confirm_final_test=False):
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    from contextlib import nullcontext
    from .schema import MODEL_ID,MODEL_REVISION,SCHEMA_VERSION,prompt_hash
    info=verify_adapter(adapter,MODEL_ID,MODEL_REVISION)
    if info.get('schema')!=SCHEMA_VERSION or info.get('prompt_sha256')!=prompt_hash():raise ValueError('adapter schema/prompt mismatch')
    if not 1<=limit<=32:raise ValueError('評估上限32筆')
    if 'test' in Path(data).stem and not confirm_final_test:raise ValueError('這是最終測試集；先使用validation。僅最後一次加--final-test')
    raw=load_jsonl(data)
    if len({r['id'] for r in raw})!=len(raw):raise ValueError('duplicate IDs')
    blocked=set(info.get('train_event_groups',[]))
    if confirm_final_test:blocked|=set(info.get('validation_event_groups',[]))
    if blocked & {r['event_cluster'] for r in raw}:raise ValueError('evaluation event leakage')
    rows=raw[:limit]
    for r in rows:
        if check_record(r,True):raise ValueError(str(check_record(r,True)))
        if digest([d['text'] for d in r['documents']]) in info.get('train_text_hashes',[]):raise ValueError('same training text with changed ID')
    if not rows:raise ValueError('empty eval')
    if not torch.cuda.is_available():raise ValueError('Colab A/B請使用GPU；網頁端CPU推論由GitHub處理')
    out=Path(out)
    if (out/'comparison.json').exists():raise ValueError('不覆寫比較結果；若要重做請另建資料夾並記錄原因')
    out.mkdir(parents=True,exist_ok=True)
    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(MODEL_ID,revision=MODEL_REVISION,trust_remote_code=False,
      torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,device_map={'':0})
    model=PeftModel.from_pretrained(model,adapter,is_trainable=False);model.eval();model.config.use_cache=True
    from .tokenization import encode_record
    logs={'base':[],'adapter':[]};start=time.monotonic();complete=True
    for r in rows:
        if time.monotonic()-start>600:complete=False;break
        prompt=tok.apply_chat_template(prompt_messages(r),tokenize=False,add_generation_prompt=True,enable_thinking=False)
        inp=tok(prompt,return_tensors='pt',add_special_tokens=False).to(model.device)
        if inp.input_ids.shape[1]>2048:raise ValueError('eval input exceeds budget; no silent truncation')
        for variant in ('base','adapter'):
            with (model.disable_adapter() if variant=='base' else nullcontext()):
                with torch.inference_mode():tokens=model.generate(**inp,max_new_tokens=768,max_time=40,do_sample=False,pad_token_id=tok.eos_token_id)
            raw_text=tok.decode(tokens[0][inp.input_ids.shape[1]:],skip_special_tokens=True).strip()
            try:obj=json.loads(raw_text)
            except json.JSONDecodeError:obj=None
            logs[variant].append({'id':r['id'],'output':obj,'raw':raw_text,'validation_errors':check_gold(obj,r)})
            save_jsonl(out/(variant+'.jsonl'),logs[variant])
    paired_ids={x['id'] for x in logs['base']} & {x['id'] for x in logs['adapter']}
    paired=[r for r in rows if r['id'] in paired_ids]
    result={v:score_predictions(paired,log) for v,log in logs.items()}
    result.update(n_requested=len(rows),n_paired=len(paired),scope='final_test' if confirm_final_test else 'validation_subset',
       complete=complete and len(paired)==len(rows),subset_ids=[r['id'] for r in paired],dataset_sha256=digest(raw),
       adapter_sha256=info['adapter_sha256'],profitability_validated=False,
       caution='這是抽取能力小樣本A/B，不是金融績效、沒有因果或獲利證明。重看validation可調整，test不可反覆挑模型。')
    (out/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--adapter',required=True);p.add_argument('--data',required=True);p.add_argument('--out',required=True)
    p.add_argument('--limit',type=int,default=8);p.add_argument('--final-test',action='store_true');a=p.parse_args()
    compare(a.adapter,a.data,a.out,a.limit,a.final_test)
