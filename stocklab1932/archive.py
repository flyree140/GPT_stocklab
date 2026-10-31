"""User-owned archive -> real headline review queue. No old scores as gold."""
from pathlib import Path
import zipfile,json,re
from stocklab192.schema import digest,blank_gold,save_jsonl,timestamp

def extract(path,out,limit=600):
 found={};bad=0;seen=0
 with zipfile.ZipFile(path) as z:
  for name in sorted(z.namelist()):
   if '/data/snapshots/' not in '/'+name or not name.endswith('.json') or '/demo/' in name:continue
   info=z.getinfo(name)
   if info.file_size>16*1024**2:continue
   try:s=json.loads(z.read(name))
   except (ValueError,KeyError):continue
   if s.get('demo') or s.get('mode') in ('reanalysis','historical_reconstruction'):continue
   cutoff=s.get('generated_at')
   try:timestamp(cutoff)
   except Exception:continue
   for st in s.get('stocks',[]):
    for n in st.get('news',[]):
     seen+=1;title=str(n.get('title') or '').strip();pub=n.get('published_at');available=n.get('available_at') or pub
     try:
      if not title or max(timestamp(pub),timestamp(available))>timestamp(cutoff):bad+=1;continue
     except Exception:bad+=1;continue
     # Cluster identical headline across issuers. Semantic / translated grouping requires human review.
     norm=re.sub(r'\s+',' ',title).lower();key=digest({'symbol':st['symbol'],'text':norm})
     if key in found:continue
     g=blank_gold();g['evidence']=[{'doc_id':'d1','quote':title}]
     g['mechanisms']=[{'claim':'僅為來源標題，影響途徑待核對全文與公司關聯。','basis':'hypothesis','evidence_ids':['d1']}]
     found[key]={'id':key,'event_cluster':digest(norm),'synthetic':False,'decision_at':cutoff,'issuer':{k:st.get(k) for k in ('symbol','name','sector')},'documents':[{'id':'d1','text':title,'published_at':pub,'available_at':available,'language':'zh-TW','source_kind':'headline','source_url':n.get('url') or n.get('source_url'),'training_allowed':False,'license':'review_required'}],'gold':g,'review':{'approved':False,'reviewer':'','cluster_verified':False},'provenance':{'archive_entry':name,'old_model_answer_not_used':True}}
 # Spread the bounded sample over dates and issuers, independent of future outcomes.
 buckets={}
 for r in sorted(found.values(),key=lambda r:(r['decision_at'],r['id'])):buckets.setdefault((r['decision_at'][:10],r['issuer']['symbol']),[]).append(r)
 date_queues={}
 for (day,symbol),q in sorted(buckets.items()):date_queues.setdefault(day,[]).append(q)
 # One issuer-event per date per round; do not exhaust earliest 30 days first.
 dates=sorted(date_queues);selected=[]
 while dates and len(selected)<limit:
  nd=[]
  for day in dates:
   if len(selected)>=limit:break
   qs=date_queues[day];q=qs.pop(0);selected.append(q.pop(0))
   if q:qs.append(q)
   if qs:nd.append(day)
  dates=nd
 save_jsonl(out,selected)
 report={'article_occurrences':seen,'time_invalid':bad,'unique_real_headline_issuer_pairs':len(found),'selected':len(selected),'dates':len({r['decision_at'][:10] for r in selected}),'approved_gold':0,'training_rights_confirmed':0,'synthetic_rows':0}
 Path(str(out)+'.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
