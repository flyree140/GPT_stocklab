"""Collect daily TWSE/TPEx flow once per market. Missing fields remain None.
No historical first-availability dates are fabricated when fetching later.
"""
from pathlib import Path
from datetime import datetime,date,timedelta
from zoneinfo import ZoneInfo
import json,re,math
from .collection import Collector,write
from stocklab17.calendar import expected_close
from .foreign import defense
from stocklab192.schema import timestamp
TZ=ZoneInfo('Asia/Taipei')
TWSE='https://www.twse.com.tw/rwd/zh/fund/T86'
TPEX='https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading'

def n(v):
 try:
  if isinstance(v,bool):return None
  x=float(str(v).replace(',','').strip());return x if math.isfinite(x) else None
 except (TypeError,ValueError):return None

def iso_day(v):
 d=re.sub(r'\D','',str(v or ''))
 if len(d)==7:d=str(int(d[:3])+1911)+d[3:]
 if len(d)!=8:raise ValueError('來源交易日期不可解析')
 return date(int(d[:4]),int(d[4:6]),int(d[6:8])).isoformat()

def parse_twse(obj,requested,observed):
 if not isinstance(obj,dict) or str(obj.get('stat','')).upper()!='OK':raise ValueError('TWSE沒有可核對日報')
 actual=iso_day(obj.get('date'))
 if actual!=requested:raise ValueError(f'TWSE日期不符 {actual} != {requested}')
 fields=obj.get('fields',[]);out=[]
 for row in obj.get('data',[]):
  r=dict(zip(fields,row));code=str(r.get('證券代號','')).strip()
  if not re.fullmatch(r'\d{4}|00\d{2,4}',code):continue
  def take(*ks):
   for k in ks:
    if k in r:return n(r[k])
  buy=take('外陸資買進股數(不含外資自營商)');sell=take('外陸資賣出股數(不含外資自營商)');net=take('外陸資買賣超股數(不含外資自營商)')
  if net is None and buy is not None and sell is not None:net=buy-sell
  if net is None:continue
  out.append({'symbol':code+'.TW','date':actual,'available_at':observed,'foreign_buy':buy,'foreign_sell':sell,'foreign_net':net,
    'trust_net':take('投信買賣超股數'),'dealer_net':take('自營商買賣超股數'),'source':TWSE,'unit':'shares','market':'TWSE'})
 return out

def parse_tpex(rows,requested,observed):
 if not isinstance(rows,list):raise ValueError('TPEx回傳格式變更')
 out=[]
 for r in rows:
  try:actual=iso_day(r.get('Date') or r.get('日期') or r.get('date'))
  except ValueError:continue
  if actual!=requested:continue
  code=str(r.get('SecuritiesCompanyCode') or r.get('Code') or r.get('代號') or '')
  if not re.fullmatch(r'\d{4}|00\d{2,4}',code):continue
  def take(*ks):
   for k in ks:
    if k in r:return n(r[k])
  buy=take('ForeignInvestorsBuy','ForeignInvestorBuy','ForeignInvestorsBuyShares','Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Buy','外資及陸資(不含外資自營商)-買進股數')
  sell=take('ForeignInvestorsSell','ForeignInvestorSell','ForeignInvestorsSellShares','Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Sell','外資及陸資(不含外資自營商)-賣出股數')
  net=take('ForeignInvestorsNet','ForeignInvestorsNetBuySell','ForeignInvestorsDifference','Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference','外資及陸資(不含外資自營商)-買賣超股數')
  if net is None and buy is not None and sell is not None:net=buy-sell
  if net is None:continue
  out.append({'symbol':code+'.TWO','date':actual,'available_at':observed,'foreign_buy':buy,'foreign_sell':sell,'foreign_net':net,
   'trust_net':take('InvestmentTrustNet','InvestmentTrustDifference','SecuritiesInvestmentTrustCompanies-Difference','投信-買賣超股數'),
   'dealer_net':take('DealerNet','DealerDifference','Dealers-Difference','自營商-買賣超股數'),'source':TPEX,'unit':'shares','market':'TPEx'})
 if not out:raise ValueError('TPEx日期或欄位未核對；不以0填值，不套用TWSE資料')
 return out

def load_flows(root,symbol,cutoff):
 out=[]
 for p in sorted((Path(root)/'data/institutional1932/days').glob('*.json')):
  try:
   obj=json.loads(p.read_text());out.extend(r for r in obj.get('rows',[]) if r['symbol']==symbol and timestamp(r['available_at'])<=timestamp(cutoff))
  except (ValueError,KeyError):continue
 return out

def attach(root,stock,cutoff):
 rows=load_flows(root,stock['symbol'],cutoff)
 proxy=defense(stock.get('candles',[]),rows,cutoff)
 facts=[]
 if rows:
  r=max(rows,key=lambda r:r['date'])
  for name,key in [('foreign_net_shares','foreign_net'),('trust_net_shares','trust_net'),('dealer_net_shares','dealer_net')]:
   if r.get(key) is not None:facts.append({'factor':'flow','name':name,'value':r[key],'available_at':r['available_at'],'period':r['date'],'source':r['source'],'unit':'shares'})
 return proxy,facts

def run(root):
 from stocklab1932.collection import Collector
 root=Path(root);now=datetime.now(TZ);day=expected_close(now.isoformat());c=Collector(root/'.cache/flows1932',max_requests=2)
 # Explicitly add only the fixed official TWSE host for this collector.
 import requests,time,hashlib
 status={};rows=[]
 for market,url in [('TWSE',TWSE+'?response=json&date='+day.replace('-','')+'&selectType=ALLBUT0999'),('TPEx',TPEX)]:
  try:
   r=requests.get(url,headers={'User-Agent':'StockLab closed research; bounded 2 requests/day'},timeout=(8,25))
   if r.status_code in (403,429):raise ValueError(f'{r.status_code} stop, no bypass')
   r.raise_for_status();observed=datetime.now(TZ).isoformat();obj=r.json()
   parsed=parse_twse(obj,day,observed) if market=='TWSE' else parse_tpex(obj,day,observed)
   rows+=parsed;status[market]={'ok':True,'count':len(parsed),'sha256':hashlib.sha256(r.content).hexdigest(),'url':url}
  except Exception as e:status[market]={'ok':False,'error':str(e),'url':url}
 dest=root/'data/institutional1932';p=dest/'days'/f'{day}.json'
 old=json.loads(p.read_text()) if p.exists() else {'rows':[]};combined={r['symbol']:r for r in old['rows']}
 for r in rows:
  if r['symbol'] not in combined:combined[r['symbol']]=r
  elif any(r.get(k)!=combined[r['symbol']].get(k) for k in ('foreign_net','trust_net','dealer_net')):
   status.setdefault('revisions',[]).append(r['symbol']) # preserve first observed record; report change, no silent rewrite
 if rows:write(p,{'date':day,'rows':list(combined.values()),'first_observed_records_preserved':True})
 write(dest/'status.json',{'requested_date':day,'collected_at':now.isoformat(),'sources':status,'not_real_cost_basis':True});return status
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');a=p.parse_args();print(json.dumps(run(a.root),ensure_ascii=False))
