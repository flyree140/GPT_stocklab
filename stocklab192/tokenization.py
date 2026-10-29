"""Completion-only labels; do not silently truncate targets into invalid JSON."""
from __future__ import annotations
import json
from .schema import prompt_messages

def encode_record(tokenizer,record,max_length):
    text=tokenizer.apply_chat_template(prompt_messages(record),tokenize=False,add_generation_prompt=True,enable_thinking=False)
    prefix=tokenizer(text,add_special_tokens=False)['input_ids']
    answer=json.dumps(record['gold'],ensure_ascii=False,separators=(',',':'))
    suffix=tokenizer(answer+tokenizer.eos_token,add_special_tokens=False)['input_ids']
    if not suffix:raise ValueError('empty target')
    if len(prefix)+len(suffix)>max_length:
        return None # Explicitly counted/rejected in trainer. Keep evidence/answer complete.
    return {'input_ids':prefix+suffix,'attention_mask':[1]*(len(prefix)+len(suffix)),
            'labels':[-100]*len(prefix)+suffix}

class ResponseCollator:
    def __init__(self,pad_id):self.pad_id=pad_id
    def __call__(self,rows):
        import torch
        width=max(len(r['input_ids']) for r in rows)
        return {key:torch.tensor([r[key]+[pad]*(width-len(r[key])) for r in rows],dtype=torch.long)
                for key,pad in [('input_ids',self.pad_id),('attention_mask',0),('labels',-100)]}
