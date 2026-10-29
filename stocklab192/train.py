"""GPU-only, bounded LoRA/QLoRA. No paid endpoints or automatic retries."""
from __future__ import annotations
import argparse,json,time,sys,subprocess,math
from pathlib import Path
from .schema import (load_jsonl,check_record,digest,timestamp,MODEL_ID,MODEL_REVISION,SCHEMA_VERSION,prompt_hash)

def budget_for(profile):
    if profile=='smoke':return dict(max_records=24,max_steps=6,grad_accum=2,wall_minutes=10,max_total_tokens=80000,eval_cap=4)
    if profile=='reviewed':return dict(max_records=1000,max_steps=200,grad_accum=8,wall_minutes=30,max_total_tokens=1800000,eval_cap=24)
    raise ValueError('profile must be smoke or reviewed')

def validate_parts(parts,allow_synthetic=False):
    if not all(parts.get(k) for k in ('train','validation','test')):raise ValueError('train / validation / test 不可為空')
    groups={k:{r.get('event_cluster') for r in v} for k,v in parts.items()}
    for a,b in [('train','validation'),('train','test'),('validation','test')]:
        if groups[a]&groups[b]:raise ValueError('同一事件跨資料集；重新分組')
        if max(timestamp(r['decision_at']) for r in parts[a])>=min(timestamp(r['decision_at']) for r in parts[b]):raise ValueError('時間順序重疊')
    for rows in parts.values():
        for row in rows:
            errors=check_record(row,True)
            if row.get('synthetic') and not allow_synthetic:errors.append('正式訓練排除合成教材')
            if errors:raise ValueError(str(row.get('id'))+': '+'; '.join(errors))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',required=True);p.add_argument('--out',required=True)
    p.add_argument('--profile',choices=['smoke','reviewed'],default='smoke')
    p.add_argument('--qlora',action='store_true');p.add_argument('--resume',action='store_true')
    p.add_argument('--max-length',type=int,default=2048)
    a=p.parse_args();budget=budget_for(a.profile)
    if not 512<=a.max_length<=2048:raise ValueError('免費起步版本限制長度512–2048')
    parts={k:load_jsonl(Path(a.data)/(k+'.jsonl')) for k in ('train','validation','test')}
    validate_parts(parts,a.profile=='smoke')
    # No automatic truncation or silent sampling. Select a reviewed pilot in preparation.
    if len(parts['train'])>budget['max_records']:raise ValueError('超過本輪樣本預算；先在CPU選定試驗集，不直接全量訓練')
    import torch
    if not torch.cuda.is_available():raise SystemExit('無GPU：請在Colab切換GPU；先前CPU準備檔須存Drive。不自動購買或換帳號重試。')
    from transformers import AutoTokenizer,AutoModelForCausalLM,TrainingArguments,Trainer,TrainerCallback,BitsAndBytesConfig,set_seed
    from transformers.trainer_utils import get_last_checkpoint
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    from .tokenization import encode_record,ResponseCollator
    set_seed(42);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    fingerprint={'dataset':{k:digest(rows) for k,rows in parts.items()},'model':MODEL_ID,'revision':MODEL_REVISION,
      'schema':SCHEMA_VERSION,'prompt_sha256':prompt_hash(),'profile':a.profile,'budget':budget,
      'max_length':a.max_length,'rank':8,'target_modules':['q_proj','v_proj'],'lr':1e-4,'qlora':a.qlora,'seed':42}
    manifest_path=out/'run_manifest.json'
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text())
        if not a.resume:raise ValueError('這個RUN_NAME已存在；明確續訓或換新名稱，不覆寫')
        if old.get('fingerprint')!=fingerprint:raise ValueError('續訓的資料／參數／版本不同，請開新RUN_NAME')
    elif a.resume:raise ValueError('沒有原始run_manifest，不能續訓')
    start=time.monotonic();tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION,trust_remote_code=False)
    tok.padding_side='right';tok.pad_token=tok.eos_token if tok.pad_token_id is None else tok.pad_token
    encoded={};overlong={}
    for name in ('train','validation'):
        pairs=[(r['id'],encode_record(tok,r,a.max_length)) for r in parts[name]]
        encoded[name]=[v for _,v in pairs if v is not None];overlong[name]=[i for i,v in pairs if v is None]
    (out/'token_audit.json').write_text(json.dumps({'overlong':overlong,'counts':{k:len(v) for k,v in encoded.items()}},ensure_ascii=False,indent=2))
    if any(overlong.values()):raise ValueError('部分樣本超長，已寫token_audit。請縮短無關來源，不裁掉答案／證據，不空燒GPU。')
    total_tokens=sum(len(x['input_ids']) for x in encoded['train'])
    if total_tokens>budget['max_total_tokens']:raise ValueError('超過本輪總token預算')
    # Smoke is pipeline-only; reviewed runs are capped at one pass, never a hidden hyperparameter sweep.
    steps=min(budget['max_steps'],max(1,math.ceil(len(encoded['train'])/budget['grad_accum'])))
    if a.profile=='smoke':steps=budget['max_steps']
    val=encoded['validation'][:budget['eval_cap']]
    manifest={'fingerprint':fingerprint,'model':MODEL_ID,'revision':MODEL_REVISION,'schema':SCHEMA_VERSION,
      'prompt_sha256':prompt_hash(),'synthetic_smoke_only':a.profile=='smoke','shadow_only':True,
      'profitability_validated':False,'training_finished':False,'training_data_sha256':fingerprint['dataset'],
      'train_event_groups':sorted({r['event_cluster'] for r in parts['train']}),
      'validation_event_groups':sorted({r['event_cluster'] for r in parts['validation']}),
      'train_text_hashes':sorted({digest([d['text'] for d in r['documents']]) for r in parts['train']}),
      'counts':{k:len(v) for k,v in parts.items()},'total_train_tokens':total_tokens,'planned_update_steps':steps,
      'gpu':torch.cuda.get_device_name(0),'gpu_memory_gib':torch.cuda.get_device_properties(0).total_memory/2**30,
      'torch':torch.__version__,'run_status':'loading','process_limit_minutes':budget['wall_minutes']}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (out/'environment.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    kwargs={'revision':MODEL_REVISION,'trust_remote_code':False,'device_map':{'':0},'torch_dtype':dtype,'attn_implementation':'sdpa'}
    if a.qlora:kwargs['quantization_config']=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype)
    model=AutoModelForCausalLM.from_pretrained(MODEL_ID,**kwargs)
    if a.qlora:model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    model.config.use_cache=False
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=.05,target_modules=['q_proj','v_proj'],bias='none',task_type='CAUSAL_LM'))
    model.enable_input_require_grads()
    for v in model.parameters():
        if v.requires_grad:v.data=v.data.float()
    model.print_trainable_parameters();train_start=time.monotonic();timings=[]
    class Budget(TrainerCallback):
        def on_step_end(self,args,state,control,**kwargs):
            elapsed=time.monotonic()-start;timings.append((state.global_step,time.monotonic()-train_start))
            if state.global_step in (1,5):
                print(json.dumps({'step':state.global_step,'training_elapsed':timings[-1][1],'peak_gpu_gib':torch.cuda.max_memory_allocated()/2**30}))
            if elapsed>=budget['wall_minutes']*60:control.should_save=True;control.should_training_stop=True
            return control
    args=TrainingArguments(output_dir=str(out/'checkpoints'),max_steps=steps,num_train_epochs=1,
      per_device_train_batch_size=1,per_device_eval_batch_size=1,gradient_accumulation_steps=budget['grad_accum'],
      gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False},
      learning_rate=1e-4,warmup_ratio=.05,lr_scheduler_type='cosine',optim='adamw_torch',max_grad_norm=1.0,
      fp16=dtype==torch.float16,bf16=dtype==torch.bfloat16,eval_strategy='no',save_strategy='steps',save_steps=25,
      logging_steps=1 if a.profile=='smoke' else 5,save_total_limit=2,report_to='none',seed=42,data_seed=42,
      dataloader_num_workers=0,remove_unused_columns=False)
    trainer=Trainer(model=model,args=args,train_dataset=encoded['train'],eval_dataset=val,
      data_collator=ResponseCollator(tok.pad_token_id),processing_class=tok,callbacks=[Budget()])
    ckpt=get_last_checkpoint(str(out/'checkpoints')) if a.resume and (out/'checkpoints').exists() else None
    if a.resume and not ckpt:raise ValueError('沒有可續訓checkpoint')
    try:
        trainer.train(resume_from_checkpoint=ckpt)
        adapter=out/'adapter';trainer.save_model(str(adapter));tok.save_pretrained(adapter)
        manifest.update(training_finished=True,run_status='completed',completed_steps=trainer.state.global_step,
          elapsed_seconds=time.monotonic()-start,peak_gpu_gib=torch.cuda.max_memory_allocated()/2**30,
          stopped_at_budget=trainer.state.global_step<steps,validation_loss=None,validation_loss_note='省額度；生成式A/B另行執行，不以loss當投資準確率')
        import hashlib
        manifest['adapter_sha256']=hashlib.sha256((adapter/'adapter_model.safetensors').read_bytes()).hexdigest()
        (adapter/'stocklab_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print('已保存adapter。下一步執行A/B；沒有自動部署、沒有獲利保證。')
    except torch.OutOfMemoryError:
        manifest.update(run_status='oom_no_auto_retry',training_finished=False)
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));raise

if __name__=='__main__':main()
