"""Conditional research labels, not recommendations tailored to a person."""
from __future__ import annotations
from .events import aggregate
from .common import number, clamp
WEIGHTS={'news':.30,'fundamental':.20,'technical':.20,'flow':.12,'valuation':.10,'market':.08}
NAMES={'news':'新聞事件','fundamental':'基本面','technical':'技術面','flow':'法人籌碼','valuation':'估值','market':'大盤'}
def decide(stock, as_of, weights=None):
    weights=weights or WEIGHTS
    if abs(sum(weights.values())-1)>1e-8: raise ValueError('Weights must sum to 1')
    bars=stock.get('candles',[]);last=bars[-1] if bars else {};events=stock.get('news',[])
    news=aggregate(events);facts=stock.get('facts',{});values={};notes={};positives=[];risks=[]
    values['news']=news['score'];notes['news']=news['explanation']
    tech=None
    if last.get('ma60') is not None:
        tech=50
        for key,weight in [('ma20',12),('ma60',12)]:
            above=last['close']>last[key];tech+=weight if above else -weight
            (positives if above else risks).append(('站上' if above else '跌破')+('月線' if key=='ma20' else '季線'))
        if last.get('histogram') is not None:tech+=8 if last['histogram']>0 else -8
        rsi=last.get('rsi')
        if rsi is not None:
            if rsi>75:tech-=8;risks.append('RSI 過熱，避免只看利多追價')
            elif rsi<30:tech-=5;risks.append('超賣不代表已止跌')
    values['technical']=tech;notes['technical']='以當日以前日 K 計算；不足 60 根不給趨勢分'
    rev=number(facts.get('revenue_yoy')); eps=number(facts.get('eps'))
    # A single monthly revenue observation is not full financial coverage.
    values['fundamental']=clamp(50+rev*.6,15,85) if rev is not None else None
    notes['fundamental']=f'月營收年增 {rev:+.1f}%；尚未涵蓋資產負債、自由現金流與完整季報' if rev is not None else '缺可用財報／月營收；不以中立分冒充已評估'
    if rev is not None:(positives if rev>0 else risks).append(f'月營收年增 {rev:+.1f}%（不等於淨利成長）')
    flow=number(facts.get('institutional_net')); volume=number(last.get('volume'))
    values['flow']=clamp(50+(flow/volume)*100,15,85) if flow is not None and volume and volume>0 else None
    notes['flow']='法人淨買賣股數／當日成交股數；單日流向不等於長期籌碼集中'
    peer=number(facts.get('pe_peer_percentile'))
    values['valuation']=clamp(90-peer*.8) if peer is not None else None
    notes['valuation']='同產業正本益比橫斷面位置；成長不同不能只憑便宜買入' if peer is not None else '缺同業可比估值；不套用所有產業通用 PE 門檻'
    values['market']=number(stock.get('market_score'));notes['market']='以 0050 相對月線與季線判定；不是景氣預測'
    missing=[NAMES[k] for k,v in values.items() if v is None]
    covered=sum(weights[k] for k,v in values.items() if v is not None)
    # A revenue-only basic factor counts half coverage, avoiding false completeness.
    completeness=covered-(weights['fundamental']*.5 if rev is not None else 0)
    contributions={k:round((v-50)*weights[k],2) if v is not None else 0 for k,v in values.items()}
    risk=0
    if last.get('atr') and last.get('close'):
        if last['atr']/last['close']>.05:risk+=8;risks.append('ATR 波動超過股價 5%')
    stale=not bars or (as_of>last.get('date','') and working_gap(last.get('date'),as_of)>2)
    if stale:risk+=12;risks.append('價格過期或不存在，不產生買進標籤')
    if any(e.get('category')=='disruption' and e.get('impact_score',0)<-15 for e in events):risk+=8;risks.append('存在未釐清的營運中斷／法遵事件')
    missing_penalty=(1-completeness)*12
    score=round(clamp(50+sum(contributions.values())-risk-missing_penalty),1)
    material_events=[e for e in events if e.get('included') and e.get('category') in ('earnings','orders') and e.get('impact_score',0)>15]
    # Core factors and substantial evidence are required before a positive label.
    strong_evidence=any(e.get('source_assessment',{}).get('verified') for e in material_events)
    gated=stale or completeness<.60 or tech is None or rev is None
    if stock.get('kind')=='etf':
        label='ETF 資料不足，僅追蹤';code='insufficient';risks.append('ETF 須評估成分曝險、折溢價、追蹤差異與費率；不套公司 PE')
    elif gated:label='資料不足，暫不建議進場';code='insufficient'
    elif score>=68 and strong_evidence and tech>=65 and values['valuation'] is not None:
        label='條件式偏多，可研究分批';code='conditional_buy'
    elif score<40 or risk>=16:label='風險偏高，暫不進場';code='avoid'
    elif tech>=65 and score>=54:label='列入候選，等待確認';code='watch'
    else:label='觀望，不急著買入';code='neutral'
    if not material_events:risks.append('缺可連結到獲利的正向重大事件；不因話題熱度追價')
    if missing:risks.append('尚未評估：'+'、'.join(missing))
    trigger=material_events[0]['confirmation'] if material_events else (events[0]['confirmation'] if events else '新增可驗證的公司營運資訊')
    invalidation='價格跌破月線並伴隨基本面惡化時，重新評估；不要機械加碼'
    plan={}
    if last.get('atr') and last.get('support') and last.get('resistance'):
        c=last['close'];a=last['atr'];stop=max(.01,c-2*a);reward=max(0,last['resistance']-c)
        plan={'reference_price':c,'reference_date':last['date'],'watch_zone':[round(min(c,last['ma20']),2),round(c,2)],
              'stop_reference':round(stop,2),'resistance':last['resistance'],
              'reward_risk':round(reward/(c-stop),2),'assumption':'觀察區間與 ATR 是風險假設，不是預測目標或委託單'}
    return {'label':label,'code':code,'score':score,'score_meaning':'研究規則分；不是勝率或預期報酬',
            'coverage':round(completeness*100,1),'factors':[{'key':k,'name':NAMES[k],'score':v,'weight':weights[k],
            'contribution':contributions[k],'note':notes[k]} for k,v in values.items()],
            'risk_deduction':risk,'missing_deduction':round(missing_penalty,2),'base':50,
            'reasons':positives[:4],'risks':risks[:6],'next_action':trigger,
            'new_investor':'尚未通過條件前，不因單則新聞買入' if code!='conditional_buy' else '先用模擬交易檢驗；等價格與營運條件同時成立再評估',
            'holder':'核對持有理由與停損條件是否仍成立，避免僅因促銷或會議新聞加碼',
            'confirmation':trigger,'invalidation':invalidation,'plan':plan}

def working_gap(before,after):
    from datetime import date,timedelta
    if not before:return 999
    a=date.fromisoformat(before[:10]);b=date.fromisoformat(after[:10]);n=0
    while a<b:a+=timedelta(days=1);n+=int(a.weekday()<5)
    return n
