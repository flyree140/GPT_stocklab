"""CPU-first six-factor evidence. Missing != neutral; no automatic buy score.
All observations must carry availability timestamps. Numbers use native units:
percent ratios = percentage points; price/volume = original units.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from math import sqrt,isfinite
from statistics import mean,pstdev
from .schema import timestamp,digest

FACTORS=('news','social','fundamental','technical','flow','macro_policy')
LABELS=dict(news='新聞與公司政策',social='社群關注與情緒',fundamental='基本・財務・估值',technical='K線・技術・量價',flow='法人・籌碼・流動性',macro_policy='總經・產業・法規')

def num(v):
    if isinstance(v,bool):return None
    try:
        x=float(v);return x if isfinite(x) else None
    except (TypeError,ValueError):return None

def safe_bars(rows,cutoff):
    cut=timestamp(cutoff);latest={};rejected=[]
    for r in rows:
        try:
            day=datetime.fromisoformat(r['date']).date()
            avail=r.get('available_at') or (day.isoformat()+'T14:30:00+08:00')
            if timestamp(avail)>cut:raise ValueError('future/unclosed bar')
            if day.weekday()>=5:raise ValueError('weekend')
            o,h,l,c,v=[num(r.get(k)) for k in ('open','high','low','close','volume')]
            if any(x is None for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<=0:raise ValueError('bad price/volume')
            if l>min(o,c) or h<max(o,c) or h<l:raise ValueError('OHLC inconsistency')
            normalized={k:r[k] for k in ('date','open','high','low','close','volume')};normalized['available_at']=avail
            if day.isoformat() in latest and latest[day.isoformat()]!=normalized:raise ValueError('conflicting duplicate date')
            latest[day.isoformat()]=normalized
        except (KeyError,ValueError,TypeError) as e:rejected.append({'date':r.get('date'),'reason':str(e)})
    return [latest[k] for k in sorted(latest)],rejected

def technical(rows,cutoff):
    bars,bad=safe_bars(rows,cutoff)
    if len(bars)<2:return {'status':'missing','values':{},'missing':['至少2筆有效、已收盤OHLCV'],'rejected':bad}
    c=[float(r['close']) for r in bars]; v=[float(r['volume']) for r in bars]; e12=e26=signal=None;k=d=50.;ag=al=None;tr=[];hist=[];kd=[];rsi=[]
    gains=[];losses=[]
    for i,row in enumerate(bars):
        p=c[i-1] if i else c[i];diff=c[i]-p
        if i:gains.append(max(0,diff));losses.append(max(0,-diff))
        if len(gains)>=14:
            if ag is None:ag=mean(gains[:14]);al=mean(losses[:14])
            else:ag=(ag*13+gains[-1])/14;al=(al*13+losses[-1])/14
        rsi.append(None if ag is None else 100. if al==0 and ag>0 else 50. if al==0 else 100-100/(1+ag/al))
        tr.append(max(float(row['high'])-float(row['low']),abs(float(row['high'])-p),abs(float(row['low'])-p)))
        e12=c[i] if e12 is None else e12*11/13+c[i]*2/13
        e26=c[i] if e26 is None else e26*25/27+c[i]*2/27
        macd=e12-e26;signal=macd if signal is None else .8*signal+.2*macd;hist.append(macd-signal)
        sub=bars[max(0,i-8):i+1];hi=max(float(x['high']) for x in sub);lo=min(float(x['low']) for x in sub)
        rsv=50 if hi==lo else (c[i]-lo)/(hi-lo)*100;k=2*k/3+rsv/3;d=2*d/3+k/3;kd.append((k,d))
    n=len(c);ma={f'ma{x}':mean(c[-x:]) if n>=x else None for x in (5,20,60)}
    prev20=v[-21:-1] if n>=21 else []
    ret=[c[i]/c[i-1]-1 for i in range(max(1,n-20),n)]
    values={**ma,'close':c[-1],'rsi14':rsi[-1],'atr14':mean(tr[-14:]) if n>=14 else None,
      'volume':v[-1],'volume_ratio_previous20':v[-1]/mean(prev20) if prev20 and mean(prev20)>0 else None,
      'macd':macd if n>=26 else None,'macd_hist':hist[-1] if n>=35 else None,
      'macd_new_cross_up':bool(hist[-2]<=0<hist[-1]) if n>=35 else None,
      'k9':k if n>=9 else None,'d9':d if n>=9 else None,
      'kd_new_cross_up':bool(kd[-2][0]<=kd[-2][1] and k>d) if n>=10 else None,
      'volatility20_pct':pstdev(ret)*sqrt(252)*100 if n>=21 else None,
      'support20':min(float(x['low']) for x in bars[-20:]) if n>=20 else None,
      'resistance20':max(float(x['high']) for x in bars[-20:]) if n>=20 else None,
      'return20_pct':(c[-1]/c[-21]-1)*100 if n>=21 else None}
    return {'status':'available' if n>=60 else 'partial','available_at':bars[-1]['available_at'],
      'quote_date':bars[-1]['date'],'bar_count':n,'values':values,
      'missing':[key for key,val in values.items() if val is None],'rejected':bad,
      'notes':['以有效OHLCV計算，不從圖像猜價格。','量比使用前20筆、不含當日的均量。','週末與價量結構檢查不等於已取得完整交易日曆認證。']}

FACT_KEYS={
 'fundamental': {'revenue_yoy_pct','eps_ttm','gross_margin_pct','operating_margin_pct','roe_pct','ocf','net_income','debt_to_equity_pct','pe','pb','dividend_yield_pct','net_interest_margin_pct','credit_cost_pct','npl_ratio_pct'},
 'flow': {'foreign_net_shares','trust_net_shares','dealer_net_shares','margin_balance','short_balance','turnover_value','spread_bps'},
 'macro_policy': {'policy_rate_pct','usd_twd','industry_growth_pct','policy_effective_date','policy_status','policy_summary'}
}

def point_facts(facts,kind,cutoff):
    accepted={};provenance={};rejected=[]
    for f in facts:
        try:
            if f.get('factor')!=kind:continue
            name=f['name']
            if name not in FACT_KEYS[kind]:raise ValueError('unknown metric')
            if timestamp(f['available_at'])>timestamp(cutoff):raise ValueError('future release')
            if not f.get('source'):raise ValueError('missing source')
            if name.endswith('_date') or name in ('policy_status','policy_summary'):value=str(f['value'])
            else:
                value=num(f['value'])
                if value is None:raise ValueError('non-finite metric')
            if name not in provenance or timestamp(f['available_at'])>timestamp(provenance[name]['available_at']):
                accepted[name]=value;provenance[name]={k:f.get(k) for k in ('available_at','period','source','unit')}
        except (KeyError,ValueError,TypeError) as e:rejected.append({'name':f.get('name'),'reason':str(e)})
    required={'fundamental':['revenue_yoy_pct','eps_ttm','roe_pct','ocf','pe','pb'],
              'flow':['foreign_net_shares','trust_net_shares','dealer_net_shares'],
              'macro_policy':['policy_rate_pct','usd_twd']}[kind]
    missing=[k for k in required if k not in accepted]
    return {'status':'missing' if not accepted else 'partial' if missing else 'available',
      'values':accepted,'provenance':provenance,'missing':missing,'rejected':rejected,
      'notes':['必須以首次可用／公布日期入列，不以財報季度末冒充公開日。','資料缺值不填成中性分；金融業不硬套製造業毛利率。']}

def six_factors(stock,cutoff,social_summary=None,extra_facts=None):
    events=[]
    for e in stock.get('news',[]):
        try:
            if timestamp(e['available_at'])<=timestamp(cutoff) and timestamp(e['published_at'])<=timestamp(cutoff):events.append(e)
        except (ValueError,TypeError,KeyError):continue
    news={'status':'partial' if events else 'missing','values':{'events':len(events),'verified_events':sum(bool(e.get('source_assessment',{}).get('verified')) for e in events)},
          'missing':[] if events else ['沒有時間可核對的新聞'],
          'notes':['標題、公司公告與社群傳聞分層；公司政策記錄承諾、時程、資本支出及里程碑。']}
    facts=extra_facts or []
    result={'news':news,'social':social_summary or {'status':'missing','values':{},'missing':['未連接有權使用的社群樣本']},
            'technical':technical(stock.get('candles',[]),cutoff)}
    for factor in FACT_KEYS:result[factor]=point_facts(facts,factor,cutoff)
    return {k:{'label':LABELS[k],**result[k]} for k in FACTORS}
