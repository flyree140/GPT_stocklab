"""Explainable global-risk research. No calibrated forecasts or broker orders.
Missing data stays missing; currency orientation and policy stages stay explicit.
"""
from __future__ import annotations
from datetime import timedelta
import math, re
from urllib.parse import urlsplit
from stocklab16.common import dt
from .global_sources import close_boundary, finite

POLICY_PATTERNS=[
 ('suspended_or_disputed',r'暫緩|暫停|禁止執行|法院|訴訟|injunction|suspend|court|appeal'),
 ('proposal',r'提案|草案|擬議|擬對|考慮|可能|計畫|徵詢|propos|draft|consider|could|may |plans? to'),
 ('campaign_promise',r'政見|競選承諾|campaign pledge|campaign promise'),
 ('effective_claim',r'生效|實施|正式施行|effective|takes? effect|enforced'),
 ('legislative_claim',r'通過|簽署|立法|signed into law|enacted|passed'),
 ('election_report',r'大選|選舉|期中選舉|期中選|選情|國會|election|midterm|congress|senate|house majority'),
]
POLICY_LABELS={'suspended_or_disputed':'暫緩／訴訟或爭議','proposal':'提案或政策預期','campaign_promise':'競選承諾',
 'effective_claim':'報導聲稱生效，待核對原始法規','legislative_claim':'報導聲稱通過，待核對法規與生效日',
 'election_report':'選舉／國會變化報導，不等於政策生效','unclear':'政策階段待核對','none':'非政策事件'}
TOPIC_PATTERNS=[
 ('election_policy','美國選舉與政策',r'大選|選舉|國會|election|midterm|congress|senate|campaign|tariff|關稅|出口管制|export control|sanction'),
 ('asia_fx','亞洲匯率與資金',r'台幣|新臺幣|新台幣|日圓|日元|韓元|人民幣|匯率|美元|yen|won\b|yuan|taiwan dollar|currenc|foreign exchange|USD/'),
 ('us_tech','美股科技與AI投資',r'美股|那斯達克|納斯達克|費半|半導體|\bAI\b|人工智慧|資料中心|nasdaq|semiconductor|chip|capex|data.cent'),
 ('asia_equities','日韓股市與同業',r'日股|韓股|日經|東證|nikkei|kospi|kosdaq|韓國股|日本股|korea.+stocks|japan.+stocks'),
 ('rates_liquidity','利率・美元流動性',r'Fed\b|FOMC|聯準會|利率|降息|升息|殖利率|公債|央行|yield|treasur|interest rate|monetary|Bank of Japan|ECB'),
 ('energy_logistics','能源・地緣與物流',r'原油|石油|能源|航運|運費|地緣|戰爭|oil\b|energy|shipping|freight|war\b|strait'),
]

def classify_event(event,cutoff):
 at=dt(cutoff)
 try:
  if dt(event['available_at'])>at or dt(event['published_at'])>at:return None
 except (KeyError,ValueError,TypeError):return None
 text=str(event.get('title',''))+' '+str(event.get('excerpt',''))
 tags=[{'key':key,'label':label} for key,label,pattern in TOPIC_PATTERNS if re.search(pattern,text,re.I)]
 if not tags:return None
 policy='none'
 if any(t['key']=='election_policy' for t in tags):
  policy=next((k for k,p in POLICY_PATTERNS if re.search(p,text,re.I)),'unclear')
  # A text match alone NEVER verifies a legal status or election result.
 host=(urlsplit(str(event.get('url',''))).hostname or '').lower()
 official=bool(event.get('official_feed')) and host in {'www.federalreserve.gov','www.ecb.europa.eu','www.boj.or.jp','www.cbc.gov.tw'}
 evidence=event.get('excerpt') or event.get('title','')
 return {**event,'topics':tags,'policy_stage':policy,'policy_stage_label':POLICY_LABELS[policy],
  'evidence_excerpt':evidence[:280],'official_source':official,'legal_effect_verified':False,
  'effective_at':None,'certainty':'來源報導／文件表述；分類與傳導是規則假設',
  'next_check':'原始文件、公布及生效日期、司法／行政程序、公司具體曝險' if policy!='none' else '核對市場完整日資料及公司營運證據',
  'event_group':sorted(t['key'] for t in tags)[0]}

def expected_day(spec,cutoff):
 local=dt(cutoff).astimezone(__import__('zoneinfo').ZoneInfo(spec['timezone']))
 day=local.date()
 # Yield series are published with a lag. Do not pretend real-time Treasury quotes.
 if spec['kind']=='yield':day-=timedelta(days=1)
 for _ in range(12):
  if day.weekday()<5 and close_boundary(day.isoformat(),spec)<=dt(cutoff):return day.isoformat()
  day-=timedelta(days=1)
 return None

def summarize_market(spec,cutoff):
 at=dt(cutoff);bars=[];rejected=0
 for r in spec.get('bars',[]):
  try:
   v=finite(r.get('value'))
   if v is None or (v<=0 and spec['kind']!='yield'):raise ValueError('invalid_value')
   if dt(r['available_at'])>at or dt(r['observed_at'])>at:raise ValueError('future_observation')
   if close_boundary(r['date'],spec)>at:raise ValueError('incomplete_session')
   if dt(r['date']+'T00:00:00+00:00').weekday()>=5:raise ValueError('weekend')
   bars.append(r)
  except (ValueError,TypeError,KeyError):rejected+=1
 bars=sorted({r['date']:r for r in bars}.values(),key=lambda x:x['date'])
 base={k:v for k,v in spec.items() if k!='bars'}
 base.update(status='missing',usable=False,price_date=None,last=None,change_1d_pct=None,change_5d_pct=None,
    change_20d_pct=None,change_1d_bp=None,local_appreciation_1d_pct=None,local_appreciation_5d_pct=None,
    sample_count=len(bars),rejected_records=rejected,bars=bars[-61:],expected_session_note='名目收盤＋45分鐘；未核對各國臨時休市／假日，日期差異需人工檢查')
 if not bars:return base
 last=bars[-1];expect=expected_day(spec,cutoff);status='recent' if expect and last['date']>=expect else 'lagged'
 age=(at-dt(last['observed_at'])).total_seconds()/3600
 if age>72 or (at.date()-dt(last['date']+'T00:00:00+00:00').date()).days>5:status='stale'
 base.update(status=status,usable=status=='recent' and len(bars)>=6,price_date=last['date'],last=last['value'],
   expected_date=expect,observed_at=last['observed_at'],session_complete_after=last['session_complete_after'],
   age_hours=round(age,1))
 for n,name in [(1,'change_1d_pct'),(5,'change_5d_pct'),(20,'change_20d_pct')]:
  if len(bars)>n and bars[-1-n]['value']!=0:
   base[name]=round((last['value']/bars[-1-n]['value']-1)*100,4)
   if spec['kind']=='fx' and n in (1,5):base[f'local_appreciation_{n}d_pct']=round((bars[-1-n]['value']/last['value']-1)*100,4)
 if spec['kind']=='yield':
  base['change_1d_bp']=round((last['value']-bars[-2]['value'])*100,3) if len(bars)>1 else None
  base['change_5d_bp']=round((last['value']-bars[-6]['value'])*100,3) if len(bars)>5 else None
  base['change_1d_pct']=base['change_5d_pct']=base['change_20d_pct']=None
  base['unit']='percent_yield'
 elif spec['kind']=='fx':
  x=base['local_appreciation_1d_pct'];c=spec['local_currency']
  base['direction_label']=f'{c}兌美元'+('升值' if x is not None and x>0.01 else '貶值' if x is not None and x<-0.01 else '近持平' if x is not None else '缺比較值')
  base['unit']='local_currency_per_USD'
 else:base['unit']='index_points' if spec['kind'] in ('equity','volatility','dollar_index') else 'provider_quoted_futures_price'
 return base

def currency_crosses(markets):
 lookup={x['key']:x for x in markets};twd=lookup.get('USDTWD');out=[]
 for code in ['JPY','KRW','CNY']:
  other=lookup.get('USD'+code)
  if not twd or not other:continue
  a={x['date']:x['value'] for x in twd['bars']};b={x['date']:x['value'] for x in other['bars']}
  days=sorted(a.keys()&b.keys())
  if len(days)<6:out.append({'other_currency':code,'status':'insufficient','reason':'共同日頻窗口不足6筆'});continue
  d,prev=days[-1],days[-6];cross=a[d]/b[d];old=a[prev]/b[prev]
  move=(old/cross-1)*100
  out.append({'other_currency':code,'status':'recent' if twd['usable'] and other['usable'] and d==twd['price_date']==other['price_date'] else 'lagged',
   'date':d,'window_start':prev,'twd_per_local':round(cross,6),'twd_appreciation_5d_pct':round(move,4),
   'formula':'TWD/外幣 = (TWD/USD)/(外幣/USD)，TWD升值率 = 舊交叉匯率/新交叉匯率−1',
   'interpretation':'TWD相對'+code+('升值' if move>0 else '貶值')+'；競爭與進口成本影響需核對產品、報價幣別與避險'})
 return out

def risk_regime(markets):
 usable={x['key']:x for x in markets if x['usable']};regions={};alerts=[]
 for region,keys in [('US',['NASDAQ','SOX','SPX']),('JP',['NIKKEI']),('KR',['KOSPI','KOSDAQ']),('HK',['HSI']),('EU',['STOXX50'])]:
  present=[usable[k] for k in keys if k in usable]
  if not present:continue
  hit=[x for x in present if (x['change_1d_pct'] is not None and x['change_1d_pct']<=-3) or (x['change_5d_pct'] is not None and x['change_5d_pct']<=-6)]
  regions[region]=bool(hit)
  if hit:alerts.append({'kind':'regional_equity_stress','region':region,'instruments':[x['key'] for x in hit],
    'reason':'日跌幅≤−3%或5個觀測期≤−6%；同區指數只算一組，不重複累加'})
 vix=usable.get('VIX');vix_stress=bool(vix and (vix['last']>=30 or (vix['change_1d_pct'] or 0)>=20))
 if vix_stress:alerts.append({'kind':'vix','instruments':['VIX'],'reason':'VIX≥30或單次變動≥20%；不是跌底機率'})
 fx_shocks=[x for x in usable.values() if x['kind']=='fx' and ((x.get('local_appreciation_1d_pct') is not None and abs(x['local_appreciation_1d_pct'])>=1.5) or (x.get('local_appreciation_5d_pct') is not None and abs(x['local_appreciation_5d_pct'])>=3))]
 if fx_shocks:alerts.append({'kind':'fx_volatility','instruments':[x['key'] for x in fx_shocks],'reason':'本幣單期升貶絕對值≥1.5%或5期≥3%；先降曝險不確定性，不能推論公司EPS淨方向'})
 rate=usable.get('US10Y');rate_jump=bool(rate and rate.get('change_5d_bp') is not None and abs(rate['change_5d_bp'])>=30)
 if rate_jump:alerts.append({'kind':'rate_shock','instruments':['US10Y'],'reason':'10年殖利率5觀測期變化絕對值≥30bp；利率下跌也可能是避險，需拆解原因'})
 oil=usable.get('WTI');oil_jump=bool(oil and oil.get('change_5d_pct') is not None and abs(oil['change_5d_pct'])>=10)
 if oil_jump:alerts.append({'kind':'oil_shock','instruments':['WTI'],'reason':'原油近月5期變化絕對值≥10%；含換月與供需歧義，不當公司直接獲利預測'})
 macro_shock=bool(fx_shocks or rate_jump or oil_jump)
 nstress=sum(regions.values());valid=len(regions)>=3 and 'US' in regions and bool(set(regions)&{'JP','KR'})
 if not valid:code='insufficient';fraction=None;label='跨市場資料不足，不宣稱全球平穩'
 elif nstress>=2 or (nstress>=1 and vix_stress):code='cross_market_stress';fraction=.5;label='跨市場同步風險升高'
 elif nstress or vix_stress or macro_shock:code='elevated';fraction=.75;label='局部壓力，降低新增風險假設'
 else:code='watch';fraction=1.;label='目前未觸發急跌規則，不等於安全買點'
 return {'code':code,'label':label,'new_risk_multiplier':fraction,'coverage_regions':list(regions),
  'stressed_regions':[k for k,v in regions.items() if v],'signals':alerts,'coverage_valid':valid,
  'calibrated':False,'bottom_probability':None,'expected_return':None,'changes_original_scores':False,
  'rules':'固定研究門檻：日≤−3%、5期≤−6%，同區只算一次；跨區≥2或一區＋VIX風險時0.5，單區或匯率／利率／原油急變0.75，未觸發1.0。缺核心市場時不產生乘數。',
  'limitation':'比較最近可得完整收盤，不是同時成交、已證明因果或最佳化參數。不得據此自動清倉或攤平。'}

CHANNELS={
 'us_tech':('美國科技→台灣供應鏈','美股科技／半導體價格與投資展望 → 評價與資本支出不確定性 → 台灣電子供應鏈研究',
  '未證明訂單取消；核對客戶與產品、收入占比、交付時程及原始財測。','半導體|電子|電腦|通信|科技'),
 'asia_equities':('日韓股市→同業與區域資金','日韓同業價格變化 → 風險偏好／區域資金／替代競爭 → 台股同業估值與波動',
  '同跌可能源自共同因子；不能當成日本或韓國下跌造成台股下跌的證明。','半導體|電子|電腦|通信|科技|金融'),
 'asia_fx':('匯率→營收、成本與避險','幣別相對美元與新台幣交叉變動 → 外幣收入折算、進口成本、匯兌與避險損益 → 淨效果待公司曝險核對',
  '台幣升值對美元收入與美元成本可互抵；台幣相對日韓升貶也要同日期比較。',''),
 'election_policy':('選舉→政策程序→企業曝險','選舉／國會結果 → 草案、立法、行政或司法程序 → 實際生效條文 → 訂單、成本、補助與資本支出',
  '選舉結果不是政策生效；不依政黨名稱自動給股票正負分。',''),
 'rates_liquidity':('利率→折現與資金','央行／通膨訊號 → 利率與美元融資條件 → 折現率、借款成本、金融資產評價與風險偏好',
  '利率下降可能是寬鬆也可能是衰退避險；金融股利差、債券及信用成本須拆開。',''),
 'energy_logistics':('地緣與能源→供應、成本及需求','能源／運輸中斷 → 原料、燃料與運費 → 毛利、需求與通膨 → 個別產業方向可能相反',
  '航運、航空、塑化與電子影響不同；需要採購合約、報價與成本曝險。',''),
}

def pathways(events,markets):
 out=[];quotes={x['key']:x for x in markets}
 instruments={'us_tech':['NASDAQ','SOX'],'asia_equities':['NIKKEI','KOSPI'],
  'asia_fx':['USDTWD','USDJPY','USDKRW','USDCNY'],'election_policy':[],
  'rates_liquidity':['US10Y','US2Y','DXY','VIX'],'energy_logistics':['WTI','GOLD']}
 for key,(title,chain,gap,_) in CHANNELS.items():
  related=[e for e in events if key in {t['key'] for t in e['topics']}]
  relatedquotes=[quotes[k] for k in instruments[key] if k in quotes and quotes[k]['last'] is not None]
  out.append({'key':key,'title':title,'chain':chain,'basis':'研究假設，非因果證明','gap':gap,
   'event_ids':[e['id'] for e in related[:5]],'quote_keys':[q['key'] for q in relatedquotes],
   'evidence_status':'有報導與數據線索' if related and relatedquotes else '只有報導線索' if related else '只有價量線索' if relatedquotes else '未取得證據',
   'independent_confirmation_count':None})
 return out

def stock_exposures(stocks,events,markets,cutoff,profiles=None):
 profiles=profiles or {};out=[]
 for stock in stocks:
  sector=str(stock.get('sector') or '');name=stock.get('name',stock['symbol']);rows=[]
  for key,(title,chain,gap,sectorpat) in CHANNELS.items():
   ids=[e['id'] for e in events if key in {t['key'] for t in e['topics']}]
   if sectorpat and not re.search(sectorpat,sector):continue
   rows.append({'key':key,'title':title,'relation':'產業／市場假設，未確認公司量化曝險',
    'basis':'sector_hypothesis' if sectorpat else 'market_background','mechanism':chain,'missing':gap,
    'event_ids':ids[:3],'net_company_direction':'unknown','changes_score':False})
  evidence=[]
  for record in profiles.get(stock['symbol'],[]):
   try:
    text=str(record.get('claim','')).strip();source=str(record.get('source_url',''));host=urlsplit(source).hostname
    if not text or not host or urlsplit(source).scheme!='https':continue
    if dt(record['available_at'])>dt(cutoff) or dt(record['published_at'])>dt(cutoff):continue
    if not record.get('reviewed'):continue
    evidence.append(record)
   except (ValueError,KeyError,TypeError):continue
  out.append({'symbol':stock['symbol'],'name':name,'sector':sector or '未分類','channels':rows,
    'reviewed_exposure_documents':evidence,'measured_net_exposure':None,
    'needs':['營收／成本幣別及占比','客戶與供應鏈關係的原始證據','避險政策與認列期間','政策生效及公司適用範圍'],
    'warning':'未取得公司數據，不計算EPS衝擊或報酬機率；不把市場新聞逐篇重複扣公司分。'})
 return out

def assemble(quotes,events,stocks,cutoff,profiles=None):
 markets=[summarize_market(x,cutoff) for x in quotes]
 classified=[r for e in events if (r:=classify_event(e,cutoff))]
 risk=risk_regime(markets)
 return {'generated_at':cutoff,'markets':markets,'currency_crosses':currency_crosses(markets),'events':classified,
   'policy_events':[e for e in classified if e['policy_stage']!='none'],
   'risk':risk,'pathways':pathways(classified,markets),
   'stock_exposures':stock_exposures(stocks,classified,markets,cutoff,profiles),
   'coverage':{'market_total':len(markets),'market_usable':sum(m['usable'] for m in markets),
      'events':len(classified),'policy_events':sum(e['policy_stage']!='none' for e in classified)},
   'qwen_calls':0,'model':'CPU可解釋規則，未訓練或校準','changes_saved_orders':False,
   'changes_original_scores':False,'point_in_time_note':'本次取得的外部資料只屬於本次研究；不回填原快照，不可當歷史預知資料。'}
