"""Bounded global inputs. Every response retains observation time; no retroactive fills.
Quote bars are daily provider observations, NOT official/live executable quotations.
"""
from __future__ import annotations
import csv, hashlib, io, json, math, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlencode, urlsplit
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from pathlib import Path
from stocklab16.common import dt, now, read_json, write_json
from .evidence import download, plain, meaningful, safe_url

VERSION='19.3.4-global.1'
# Daily market cutoffs are conservative nominal closing boundaries, not intraday quotes.
def instrument(key,label,symbol,region,tz,close,kind='equity',**extra):
 return dict(key=key,label=label,symbol=symbol,region=region,timezone=tz,close=close,kind=kind,provider='yahoo_chart',**extra)
INSTRUMENTS=[
 instrument('SPX','美國 S&P 500','^GSPC','US','America/New_York','16:00'),
 instrument('NASDAQ','美國 Nasdaq','^IXIC','US','America/New_York','16:00'),
 instrument('SOX','費城半導體','^SOX','US','America/New_York','16:00'),
 instrument('NIKKEI','日本日經225','^N225','JP','Asia/Tokyo','15:30'),
 instrument('KOSPI','韓國 KOSPI','^KS11','KR','Asia/Seoul','15:30'),
 instrument('KOSDAQ','韓國 KOSDAQ','^KQ11','KR','Asia/Seoul','15:30'),
 instrument('HSI','香港恆生','^HSI','HK','Asia/Hong_Kong','16:00'),
 instrument('STOXX50','歐洲 Euro Stoxx 50','^STOXX50E','EU','Europe/Berlin','17:30'),
 instrument('TWII','台灣加權指數','^TWII','TW','Asia/Taipei','13:30'),
 instrument('VIX','美股 VIX','^VIX','US','America/New_York','16:15','volatility'),
 instrument('DXY','美元指數','DX-Y.NYB','FX','UTC','23:59','dollar_index'),
 *[instrument('USD'+c,'美元／'+n,s,'FX','UTC','23:59','fx',local_currency=c,quote_convention='local_currency_per_USD') for c,n,s in [('TWD','新台幣','TWD=X'),('JPY','日圓','JPY=X'),('KRW','韓元','KRW=X'),('CNY','人民幣','CNY=X')]],
 instrument('WTI','WTI原油近月期貨','CL=F','Commodity','America/New_York','17:00','commodity',roll_warning=True),
 instrument('GOLD','黃金近月期貨','GC=F','Commodity','America/New_York','17:00','commodity',roll_warning=True),
 dict(key='US10Y',label='美國10年公債殖利率',symbol='DGS10',region='US',timezone='America/New_York',close='23:59',kind='yield',provider='fred_csv'),
 dict(key='US2Y',label='美國2年公債殖利率',symbol='DGS2',region='US',timezone='America/New_York',close='23:59',kind='yield',provider='fred_csv'),
]
FEEDS=[
 dict(name='Federal Reserve 官方貨幣政策',url='https://www.federalreserve.gov/feeds/press_monetary.xml',official=True),
 dict(name='ECB 官方新聞',url='https://www.ecb.europa.eu/rss/press.html',official=True),
 dict(name='日本銀行官方動態',url='https://www.boj.or.jp/en/rss/whatsnew.xml',official=True),
]
SEARCHES=[
 ('美股與AI產業','US stocks Nasdaq semiconductor AI capital expenditure selloff'),
 ('日本與韓國','Nikkei KOSPI Korea Japan stocks yen won'),
 ('亞洲幣值','Taiwan dollar yen won yuan appreciation depreciation'),
 ('選舉與政策','US election midterm tariff export control legislation policy'),
 ('台股跨市場傳導','美股 日韓 匯率 選舉 關稅 台股'),
]
DEFAULT={'enabled':True,'max_quote_requests':19,'max_news_requests':8,'max_seconds':180,
 'timeout_seconds':8,'quote_cache_minutes':60,'news_cache_minutes':120,'lookback_days':10}

def finite(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except (TypeError,ValueError):return None

def close_boundary(day,spec):
 hh,mm=map(int,spec['close'].split(':'))
 return datetime.fromisoformat(day).replace(hour=hh,minute=mm,tzinfo=ZoneInfo(spec['timezone']))+timedelta(minutes=45)

def parse_yahoo(body,spec,observed_at):
 payload=json.loads(body);chart=payload.get('chart',{})
 if chart.get('error'):raise ValueError('provider_error:'+str(chart['error'])[:160])
 result=(chart.get('result') or [None])[0]
 if not result:raise ValueError('no_chart_result')
 meta=result.get('meta',{})
 if meta.get('symbol') and meta['symbol']!=spec['symbol']:raise ValueError('symbol_mismatch')
 rows=[];at=dt(observed_at);values=(result.get('indicators',{}).get('quote') or [{}])[0].get('close',[])
 for timestamp,value in zip(result.get('timestamp',[]),values):
  n=finite(value)
  if n is None or n<=0:continue
  event_at=datetime.fromtimestamp(timestamp,timezone.utc)
  if event_at>at:continue
  day=event_at.astimezone(ZoneInfo(spec['timezone'])).date().isoformat()
  ready=close_boundary(day,spec)
  if ready>at:continue
  if datetime.fromisoformat(day).weekday()>=5:continue
  rows.append({'date':day,'value':n,'session_complete_after':ready.isoformat(),
               'observed_at':observed_at,'available_at':observed_at})
 rows=sorted({r['date']:r for r in rows}.values(),key=lambda r:r['date'])[-80:]
 return rows

def parse_fred(body,spec,observed_at):
 reader=csv.DictReader(io.StringIO(body.decode('utf-8-sig')));out=[];at=dt(observed_at)
 for r in reader:
  day=r.get('observation_date') or r.get('DATE');value=finite(r.get(spec['symbol']))
  if not day or value is None:continue
  try:ready=close_boundary(day,spec)
  except ValueError:continue
  if ready>at:continue
  # Retain observations; never treat current FRED series as historical vintages.
  out.append({'date':day,'value':value,'session_complete_after':ready.isoformat(),
              'observed_at':observed_at,'available_at':observed_at})
 return sorted({r['date']:r for r in out}.values(),key=lambda r:r['date'])[-80:]

def parse_feed(body,source,observed_at,days=10):
 if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():raise ValueError('DTD_not_allowed')
 root=ET.fromstring(body);at=dt(observed_at);earliest=at-timedelta(days=days)
 entries=root.findall('.//item')+root.findall('{http://www.w3.org/2005/Atom}entry')
 if not entries:entries=[e for e in root.iter() if e.tag.rsplit('}',1)[-1]=='item']
 out=[]
 def field(node,names):
  for child in node:
   if child.tag.rsplit('}',1)[-1] in names:
    return child.attrib.get('href') or ''.join(child.itertext())
  return ''
 for node in entries:
  title=plain(field(node,{'title'}));url=plain(field(node,{'link'}));raw=field(node,{'pubDate','published','updated','date'})
  try:
   try:when=parsedate_to_datetime(raw)
   except (ValueError,TypeError):when=datetime.fromisoformat(raw.replace('Z','+00:00'))
   if when.tzinfo is None or not earliest<=when<=at:continue
  except (ValueError,TypeError):continue
  if not title or not safe_url(url):continue
  intro=plain(field(node,{'description','summary','content'}));good=meaningful(title,intro)
  publisher=plain(field(node,{'source'})) or source['name']
  out.append({'id':hashlib.sha256((title+'|'+url).encode()).hexdigest()[:20],
   'title':title,'url':url,'publisher':publisher,'published_at':when.isoformat(),
   'available_at':observed_at,'fetched_at':observed_at,'excerpt':intro[:420] if good else '',
   'content_status':'rss_introduction' if good else 'headline_only',
   'content_reason':'來源RSS前言，不是全文或已核實因果' if good else '來源沒有有效前言，不宣稱看過全文',
   'feed_name':source['name'],'official_feed':bool(source.get('official')),
   'verified_document':False,'training_allowed':False,
   'rights_scope':'來源RSS閱讀；保留署名與連結，不自動取得訓練授權'})
 return out[:60]

class GlobalCollector:
 def __init__(self,root,fetcher=None,clock=None,monotonic=None):
  self.root=Path(root);self.clock=clock or now;self.fetch=fetcher or download
  self.monotonic=monotonic or time.monotonic;self.started=self.monotonic()
  self.cfg={**DEFAULT,**(read_json(self.root/'config/global-research.json',{}) or {})}
  self.path=self.root/'data/system/global194-cache.json';self.cache=read_json(self.path,{}) or {}
  self.status=[];self.quote_requests=0;self.news_requests=0
 def request(self,key,url,parser,ttl,kind):
  current=self.clock();old=self.cache.get(key,{});stamp=current.isoformat()
  try:age=(current-dt(old['observed_at'])).total_seconds()
  except (KeyError,ValueError,TypeError):age=1e12
  if not self.cfg.get('enabled'):
   self.status.append({'key':key,'state':'disabled'});return []
  if 0<=age<ttl*60:
   self.status.append({'key':key,'state':'cache','observed_at':old['observed_at'],'rows':len(old.get('rows',[]))})
   return old.get('rows',[])
  limit=min(19,max(0,int(self.cfg['max_quote_requests']))) if kind=='quote' else min(8,max(0,int(self.cfg['max_news_requests'])))
  spent=self.quote_requests if kind=='quote' else self.news_requests
  if spent>=limit or self.monotonic()-self.started>min(240,max(1,int(self.cfg['max_seconds']))):
   self.status.append({'key':key,'state':'budget_limit','observed_at':old.get('observed_at')})
   return old.get('rows',[]) if age>=0 else []
  if kind=='quote':self.quote_requests+=1
  else:self.news_requests+=1
  try:
   host=urlsplit(url).hostname
   body=self.fetch(url,timeout=min(12,max(1,int(self.cfg['timeout_seconds']))),hosts=[host])
   rows=parser(body,stamp)
   if not rows:raise ValueError('no_eligible_records')
   self.cache[key]={'observed_at':stamp,'rows':rows,'source_url':url}
   self.status.append({'key':key,'state':'ok','observed_at':stamp,'rows':len(rows)})
   return rows
  except Exception as exc:
   self.status.append({'key':key,'state':'failed','error':type(exc).__name__+': '+str(exc)[:140],
      'cached_observed_at':old.get('observed_at'),'fallback_cached':bool(old.get('rows'))})
   return old.get('rows',[]) if age>=0 else []
 def collect(self):
  quotes=[]
  for spec in INSTRUMENTS:
   if spec['provider']=='fred_csv':
    start=(self.clock().date()-timedelta(days=140)).isoformat()
    url='https://fred.stlouisfed.org/graph/'+'fredgraph.csv?'+urlencode({'id':spec['symbol'],'cosd':start})
    parser=lambda body,stamp,s=spec:parse_fred(body,s,stamp)
    source='Federal Reserve H.15 / FRED；目前可見序列，不是歷史vintage'
    link='https://fred.stlouisfed.org/series/'+spec['symbol']
   else:
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(spec['symbol'],safe='')+'?range=6mo&interval=1d'
    parser=lambda body,stamp,s=spec:parse_yahoo(body,s,stamp)
    source='Yahoo日頻資料，非交易所獨立核驗／非即時報價'
    link='https://finance.yahoo.com/quote/'+quote(spec['symbol'],safe='')+'/'
   rows=self.request('quote:'+spec['key'],url,parser,int(self.cfg['quote_cache_minutes']),'quote')
   quotes.append({**spec,'bars':rows,'source':source,'source_url':link})
  sources=list(FEEDS)
  for name,q in SEARCHES:
   url='https://news.google.com/rss/search?'+urlencode({'q':q+' when:7d','hl':'en-US','gl':'US','ceid':'US:en'})
   sources.append({'name':'Google News / '+name,'url':url,'official':False})
  events=[]
  for source in sources:
   rows=self.request('news:'+source['name'],source['url'],lambda b,s,f=source:parse_feed(b,f,s,int(self.cfg['lookback_days'])),int(self.cfg['news_cache_minutes']),'news')
   events.extend(rows)
  cutoff=self.clock();unique={}
  for row in events:
   try:
    if not dt(row['available_at'])<=cutoff or not 0<=(cutoff-dt(row['published_at'])).total_seconds()<=int(self.cfg['lookback_days'])*86400:continue
   except (ValueError,KeyError):continue
   key=(plain(row['title']).casefold(),row['published_at'][:10]);old=unique.get(key)
   if not old or len(row.get('excerpt',''))>len(old.get('excerpt','')):unique[key]=row
  write_json(self.path,self.cache)
  return quotes,sorted(unique.values(),key=lambda x:x['published_at'],reverse=True)[:100]
 def report(self):
  return {'quote_requests':self.quote_requests,'news_requests':self.news_requests,
   'quote_limit':min(19,int(self.cfg['max_quote_requests'])),'news_limit':min(8,int(self.cfg['max_news_requests'])),
   'seconds':round(self.monotonic()-self.started,2),'qwen_calls':0,'sources':self.status,
   'coverage_note':'有限市場日頻與RSS樣本；不是全網、盤中即時、全文擷取或已證實因果'}
