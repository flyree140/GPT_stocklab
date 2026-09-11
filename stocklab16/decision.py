"""Individual stock diagnostics. No missing value is fabricated as a good factor."""
from __future__ import annotations
from datetime import date,timedelta
from .events import aggregate,issuer_kind
from .common import number,clamp
WEIGHTS={'news':.30,'fundamental':.20,'technical':.20,'flow':.12,'valuation':.10,'market':.08}
NAMES={'news':'新聞事件','fundamental':'基本面','technical':'技術面','flow':'法人籌碼','valuation':'估值','market':'大盤'}

def fmt(x,d=2):return f'{x:,.{d}f}' if x is not None else '未取得'
def working_gap(before,after):
    if not before:return 999
    a=date.fromisoformat(before[:10]);b=date.fromisoformat(after[:10]);n=0
    while a<b:a+=timedelta(days=1);n+=int(a.weekday()<5)
    return n

def technical_report(bars):
    r=bars[-1] if bars else {};prev=bars[-2] if len(bars)>1 else {}
    c=number(r.get('close'));ma20=number(r.get('ma20'));ma60=number(r.get('ma60'));rsi=number(r.get('rsi'))
    volumes=[number(b.get('volume')) for b in bars[-6:-1]]
    avg=sum(v for v in volumes if v is not None)/len(volumes) if len(volumes)==5 and all(v is not None for v in volumes) else None
    volume=number(r.get('volume'));vr=volume/avg if avg and volume is not None else None
    h,l,o=(number(r.get(k)) for k in ('high','low','open'))
    span=h-l if h is not None and l is not None else 0
    body=abs(c-o) if c is not None and o is not None else None
    upper=h-max(o,c) if body is not None and h is not None else None
    lower=min(o,c)-l if body is not None and l is not None else None
    pattern='沒有完整 OHLC'
    if body is not None and span>0:
        if body/span<=.1:pattern=f'十字／小實體：實體占日振幅 {body/span:.0%}，表示當日拉鋸，不單獨預測反轉'
        elif upper is not None and upper>2*body:pattern=f'上影線長：上影 {upper:.2f} 元、實體 {body:.2f} 元，檢查上檔壓力'
        elif lower is not None and lower>2*body:pattern=f'下影線長：下影 {lower:.2f} 元、實體 {body:.2f} 元，有承接但須次日確認'
        else:pattern=f'{"收紅" if c>o else "收低"}實體占日振幅 {body/span:.0%}；單根 K 線不是買賣結論'
    def cross(a,b):
        vals=[number(prev.get(a)),number(prev.get(b)),number(r.get(a)),number(r.get(b))]
        if any(x is None for x in vals):return None
        pa,pb,ca,cb=vals
        return 'golden' if pa<=pb and ca>cb else 'dead' if pa>=pb and ca<cb else 'above' if ca>cb else 'below'
    return {'as_of':r.get('date'),'close':c,'ma20':ma20,'ma60':ma60,
      'above_ma20':c>ma20 if c is not None and ma20 is not None else None,
      'above_ma60':c>ma60 if c is not None and ma60 is not None else None,
      'distance_ma20_pct':round((c/ma20-1)*100,2) if c is not None and ma20 else None,
      'rsi':rsi,'volume_ratio':round(vr,2) if vr is not None else None,
      'volume_reference':'當日成交量 ÷ 前五個交易日均量（不包含今天）',
      'kd_cross':cross('k','d'),'macd_cross':cross('macd','signal'),'candle_pattern':pattern,
      'ibs':round((c-l)/span,3) if span and c is not None else None}

def decide(stock,as_of,weights=None):
    weights=weights or WEIGHTS
    if abs(sum(weights.values())-1)>1e-8:raise ValueError('Weights must sum to 1')
    name=stock.get('name',stock.get('symbol','這檔股票'));kind=issuer_kind(stock)
    bars=[b for b in stock.get('candles',[]) if b.get('date','')<=as_of]
    last=bars[-1] if bars else {};techinfo=technical_report(bars);events=stock.get('news',[])
    news=aggregate(events);facts=dict(stock.get('facts',{}));notes={};values={};positives=[];risks=[]
    if str(facts.get('available_at',''))[:10]>as_of:facts={};risks.append('財務值晚於切點，已排除')
    values['news']=news['score'];notes['news']=news['explanation']
    c=techinfo['close'];tech=None
    if techinfo['ma20'] is not None and techinfo['ma60'] is not None and c is not None:
        tech=50
        for key,w,lab in [('ma20',12,'月線'),('ma60',12,'季線')]:
            m=techinfo[key];above=c>m;tech+=w if above else -w
            (positives if above else risks).append(f'收盤 {fmt(c)} {"高於" if above else "低於"}{lab} {fmt(m)} 元（{(c/m-1)*100:+.2f}%）')
        hist=number(last.get('histogram'))
        if hist is not None:tech+=8 if hist>0 else -8
        if techinfo['rsi'] is not None and techinfo['rsi']>75:
            tech-=8;risks.append(f'RSI {techinfo["rsi"]:.1f} 偏熱：利多不等於現在適合追價')
        elif techinfo['rsi'] is not None and techinfo['rsi']<30:
            tech-=5;risks.append(f'RSI {techinfo["rsi"]:.1f} 超賣：仍需止跌，不能用超賣當反彈保證')
    values['technical']=clamp(tech) if tech is not None else None
    notes['technical']=f'MA20 {fmt(techinfo["ma20"])}、MA60 {fmt(techinfo["ma60"])}、RSI {fmt(techinfo["rsi"],1)}；價量截至 {last.get("date","未取得")}'
    rev=number(facts.get('revenue_growth_reported'))
    basis=facts.get('revenue_growth_basis','期間未核對')
    if rev is None and number(facts.get('revenue_yoy')) is not None:
        rev=number(facts['revenue_yoy']);basis='舊欄位成長率，非已核對月營收'
    roe=number(facts.get('roe'));profit=number(facts.get('profit_growth'))
    if kind=='financial':
        components=[]
        if roe is not None:components.append(clamp(50+(roe-10)*2,15,85))
        if profit is not None:components.append(clamp(50+profit*.5,15,85))
        fundamental=sum(components)/len(components) if components else None
        notes['fundamental']=f'金融股：ROE {fmt(roe)}%、獲利成長 {fmt(profit)}%；未涵蓋信用成本與資本適足性。不用製造業毛利率。'
        fundamental_coverage=.5 if components else 0
    else:
        fundamental=clamp(50+rev*.6,15,85) if rev is not None else None
        notes['fundamental']=f'來源回報成長 {rev:+.1f}%（{basis}）；未完成現金流／資產負債分析' if rev is not None else '缺帶有比較期間的營運成長資料'
        fundamental_coverage=.5 if rev is not None else 0
        if rev is not None:(positives if rev>0 else risks).append(f'營運成長指標 {rev:+.1f}%（{basis}），不是淨利成長保證')
    values['fundamental']=fundamental
    flow=number(facts.get('institutional_net'));v=number(last.get('volume'))
    values['flow']=clamp(50+flow/v*100,15,85) if flow is not None and v and v>0 else None
    notes['flow']=f'法人合計 {fmt(flow,0)} 股／當日量 {fmt(v,0)} 股；{facts.get("flow_date","未標示日期")}' if flow is not None else '本次未取得帶日期的三大法人買賣超；不寫成買超支持'
    if flow is not None and facts.get('flow_date')!=last.get('date'):
        values['flow']=None;notes['flow']='法人資料日與價格日不同，暫不比較比例'
    peer=number(facts.get('pe_peer_percentile'));peer_n=number(facts.get('peer_count'),0)
    values['valuation']=clamp(90-peer*.8) if peer is not None and peer_n>=5 and kind!='financial' else None
    notes['valuation']=f'{facts.get("peer_sector",stock.get("sector","未分組"))} 可比正PE樣本 {int(peer_n)} 家；分位 {fmt(peer)}，不是便宜保證' if values['valuation'] is not None else ('金融股需結合 PB、ROE 與信用風險，尚未校準估值分' if kind=='financial' else '同產業至少5個正PE樣本才計分；不把少數跨產業股票混排')
    values['market']=number(stock.get('market_score'));notes['market']='0050與月線／季線的相對位置；不是景氣預測'
    covered=sum(weights[k] for k,v in values.items() if v is not None)
    completeness=covered-weights['fundamental']*(1-fundamental_coverage) if fundamental is not None else covered
    contrib={k:round((v-50)*weights[k],2) if v is not None else 0 for k,v in values.items()}
    risk=0;stale=not bars or working_gap(last.get('date'),as_of)>2
    if stale:risk+=12;risks.append(f'價格截至 {last.get("date","缺值")}，相對 {as_of} 已過期或沒有價格')
    atr=number(last.get('atr'))
    if atr and c and atr/c>.05:risk+=8;risks.append(f'ATR／股價＝{atr/c*100:.1f}%，模擬停損可能很寬')
    if any(e.get('included') and e.get('category')=='disruption' and e.get('impact_score',0)<-15 for e in events):risk+=8;risks.append('負向營運中斷／法遵事件尚未釐清')
    missing_penalty=(1-completeness)*12
    score=round(clamp(50+sum(contrib.values())-risk-missing_penalty),1)
    useful=sorted([e for e in events if e.get('included')],key=lambda e:abs(e.get('active_score',e.get('impact_score',0))),reverse=True)
    leading=useful[0] if useful else None
    verified=any(e.get('category') in ('monthly_revenue','reported_earnings','orders','company_guidance') and e.get('impact_score',0)>10 and e.get('source_assessment',{}).get('verified') for e in useful)
    plan={};rr=None
    support=number(last.get('support'));resistance=number(last.get('resistance'));ma20=techinfo['ma20']
    if c and atr and atr>0 and support and resistance and ma20:
        stop=max(.01,c-2*atr);reward=max(0,resistance-c);rr=reward/(c-stop) if stop<c else None
        ceiling=(resistance+1.5*stop)/2.5
        plan={'reference_price':c,'reference_date':last['date'],'watch_zone':[round(min(c,ma20),2),round(c,2)],
          'stop_reference':round(stop,2),'support':support,'resistance':resistance,'reward_risk':round(rr,2) if rr is not None else None,
          'research_max_entry':round(ceiling,2),'reward_risk_threshold':1.5,
          'formula':f'目前估計 ({resistance:.2f}−{c:.2f})÷({c:.2f}−{stop:.2f})；門檻1.5是假設值',
          'assumption':'固定現有2ATR停損與20日壓力的情境；壓力不是保證目標，未含成本、跳空或成交限制；非下單指令'}
    checks=[]
    def gate(key,label,status,evidence):checks.append({'key':key,'label':label,'status':status,'evidence':evidence})
    gate('fresh','價格新鮮度','fail' if stale else 'pass',f'價格日 {last.get("date","缺值")}；分析日 {as_of}')
    gate('trend','中期趨勢','missing' if tech is None else 'pass' if tech>=65 else 'fail',notes['technical'])
    gate('facts','基本面可用性','pass' if fundamental is not None else 'missing',notes['fundamental'])
    gate('valuation','可比估值','pass' if values['valuation'] is not None else 'missing',notes['valuation'])
    gate('reward','報酬／風險情境','missing' if rr is None else 'pass' if rr>=1.5 else 'fail',f'到20日壓力／2ATR風險＝{fmt(rr)}；研究門檻1.5（非回测最佳值）')
    gate('event','重大事件原始證據','pass' if verified else 'missing','原始重大事件已核對' if verified else '尚未有原始公告核驗；媒體標題不升格為已確認')
    if kind=='etf':code='insufficient';label='ETF：先檢查曝險與費用';heading=f'{name}不套用單一公司EPS評分';next_action='檢查成分集中、追蹤差異、費率與折溢價'
    elif stale or tech is None:
        code='insufficient';label='價格／趨勢資料不足';heading=f'{name}缺可用價格基準，不判定進場';next_action=f'更新截至 {as_of} 的至少60根有效日K，現有最後日為 {last.get("date","缺值")}'
    elif risk>=16 or score<40 or (tech<=34):
        code='avoid';label='偏弱：先等止跌';heading=f'{name}趨勢分 {tech:.0f}，不因單則利多接刀';next_action=f'先觀察是否重回月線 {fmt(ma20)} 元；{leading["invalidation"] if leading else "若繼續破低，停止進場假設"}'
    elif rr is not None and rr<1.5 and tech>=65:
        code='watch';label='技術偏多，但不追價';heading=f'{name}到壓力的報酬／風險僅 {rr:.2f}，低於1.5假設門檻';next_action=f'固定停損 {fmt(plan["stop_reference"])} 與壓力 {fmt(resistance)} 時，入場價須≤ {fmt(plan["research_max_entry"])} 才達1.5；只是情境，突破後要重算'
    elif fundamental is None:
        code='insufficient';label='先補獲利證據';heading=f'{name}技術分 {tech:.0f}，但缺金融本業／營運基準';next_action=(leading.get('action') if leading else notes['fundamental'])
    elif score>=68 and verified and tech>=65 and values['valuation'] is not None and rr is not None and rr>=1.5 and completeness>=.6:
        code='conditional_buy';label='條件式偏多：研究分批';heading=f'{name}趨勢、原始事件與估值關卡通過，先用試買檢驗';next_action=f'用 {fmt(c)} 收盤作為參考；下一交易日實际開盤不同，重新计算風險，不保證成交或獲利'
    elif tech>=65:
        code='watch';label='趨勢偏多：等待營運確認';heading=f'{name}站上月／季線；尚缺足夠基本與估值證據支持進場';next_action=leading.get('action') if leading else '補充原始公告與同業估值，不把量價強勢當成低估'
    else:
        code='neutral';label='震盪：等價格與事件一致';heading=f'{name}技術分 {tech:.0f}，新聞與價格尚未形成明確進場條件';next_action=f'觀察月線 {fmt(ma20)} 元是否站穩；'+(leading.get('confirmation') if leading else '等待新公司事件而非追逐舊標題')
    if leading:positives.append('最有影響事件：'+leading.get('summary',leading.get('title','')) if leading.get('impact_score',0)>0 else '主要追蹤：'+leading.get('summary',leading.get('title','')))
    if rr is not None and rr<1.5:risks.append(f'報酬／風險 {rr:.2f} 不達1.5研究假設；高新聞分也不能補掉價格風險')
    missing=[NAMES[k] for k,v in values.items() if v is None]
    if missing:risks.append('缺少資料：'+'、'.join(missing))
    holder=f'{name}持有者：目前收盤 {fmt(c)}、月線 {fmt(ma20)}；核對原持有理由是否仍成立，勿把新聞目標價當成保證。'
    if leading and leading.get('category')=='analyst_forecast':holder+=f' 檢查同年度預估是否被下修，而非只看 {name} EPS 絕對值。'
    if tech is not None and tech<50:holder+=' 價格偏弱時先做減碼／停損情境，不用攤平取代風控。'
    return {'version':'16.1','label':label,'code':code,'score':score,'score_meaning':'研究規則分；不是勝率或預期報酬',
      'coverage':round(completeness*100,1),'factors':[{'key':k,'name':NAMES[k],'score':v,'weight':weights[k],'contribution':contrib[k],'note':notes[k]} for k,v in values.items()],
      'risk_deduction':risk,'missing_deduction':round(missing_penalty,2),'base':50,'reasons':positives,'risks':risks,
      'next_action':next_action,'new_investor':heading,'holder':holder,
      'confirmation':leading.get('confirmation') if leading else '新增原始營運證據',
      'invalidation':leading.get('invalidation') if leading else f'失守月線 {fmt(ma20)} 或營運基準惡化時重做評估',
      'plan':plan,'checks':checks,'technical_diagnosis':techinfo,
      'leading_event_id':leading.get('id') if leading else None}
