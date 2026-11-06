"""Bounded RSS introductions and explicitly opted-in document extracts.
No paywall/Google redirect decoding, no source-homepage-as-article, no full-body
redistribution and no current retrieval backfilled into historical snapshots.
"""
from __future__ import annotations
import hashlib, html, json, re, time, urllib.parse, urllib.request, urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from html.parser import HTMLParser
from stocklab16.common import TZ, now, dt, read_json, write_json

UA='StockLab-PaperLab/19.3.4 (personal non-commercial RSS research)'
FEEDS=[
 {'name':'中央通訊社・產經證券','url':'https://feeds.feedburner.com/rsscna/finance'},
 {'name':'中央通訊社・國際','url':'https://feeds.feedburner.com/rsscna/intworld'},
]
TOPICS=[
 ('market','台股 外資 融資 匯率'),
 ('industry','半導體 AI 資料中心 訂單 財測'),
 ('global','semiconductor data center capex restrictions earnings'),
]
POLICY='https://www.cna.com.tw/about/rss.aspx'
DEFAULT={'enabled':True,'max_context_requests':5,'max_article_requests':6,
 'max_seconds':90,'timeout_seconds':12,'max_excerpt_chars':600,
 'cache_minutes':120,'feeds':FEEDS,'article_sources':[]}

class Cleaner(HTMLParser):
 def __init__(self): super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','noscript'):self.skip+=1
  if tag in ('p','br','div','li'):self.parts.append(' ')
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript') and self.skip:self.skip-=1
  if tag in ('p','div','li'):self.parts.append(' ')
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)
def plain(value):
 p=Cleaner()
 try:p.feed(str(value or ''));return ' '.join(html.unescape(''.join(p.parts)).split())
 except Exception:return ''
def norm(title):return re.sub(r'[^\w\u4e00-\u9fff]','',plain(title).rsplit(' - ',1)[0].lower())
def meaningful(title,text):
 a,b=norm(title),norm(text)
 return bool(len(b)>=40 and b!=a and b not in a and len(b.replace(a,''))>=30)
def safe_url(url):
 p=urllib.parse.urlsplit(str(url));host=(p.hostname or '').lower()
 if p.scheme!='https' or not host or p.username or p.password or p.port not in (None,443):return False
 # No literal/private network targets. Outbound hosts also need configuration below.
 if host in ('localhost','metadata.google.internal') or ':' in host or re.fullmatch(r'[\d.]+',host):return False
 return not host.endswith(('.local','.internal'))
class Redirects(urllib.request.HTTPRedirectHandler):
 def __init__(self,hosts):super().__init__();self.hosts=set(hosts)
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if not safe_url(newurl) or urllib.parse.urlsplit(newurl).hostname not in self.hosts:raise ValueError('redirect_host_not_allowed')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def download(url,timeout=12,max_bytes=1500000,hosts=None):
 if not safe_url(url):raise ValueError('unsafe_url')
 host=urllib.parse.urlsplit(url).hostname;allowed=set(hosts or [host])
 if host not in allowed:raise ValueError('host_not_allowed')
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/rss+xml,application/xml,text/html;q=0.8'})
 opener=urllib.request.build_opener(Redirects(allowed))
 with opener.open(req,timeout=timeout) as r:
  body=r.read(max_bytes+1)
  if len(body)>max_bytes:raise ValueError('response_too_large')
  return body

def parse_feed(body,source,observed_at,lookback_days=7,max_chars=600):
 if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():raise ValueError('DTD_not_allowed')
 root=ET.fromstring(body);end=dt(observed_at);start=end-timedelta(days=lookback_days);out=[]
 for x in root.findall('.//item'):
  title=plain(x.findtext('title'));link=plain(x.findtext('link'));raw=x.findtext('pubDate') or ''
  try:published=parsedate_to_datetime(raw)
  except Exception:continue
  if published.tzinfo is None:continue
  if not start<=published<=end:continue
  s=x.find('source');publisher=(s.text or '').strip() if s is not None else source['name']
  desc=plain(x.findtext('description') or '')
  good=meaningful(title,desc)
  src_url=s.attrib.get('url',link) if s is not None else link
  out.append({'id':hashlib.sha256((title+'|'+link).encode()).hexdigest()[:20],
   'title':title,'url':link,'source_url':src_url,'publisher':publisher,
   'published_at':published.isoformat(),'available_at':observed_at,'fetched_at':observed_at,
   'excerpt':desc[:max_chars] if good else '', 'excerpt_origin':'publisher_rss_introduction' if good else None,
   'evidence_level':'rss_introduction' if good else 'headline',
   'content_status':'rss_introduction' if good else 'headline_only',
   'content_reason':'來源RSS提供前言；不是完整文章或已核對公司公告' if good else '來源RSS無超出標題的有效前言，未宣稱已讀全文',
   'rights_scope':'中央社RSS個人非商業閱讀；不是訓練授權' if source['url'].startswith('https://feeds.feedburner.com/rsscna/') else '來源RSS內容，依原站條款使用；未取得模型訓練授權',
   'terms_url':POLICY if source['url'].startswith('https://feeds.feedburner.com/rsscna/') else None,
   'verified_document':False,'feed_url':source['url']})
 return [r for r in out if r['title'] and safe_url(r['url'])]

def topic_tags(text):
 specs=[('ai_policy','AI／資料中心政策與資本支出',r'資料中心|data center|capex|AI.{0,12}(?:監管|限制|基建)'),
 ('semiconductors','半導體與海外價格傳導',r'半導體|semiconductor|費半|費城|ADR|chip'),
 ('capital_flow','資金與流動性',r'外資|融資|賣超|匯率|貶值|margin call|outflow'),
 ('macro','利率／政策／總體',r'利率|降息|升息|關稅|制裁|tariff|interest rate|regulat'),
 ('selloff','市場急跌／風險',r'重挫|崩跌|暴跌|大跌|連跌|失守|sell.off|plunge|slump')]
 return [{'key':k,'label':v} for k,v,p in specs if re.search(p,text,re.I)]

def relationship(meta,event):
 text=plain(event.get('title','')+' '+event.get('excerpt',''));aliases=[meta.get('name',''),*meta.get('aliases',[])]
 if any(a and a.lower() in text.lower() for a in aliases):
  return {'type':'company_mentioned','reason':'文中出現公司名稱；仍須核對主體、期間與事件', 'changes_company_score':False}
 tags={x['key'] for x in event.get('topics',topic_tags(text))};sector=str(meta.get('sector',''))
 if tags & {'ai_policy','semiconductors'} and re.search(r'半導體|電子|電腦|通信|科技',sector):
  return {'type':'sector_hypothesis','reason':'產業風險假設：曝險與收入量級未核對，不當成公司訂單取消事實','changes_company_score':False}
 if tags & {'capital_flow','selloff','macro'}:
  return {'type':'market_risk','reason':'市場風險背景，非這檔公司財報或外資個股明細','changes_company_score':False}
 return None

class Collector:
 def __init__(self,root,fetcher=None,clock=None):
  self.root=Path(root);self.clock=clock or now;self.get=fetcher or download;self.start=time.monotonic()
  self.cfg={**DEFAULT,**(read_json(self.root/'config/news-evidence.json',{}) or {})}
  self.path=self.root/'data/system/news-evidence-cache194.json';self.cache=read_json(self.path,{}) or {}
  self.items=[];self.requests=0;self.article_attempts=0;self.status=[];self.stats={};self.robots={}
 def collect(self):
  if not self.cfg.get('enabled'):self.status.append({'status':'disabled'});return []
  at=self.clock();stamp=at.isoformat();sources=list(self.cfg['feeds'])
  for scope,q in TOPICS:
   query=q+' when:7d'
   url='https://news.google.com/rss/search?q='+urllib.parse.quote_plus(query)+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
   sources.append({'name':'Google News / '+scope,'url':url})
  for source in sources[:min(8,int(self.cfg['max_context_requests']))]:
   url=source['url'];key=hashlib.sha256(url.encode()).hexdigest();old=self.cache.get(key,{})
   try:age=(at-dt(old['fetched_at'])).total_seconds()
   except Exception:age=1e12
   if 0<=age<int(self.cfg['cache_minutes'])*60:
    rows=old.get('items',[]);self.status.append({'source':source['name'],'status':'cache','items':len(rows),'observed_at':old['fetched_at']})
   elif time.monotonic()-self.start>min(180,int(self.cfg['max_seconds'])):
    rows=[];self.status.append({'source':source['name'],'status':'time_budget_reached'})
   else:
    self.requests+=1
    try:
     host=urllib.parse.urlsplit(url).hostname
     body=self.get(url,timeout=min(20,int(self.cfg['timeout_seconds'])),hosts=[host,'feedburner.google.com'])
     rows=parse_feed(body,source,stamp,max_chars=min(800,int(self.cfg['max_excerpt_chars'])))[:120]
     self.cache[key]={'fetched_at':stamp,'items':rows}
     self.status.append({'source':source['name'],'status':'ok','items':len(rows),'observed_at':stamp})
    except Exception as e:
     rows=[];self.status.append({'source':source['name'],'status':'failed','error':type(e).__name__+': '+str(e)[:160]})
   self.items.extend(r for r in rows if dt(r['available_at'])<=at and 0<=(at-dt(r['published_at'])).total_seconds()<=7*86400)
  unique={}
  for r in self.items:
   key=(norm(r['title']),r['published_at'][:10]);previous=unique.get(key)
   if previous is None or len(r.get('excerpt',''))>len(previous.get('excerpt','')):unique[key]=r
  self.items=sorted(unique.values(),key=lambda r:r['published_at'],reverse=True)
  for r in self.items:r['topics']=topic_tags(r['title']+' '+r.get('excerpt',''))
  self.cache={k:v for k,v in self.cache.items() if (at-dt(v['fetched_at'])).total_seconds()<8*86400}
  write_json(self.path,self.cache)
  return self.items
 def enrich(self,items,meta):
  # Supplement company items from directly obtained public RSS, not only company search.
  matching=[r for r in self.items if relationship(meta,r) and relationship(meta,r)['type']=='company_mentioned']
  by_title={norm(r['title']):r for r in self.items if r.get('excerpt')}
  output=[]
  for original in [*items,*matching[:6]]:
   r=dict(original);r.setdefault('content_status','headline_only');r.setdefault('content_reason','沒有來源前言；未取得授權內文')
   desc=plain(r.get('excerpt',''))
   if not meaningful(r.get('title',''),desc):r['excerpt']=''
   candidate=by_title.get(norm(r['title']))
   if candidate and abs((dt(candidate['published_at'])-dt(r['published_at'])).total_seconds())<86400 and len(candidate['excerpt'])>len(r.get('excerpt','')):
    r.update({k:candidate[k] for k in ('excerpt','excerpt_origin','evidence_level','content_status','content_reason','rights_scope','terms_url','url','source_url','publisher','fetched_at') if k in candidate})
    r['verified_document']=False
    r['official_document']=False
    r['available_at']=max(dt(original.get('available_at') or original['published_at']),dt(candidate['available_at'])).isoformat()
   if not r.get('excerpt'):r=self.try_document(r)
   if r.get('excerpt') and r.get('content_status')=='headline_only':r.update(content_status='provided_excerpt',content_reason='提供的節錄；非完整文章',evidence_level='excerpt')
   output.append(r)
  return output
 def try_document(self,r):
  """Only explicit user-approved sources; sources are NOT silently marked verified."""
  url=r.get('url','');host=urllib.parse.urlsplit(url).hostname
  spec=next((s for s in self.cfg.get('article_sources',[]) if s.get('host')==host and s.get('enabled') and s.get('usage_basis')),None)
  if not spec:return r
  if not safe_url(url) or not re.match(spec.get('path_regex',r'^/$'),urllib.parse.urlsplit(url).path):return r
  if self.article_attempts>=min(12,int(self.cfg['max_article_requests'])) or time.monotonic()-self.start>min(180,int(self.cfg['max_seconds'])):
   return {**r,'content_reason':'本輪授權文件擷取預算已達上限'}
  self.article_attempts+=1
  try:
   if host not in self.robots:
    robot=urllib.robotparser.RobotFileParser();robot.parse(self.get('https://'+host+'/robots.txt',timeout=8,hosts=[host]).decode('utf-8','replace').splitlines());self.robots[host]=robot
   if not self.robots[host].can_fetch(UA,url):return {**r,'content_reason':'robots規則不允許擷取，保留標題'}
   body=self.get(url,timeout=12,hosts=[host]).decode('utf-8','replace')
   if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")',body,re.I):return {**r,'content_reason':'付費／受限內容，不擷取'}
   parsed=[]
   for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',body,re.I|re.S):
    try:parsed.append(json.loads(html.unescape(block)))
    except ValueError:continue
   def visit(x):
    if isinstance(x,dict):
     if isinstance(x.get('articleBody'),str):yield x
     for v in x.values():yield from visit(v)
    elif isinstance(x,list):
     for v in x:yield from visit(v)
   articles=[a for x in parsed for a in visit(x)]
   if not articles:return {**r,'content_reason':'找不到可確認的文章正文結構，保留原內容'}
   a=max(articles,key=lambda x:len(x.get('articleBody','')));text=plain(a['articleBody']);at=self.clock()
   for key in ('datePublished','dateModified'):
    if a.get(key) and dt(a[key])>at:raise ValueError('future_document_time')
   if not meaningful(r['title'],text):return {**r,'content_reason':'正文過短或與標題相同'}
   return {**r,'excerpt':text[:min(800,int(self.cfg['max_excerpt_chars']))],
    'evidence_level':'excerpt','excerpt_origin':'opted_in_article_extract','content_status':'licensed_extract',
    'content_reason':'已取得使用者允許來源的正文節錄，未宣稱全文／事實核實',
    'available_at':at.isoformat(),'fetched_at':at.isoformat(),'content_sha256':hashlib.sha256(text.encode()).hexdigest(),
    'rights_scope':spec['usage_basis'],'training_allowed':False,'verified_document':False}
  except Exception as e:return {**r,'content_reason':'文件擷取失敗：'+type(e).__name__+'；未以標題冒充正文'}
 def report(self):
  return {'version':'19.3.4','requests':self.requests,'article_attempts':self.article_attempts,
   'rss_items':len(self.items),'rss_with_intro':sum(bool(r.get('excerpt')) for r in self.items),
   'sources':self.status,'full_text_claimed':False,'model_calls':0,
   'note':'有限RSS與明確授權文件節錄；不是全網、不是所有全文、不自動取得訓練權利'}
