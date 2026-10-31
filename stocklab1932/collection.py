"""Bounded CPU collection. Raw real documents != reviewed gold; no invented dates.
No provider limits are bypassed. Downloads are cached and provenance is saved.
"""
from __future__ import annotations
import io,json,hashlib,time,re,zipfile
from pathlib import Path
from datetime import datetime,timezone
import requests
from stocklab192.schema import blank_gold,save_jsonl,digest

SOURCES={
 'twse_revenue':{'url':'https://openapi.twse.com.tw/v1/opendata/t187ap05_L','card':'https://data.gov.tw/dataset/18420','license':'Open Government Data License 1.0; attribution required','purpose':'real Taiwan monthly revenue facts; drafts require review'},
 'phrasebank':{'repo':'takala/financial_phrasebank','file':'data/FinancialPhraseBank-v1.0.zip','card':'https://huggingface.co/datasets/takala/financial_phrasebank','license':'CC-BY-NC-SA-3.0','purpose':'English sentiment auxiliary benchmark, not future stock returns'},
 'finqa':{'repo':'czyssrs/FinQA','files':['dataset/train.json','dataset/dev.json','dataset/test.json'],'card':'https://github.com/czyssrs/FinQA','license':'repository MIT; verify third-party document rights','purpose':'numerical reasoning auxiliary task; preserve official splits'},
 'sec':{'url':'https://data.sec.gov/submissions/CIK{cik:010d}.json','card':'https://www.sec.gov/search-filings/edgar-application-programming-interfaces','license':'verify underlying filing rights; no automatic training approval','purpose':'filing metadata, not full news text'},
}
def stamp():return datetime.now(timezone.utc).isoformat()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
class Collector:
 def __init__(self,cache,contact='StockLab academic personal research',max_requests=12):
  self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True);self.calls=0;self.max_requests=max_requests;self.contact=contact;self.session=requests.Session();self.last=0
 def get(self,url,max_bytes=24*1024**2,cache=True):
  from urllib.parse import urlparse
  u=urlparse(url)
  if u.scheme!='https' or u.hostname not in {'huggingface.co','raw.githubusercontent.com','api.github.com','openapi.twse.com.tw','www.tpex.org.tw','data.sec.gov'}:raise ValueError('只允許登記的HTTPS資料來源')
  key=hashlib.sha256(url.encode()).hexdigest();p=self.cache/(key+'.bin');mp=self.cache/(key+'.json')
  if cache and p.exists() and mp.exists():
   meta=json.loads(mp.read_text());body=p.read_bytes()
   if hashlib.sha256(body).hexdigest()!=meta['sha256']:raise ValueError('cache hash mismatch')
   return body,meta
  if self.calls>=self.max_requests:raise ValueError('本輪CPU抓取預算用完；不開GPU也不自動繞過配額')
  time.sleep(max(0,1.2-(time.monotonic()-self.last)));self.last=time.monotonic();self.calls+=1
  r=self.session.get(url,headers={'User-Agent':self.contact,'Accept':'application/json,text/plain,*/*'},timeout=(10,30),stream=True)
  if r.status_code in (401,403,429):r.close();raise RuntimeError(f'{r.status_code}：停止此來源，不繞過封鎖／限流')
  r.raise_for_status();chunks=[];size=0
  for ch in r.iter_content(65536):
   size+=len(ch)
   if size>max_bytes:r.close();raise ValueError('來源超過本輪下載上限')
   chunks.append(ch)
  r.close();body=b''.join(chunks);meta={'url':url,'fetched_at':stamp(),'bytes':size,'sha256':hashlib.sha256(body).hexdigest()}
  p.write_bytes(body);write(mp,meta);return body,meta
 def json(self,url,**kw):
  body,meta=self.get(url,**kw);return json.loads(body),meta

def revenue_records(rows,meta,limit=120):
 out=[]
 for row in rows:
  code=str(row.get('公司代號','')).strip();name=str(row.get('公司名稱') or row.get('公司簡稱') or '').strip()
  if not re.fullmatch(r'\d{4}',code) or not name:continue
  # Do not turn revenue period or dataset refresh date into a publication timestamp.
  text=json.dumps(row,ensure_ascii=False,sort_keys=True)
  at=meta['fetched_at'];rid='revenue-'+digest({'code':code,'text':text})[:20]
  gold=blank_gold();gold.update(category='monthly_revenue',relation='direct',reported_status='realized',fundamental_direction='unknown',
    evidence=[{'doc_id':'d1','quote':text}],mechanisms=[{'claim':'官方結構化月營收資料；比較期間、單位與成長來源仍需人工核對。','basis':'stated_fact','evidence_ids':['d1']}],
    missing=['首次公告時分未知；目前只保證抓取時可取得','營收不是利潤；缺毛利、現金流與成長來源'],next_check=['核對資料年月與單位','比對月增／年增與公司公告'])
  out.append({'id':rid,'event_cluster':rid,'synthetic':False,'decision_at':at,
    'issuer':{'symbol':code+'.TW','name':name,'sector':str(row.get('產業別',''))},
    'documents':[{'id':'d1','text':text,'published_at':at,'available_at':at,'source_kind':'official_structured','language':'zh-TW','source_url':meta['url'],'training_allowed':False,
    'timestamp_basis':'observed_at upper bound; exact original publication unknown','raw_sha256':meta['sha256'],'license':SOURCES['twse_revenue']['license']}],
    'gold':gold,'review':{'approved':False,'reviewer':'','cluster_verified':False},'draft_method':'numeric_source_only_NOT_human_gold'})
  if len(out)>=limit:break
 return out

def fetch_revenue(c:Collector,out,limit=120):
 rows,meta=c.json(SOURCES['twse_revenue']['url'],cache=False)
 if not isinstance(rows,list) or not rows:raise ValueError('月營收來源不是非空列表')
 records=revenue_records(rows,meta,limit);save_jsonl(Path(out)/'review_queue_revenue.jsonl',records)
 write(Path(out)/'revenue_provenance.json',{**meta,**SOURCES['twse_revenue'],'rows_returned':len(rows),'draft_records':len(records),'historical_publication_verified':False})
 return records

def fetch_phrasebank(c:Collector,out,accept_noncommercial=False):
 if not accept_noncommercial:raise ValueError('先閱讀並確認CC BY-NC-SA 3.0用途；預設不下載')
 s=SOURCES['phrasebank'];info,_=c.json('https://huggingface.co/api/datasets/'+s['repo'],cache=False);rev=info.get('sha','')
 if not re.fullmatch('[0-9a-f]{40}',rev):raise ValueError('HF revision invalid')
 body,meta=c.get(f'https://huggingface.co/datasets/{s["repo"]}/resolve/{rev}/{s["file"]}')
 with zipfile.ZipFile(io.BytesIO(body)) as z:
  candidates=[n for n in z.namelist() if n.endswith('Sentences_AllAgree.txt')]
  if len(candidates)!=1:raise ValueError('PhraseBank格式改變；不猜欄位')
  info=z.getinfo(candidates[0])
  if info.file_size>8*1024**2:raise ValueError('benchmark too large')
  text=z.read(candidates[0]).decode('latin-1')
 rows=[];seen=set()
 for line in text.splitlines():
  if '@' not in line:continue
  sentence,label=line.rsplit('@',1);label=label.strip();sentence=sentence.strip()
  if label not in ('positive','negative','neutral') or not sentence:continue
  key=digest(sentence.lower())
  if key in seen:continue
  seen.add(key);rows.append({'id':key,'text':sentence,'label':label,'label_source':'original_phrasebank_annotators','task':'sentiment_only','published_at':None,'event_cluster':None,'source':s['card'],'license':s['license']})
 if not rows:raise ValueError('沒有可解析的真實資料；不以合成資料補足')
 # Preserve text and provider labels. No fabricated issuer, timestamp, causal gold or price outcome.
 save_jsonl(Path(out)/'phrasebank_real_sentiment.jsonl',rows)
 write(Path(out)/'phrasebank_provenance.json',{**meta,**s,'revision':rev,'n':len(rows),'stocklab_evidence_schema_ready':False,'warning':'無逐則時間；只做輔助情緒，不可冒充台股時序獲利驗證'})
 return rows

def fetch_finqa(c:Collector,out):
 s=SOURCES['finqa'];info,_=c.json('https://api.github.com/repos/'+s['repo']+'/commits/main',cache=False);rev=info.get('sha','')
 if not re.fullmatch('[0-9a-f]{40}',rev):raise ValueError('GitHub revision invalid')
 result={}
 for filename in s['files']:
  rows,meta=c.json(f'https://raw.githubusercontent.com/{s["repo"]}/{rev}/{filename}')
  if not isinstance(rows,list):raise ValueError('FinQA格式變動')
  split=Path(filename).stem;write(Path(out)/('finqa_'+split+'.json'),rows)
  result[split]={'count':len(rows),**meta}
 write(Path(out)/'finqa_provenance.json',{**s,'revision':rev,'splits':result,'warning':'保留官方train/dev/test；不同任務，不自動轉成股票報酬或人工核准教材'})
 return result

def sec_index(c:Collector,out,cik):
 if '@' not in c.contact:raise ValueError('SEC需適當連絡User-Agent；請填自己的真實email，不使用示例')
 obj,meta=c.json(SOURCES['sec']['url'].format(cik=int(cik)))
 recent=obj.get('filings',{}).get('recent',{});rows=[]
 for i,acc in enumerate(recent.get('accessionNumber',[])[:100]):
  rows.append({k:v[i] for k,v in recent.items() if isinstance(v,list) and i<len(v)})
 write(Path(out)/f'sec_{int(cik):010d}_index.json',{'issuer':obj.get('name'),**meta,'filings':rows,'metadata_only':True})
 return rows

def collect(out,phrasebank=False,finqa=False,revenue=True,contact='StockLab personal research'):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);c=Collector(out/'download_cache',contact=contact);results={}
 for name,enabled,fn in [('revenue',revenue,lambda:fetch_revenue(c,out)),('phrasebank',phrasebank,lambda:fetch_phrasebank(c,out,True)),('finqa',finqa,lambda:fetch_finqa(c,out))]:
  if not enabled:continue
  try:r=fn();results[name]={'ok':True,'n':len(r)}
  except Exception as e:results[name]={'ok':False,'error':str(e),'synthetic_fallback':False}
 write(out/'collection_report.json',{'at':stamp(),'requests':c.calls,'results':results,'GPU_used':False});return results
