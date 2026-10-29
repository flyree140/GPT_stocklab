"""Chronological event-group splits. No automatic generation of gold labels."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from collections import defaultdict
from .schema import load_jsonl,save_jsonl,check_record,prompt_messages,timestamp,digest

def split_records(rows,train_end,validation_end,test_end=None,allow_synthetic=False):
    t=timestamp(train_end);v=timestamp(validation_end);end=timestamp(test_end) if test_end else None
    if not t<v or (end and not v<end):raise ValueError('train_end < validation_end < test_end required')
    approved=[];rejected=[];seen={}
    for r in rows:
        errs=check_record(r,require_review=True)
        if r.get('synthetic') and not allow_synthetic:errs.append('synthetic excluded outside smoke mode')
        if not r.get('id'):errs.append('record id missing')
        if r.get('id') in seen:
            if digest(r)!=seen[r['id']]:errs.append('conflicting duplicate ID')
            else:continue
        if errs:rejected.append({'id':r.get('id'),'errors':errs});continue
        seen[r['id']]=digest(r);approved.append(r)
    groups=defaultdict(list)
    for r in approved:groups[r['event_cluster']].append(r)
    sets={'train':[],'validation':[],'test':[]};purged=[]
    for cluster,rs in sorted(groups.items()):
        names=set()
        for r in rs:
            d=timestamp(r['decision_at'])
            names.add('train' if d<=t else 'validation' if d<=v else 'test' if end is None or d<=end else 'outside')
        # An evolving event spanning the boundary is removed completely, not moved
        # backward into training or mixed across test/train.
        if len(names)>1 or 'outside' in names:purged.append({'event_cluster':cluster,'reason':'cross-boundary/outside','n':len(rs)});continue
        name=next(iter(names));sets[name]+=rs
    text_owners=defaultdict(set)
    for name,rs in sets.items():
        for r in rs:
            for d in r['documents']:text_owners[digest(' '.join(d['text'].split()).lower())].add(name)
    cross_text={h for h,names in text_owners.items() if len(names)>1}
    for name in sets:
        kept=[]
        for r in sets[name]:
            if any(digest(' '.join(d['text'].split()).lower()) in cross_text for d in r['documents']):
                purged.append({'event_cluster':r['event_cluster'],'reason':'identical source text across splits','n':1})
            else:kept.append(r)
        sets[name]=kept
    for name in sets:sets[name].sort(key=lambda r:(r['decision_at'],r['id']))
    return sets,{'rejected':rejected,'purged':purged,'counts':{k:len(v) for k,v in sets.items()},
                 'event_groups':{k:len({r['event_cluster'] for r in v}) for k,v in sets.items()},
                 'boundaries':{'train_end':train_end,'validation_end':validation_end,'test_end':test_end},
                 'scope':'Evidence interpretation only. Return-model labels need additional outcome-window purging.',
                 'not_proof_of_pretraining_cleanliness':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('reviewed');p.add_argument('--out',default='private_data/splits')
    p.add_argument('--train-end',required=True);p.add_argument('--validation-end',required=True);p.add_argument('--test-end')
    p.add_argument('--allow-synthetic',action='store_true');a=p.parse_args()
    sets,report=split_records(load_jsonl(a.reviewed),a.train_end,a.validation_end,a.test_end,a.allow_synthetic)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for name,rows in sets.items():save_jsonl(out/(name+'.jsonl'),rows)
    report['dataset_sha256']={name:digest(rows) for name,rows in sets.items()}
    (out/'split_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not all(sets.values()):raise SystemExit('One split is empty: label more independent events or adjust the predeclared boundaries. Do not random-split to hide this.')
if __name__=='__main__':main()
