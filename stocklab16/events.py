"""Evidence-linked news assessment, v16.1.
Scores describe a bounded research signal, not stock-return probabilities.
Missing EPS baselines must never be fabricated. Equal evidence can legitimately
produce equal scores; distinct wording alone must never change a score.
"""
from __future__ import annotations
import re, math
from .common import dt, number, clamp, VERSION
from .taxonomy import (RULES, BY_ID, LABELS as BASIC_LABELS, clean, sentences,
                       source_status, group_items)
LABELS={**BASIC_LABELS,'monthly_revenue':'已公布月營收',
        'analyst_forecast':'分析師預估修訂','reported_earnings':'已公布獲利',
        'company_guidance':'公司財測','margin_change':'毛利與利潤率'}
NUM=r'([+\-−]?\d[\d,]*(?:\.\d+)?)'
ENGINE='events-16.1.2'

def issuer_kind(meta):
    sector=str(meta.get('sector',''))
    if meta.get('kind')=='etf': return 'etf'
    if any(k in sector for k in ('金融','銀行','金控','保險')):return 'financial'
    return 'operating'

def issuer_relation(item,meta):
    text=clean(item.get('title'))+' '+clean(item.get('excerpt'))
    aliases=[meta.get('name','')]+list(meta.get('aliases',[]))
    if any(a and a.lower() in text.lower() for a in aliases):return 'direct'
    code=meta.get('symbol','').split('.')[0]
    # Explicit 5274-TW or (5274) is an issuer identifier; a price of 5274 isn't.
    if code and re.search(r'(?:[（(]'+re.escape(code)+r'(?:[)）]|[-.]TW(?:O)?\b)|\b'+re.escape(code)+r'[-.]TW(?:O)?\b)',text,re.I):return 'direct'
    return 'unconfirmed'

def categorize(item):
    text=clean(item.get('title'))+' '+clean(item.get('excerpt'))
    # Static profiles first. Subtypes precede broad "earnings" keywords.
    if re.search(BY_ID['profile'][1],text,re.I):return 'profile'
    if re.search(r'分析師|FactSet|Factset|共識|投顧|券商|大摩|高盛|目標價',text,re.I) and re.search(r'EPS|每股盈餘|預估|預測|目標價',text,re.I):return 'analyst_forecast'
    if re.search(r'(?:公司|管理層|董事長).{0,15}(?:財測|展望)|財測',text) and not re.search(r'分析師|Factset',text,re.I):return 'company_guidance'
    if re.search(r'月營收|\d{1,2}月.{0,6}營收',text):return 'monthly_revenue'
    if re.search(r'毛利率|淨利率|營益率',text):return 'margin_change'
    if re.search(r'(?:已公布|公布|公告|自結|財報).{0,20}(?:EPS|每股盈餘|淨利|獲利)|(?:季|年)報',text,re.I):return 'reported_earnings'
    for r in RULES:
        if re.search(r[1],text,re.I):return r[0]
    return 'unclear'

def extract_metrics(item):
    """Each parsed number retains a verbatim span and evidence ID."""
    specs=[
      ('eps_prior','上次 EPS 預估',r'(?:EPS|每股盈餘).{0,8}?(?:由|從|原(?:為|估))\s*'+NUM+r'\s*元?', '元'),
      ('eps','EPS 預估／披露值',r'(?:EPS|每股盈餘)\s*(?:[預预]估|預測|共識|中位數|上修|下修|為|至|達|約|最新|調整|估|自結|實際|\s)*'+NUM+r'\s*元','元'),
      ('target_prior','上次目標價',r'目標價.{0,6}?(?:由|從)\s*'+NUM+r'\s*元?','元'),
      ('target','報導目標價',r'目標價\s*(?:預估|預測|上修|下修|為|至|達|約|調整|從|\s)*'+NUM+r'\s*元','元'),
      ('revenue_yoy','營收年增率',r'(?:年增(?:率)?|年成長|年減|年衰退|同比(?:增長|成長|下降|下滑)?|較去年同期(?:成長|增加|下滑|減少))\s*(?:達|至|為|約|\s)*'+NUM+r'\s*[%％]','%'),
      ('revenue_mom','營收月增率',r'(?:月增(?:率)?|月減|環比(?:增長|成長|下降|下滑)?)\s*(?:達|至|為|約|\s)*'+NUM+r'\s*[%％]','%'),
      ('revenue_amount','營收金額',r'(?:月營收|營收)\s*(?:達|為|約|合計|\s)*'+NUM+r'\s*(億元|百萬元|萬元|元)',''),
      ('margin','毛利率',r'毛利率\s*(?:達|為|約|至|上升至|下滑至|\s)*'+NUM+r'\s*[%％]','%'),
      ('order_amount','合約／訂單金額',r'(?:訂單|合約|得標)(?:金額)?\s*(?:達|為|約|\s)*'+NUM+r'\s*(億元|萬元|元)',''),
    ]
    out={}
    for ev in sentences(item):
        text=ev['text']
        for key,label,pattern,unit in specs:
            if key in out:continue
            m=re.search(pattern,text,re.I)
            if not m:continue
            raw=m.group(1).replace(',','').replace('−','-');value=number(raw)
            if value is None:continue
            if key in ('revenue_yoy','revenue_mom') and re.search(r'年減|月減|年衰退|下滑|下降|減少',m.group(0)):value=-abs(value)
            u=unit or m.group(2)
            out[key]={'key':key,'label':label,'value':value,'unit':u,'quote':m.group(0),'evidence_id':ev['id']}
        # Parse "EPS由180元上修至194.98元" correctly: last value, not prior value.
        for key,term in [('eps',r'(?:EPS|每股盈餘)'),('target','目標價')]:
            m=re.search(term+r'.{0,12}?(?:由|從)\s*'+NUM+r'\s*元?\s*(?:上修|下修|調升|調降|調整|提高|降低)(?:為|至)\s*'+NUM+r'\s*元',text,re.I)
            if m:
                for k,g,lab in [(key+'_prior',1,'上次'+('EPS 預估' if key=='eps' else '目標價')),(key,2,'EPS 預估／披露值' if key=='eps' else '報導目標價')]:
                    out[k]={'key':k,'label':lab,'value':float(m.group(g).replace(',','')),'unit':'元','quote':m.group(0),'evidence_id':ev['id']}
    return out

def val(metrics,k):return metrics.get(k,{}).get('value')
def f(v,d=2):return f'{v:,.{d}f}'.rstrip('0').rstrip('.') if isinstance(v,(int,float)) else '未取得'
def signed(v):return f'{v:+.2f}'.rstrip('0').rstrip('.')

def validate_hint(hint,evidence):
    if not isinstance(hint,dict) or hint.get('category') not in LABELS:return False
    span=hint.get('evidence')
    return isinstance(span,str) and len(span.strip())>=3 and any(span in ev['text'] for ev in evidence)

def analyze(item,meta,cutoff,model_hint=None):
    cutoff=dt(cutoff);published=dt(item['published_at']);available=dt(item.get('available_at') or item['published_at'])
    if max(published,available)>cutoff:raise ValueError('Article was not available at cutoff')
    evidence=sentences(item);metrics=extract_metrics(item);cat=categorize(item);engine='可稽核數字擷取＋事件規則'
    if model_hint and validate_hint(model_hint,evidence):
        # The model cannot erase a specific actual/forecast distinction or static exclusion.
        if cat=='unclear':cat=model_hint['category']
        engine='Qwen 證據輔助＋數字規則'
    rel=issuer_relation(item,meta);kind=issuer_kind(meta);name=meta.get('name') or meta.get('symbol','公司')
    text=' '.join(e['text'] for e in evidence)
    rule=BY_ID.get(cat) or BY_ID.get('earnings') if cat in ('monthly_revenue','analyst_forecast','reported_earnings','company_guidance','margin_change') else BY_ID.get(cat)
    if rule:
        _,_,channel,chain,horizon,kpi,confirm,invalid,prior=rule
        chain=list(chain)
    else:
        channel='尚無可辨識營運變動';chain=[name+'出現報導','尚無可量化營運變動','不產生方向訊號'];horizon='下一份明確事件公告';kpi='公告主體與實際變動';confirm='先找新增事件';invalid='沒有新增公司事實';prior=0
    missing=[];derived=[];flags=[];basis='事件先驗，並非報酬率';increment='unquantified';action='';summary=''
    if cat=='monthly_revenue':
        yoy=val(metrics,'revenue_yoy');mom=val(metrics,'revenue_mom')
        month=re.search(r'(?<!\d)(\d{1,2})月',text);period=(month.group(1)+'月') if month else '本月'
        amount=metrics.get('revenue_amount')
        if yoy is not None:
            prior=math.copysign(min(60,10+12*math.log1p(abs(yoy)/10)),yoy) if yoy else 0
            increment='actual_change';basis=f'年增 {signed(yoy)}%：10 + 12×ln(1+|年增|/10)，上限60；負成長取負號'
            summary=f'{name}{period}營收年增 {signed(yoy)}%，這是營收規模的已披露變化，不是 EPS 成長率。'
            confirm=f'對照 {period} 原始月營收表，確認 {signed(yoy)}% 的基期與是否合併新業務'
            if abs(yoy)>100:flags.append('大幅年增：低基期／併購的拆解優先於單看成長百分比')
        else:
            prior=8 if re.search(r'創.{0,2}高|成長|增加',text) else -8 if re.search('下滑|衰退',text) else 0
            summary=f'{name}{period}的報導有營收變化，但缺可擷取年增率；尚不能比較成長幅度。'
            confirm=f'取得{name}{period}營收金額與去年同月基準'
            missing.append(f'{period}營收年增率及比較基準')
        if mom is not None:
            prior+=clamp(mom*.25,-8,8);basis+=f'；月增 {signed(mom)}% 追加 {clamp(mom*.25,-8,8):+.2f}'
        else:missing.append(f'{period}月增率未提供，無法排除季節性')
        if not amount:missing.append('營收絕對金額未提供，不能由百分比推算增加多少元')
        missing.append('未提供本期毛利與營業現金流，無法把營收增幅直接換成 EPS')
        chain=[f'{name} {period}年增 {signed(yoy)}%' if yoy is not None else f'{name}{period}營收披露',
               f'月增 {signed(mom)}%' if mom is not None else '先拆低基期、產品量價與合併範圍',
               '再用季報檢驗營益與現金流，不直接追價']
        kpi=f'{name}：下月營收是否延續、產品單價／出貨量、存貨天數與營業現金流'
        if kind=='financial':kpi=f'{name}：利息與手續費收入、備抵呆帳、信用成本、ROE；不套製造業毛利率'
        action=f'先把{name}列入營收追蹤，拿本月與前月、去年同月交叉核對；再與技術面進場關卡比較'
        invalid=f'{name}下一期營收無法延續，或增量來自併購／低基期而非同口徑需求；不能維持本次成長假設'
        horizon='下一次月營收公布；季報再檢驗獲利轉換'
    elif cat=='analyst_forecast':
        eps=val(metrics,'eps');old=val(metrics,'eps_prior');target=val(metrics,'target')
        up=bool(re.search(r'上修|調升|提高',text));down=bool(re.search(r'下修|調降|降低',text))
        prior=0
        if old is not None and eps is not None and old>0:
            revision=(eps/old-1)*100
            prior=clamp(revision*1.2,-45,45);increment='estimate_revision'
            derived.append({'label':'同一報導 EPS 修訂幅度','value':round(revision,2),'unit':'%','formula':f'({f(eps)} ÷ {f(old)} − 1) × 100','assumption':'新舊 EPS 必須為相同預測期間；僅報導內比較，不是已實現盈餘'})
            summary=f'{name}的分析師 EPS 預估由 {f(old)} 元改為 {f(eps)} 元，修訂 {signed(revision)}%；仍是預估，不是公司自結獲利。'
            basis=f'EPS 相對修訂 {signed(revision)}% × 1.2，上限±45；不使用 EPS 絕對高低比較公司'
        else:
            prior=14 if up and not down else -14 if down and not up else 0
            increment='direction_only' if prior else 'no_comparable_revision'
            summary=f'{name}的分析師 EPS 預估為 {f(eps)} 元；'+('文字表示上修，但缺舊預估，不能算上修幅度。' if prior>0 else '文字表示下修，但缺舊預估，不能算下修幅度。' if prior<0 else '沒有同年度舊預估，不知道這次究竟增加還是減少。') if eps is not None else f'{name}有分析師評估消息，但缺可讀 EPS 預估值。'
            basis='僅有上／下修方向：±14；沒有比較基準與修訂方向則為0'
            missing.append('上次同年度 EPS 預估，不能計算修訂百分比')
        missing+=['EPS 預測年度、分析師家數及預估分歧未核對','目標價的評價方法與調整前基準未核對']
        if eps is not None and eps>0 and target is not None and target>0:
            derived.append({'label':'目標價／EPS 配對情境','value':round(target/eps,2),'unit':'倍','formula':f'{f(target)} ÷ {f(eps)}',
              'assumption':'純標題算術，須先核對 EPS 年度與目標價基期；不是目前本益比，也不是本站目標價'})
        if target is not None:flags.append(f'{f(target)} 元是報導引用的目標價，不是本站預測；沒有當時股價就不計算上漲空間')
        channel='市場獲利預期／估值，不是已實現營收'
        chain=[f'{name}預估 EPS {f(eps)} 元' if eps is not None else f'{name}分析師預估',
               f'與舊預估 {f(old)} 元比較' if old is not None else '缺同年度舊預估，先分清上修幅度',
               '對照估值情境與公司季報，再看價格關卡']
        if kind=='financial':
            kpi=f'{name}：淨利差、信用成本／逾放、手續費收益、ROE 與股價淨值比；金控另查保險曝險'
            confirm=f'核對 {f(eps)} 元 EPS 的預測年度，確認是否來自本業淨利差改善而非處分收益'
            invalid=f'{name}信用成本提高、利差收窄或一次性收益消失，導致同年度 EPS 預估下調'
            action=f'對{name}先做股價淨值比與 ROE 情境；不要拿金融股 EPS 或 PE 直接和半導體股排名'
        else:
            kpi=f'{name}：同年度 EPS 預估修訂幅度、客戶需求與產品組合、下一季公司營運展望'
            confirm=f'取得 {f(eps)} 元對應的預測年度與舊預估，核對公司展望是否支持該成長'
            invalid=f'{name}同年度 EPS 預估被下修，或公司展望不支持報導假設，即重新評估'
            action=f'先比較{name}同年度新舊 EPS，再估算不同 PE 情境；報導目標價不是限價單'
        horizon='下一次同年度預估修訂或公司季報；不是任意指定1–5天'
    elif cat in ('reported_earnings','company_guidance','margin_change','earnings'):
        eps=val(metrics,'eps');margin=val(metrics,'margin')
        positive=bool(re.search(r'成長|上修|增加|轉盈|優於|創.{0,2}高',text));negative=bool(re.search(r'衰退|下修|虧損|下滑|轉虧|低於',text))
        prior=24 if positive and not negative else -24 if negative and not positive else 0
        if cat=='margin_change':
            summary=f'{name}毛利率披露為 {f(margin)}%；缺上期同口徑值時，不把單一水準当作改善。'
            action=f'找{name}上一季與去年同季毛利率，拆解產品組合與成本'
            kpi='毛利率變動百分點、單位成本、產品組合及存貨評價'
            missing=['上期同口徑毛利率與變動原因'];invalid='高毛利來自一次性回沖或產品組合無法延續';confirm='同口徑比較顯示毛利改善且由持續性本業帶動'
            chain=[f'{name}毛利率 {f(margin)}%', '同口徑比較百分點差', '判斷可持續利潤而非單看絕對值']
        else:
            label='公司財測' if cat=='company_guidance' else '獲利披露'
            summary=f'{name}{label}'+(f'中 EPS 為 {f(eps)} 元。' if eps is not None else '有新變動，但沒有完整數值。')+'需區分本業、稅項與一次性損益。'
            action=f'核對{name}財報期間與 EPS 組成，再對照市場原預期'
            missing=['完整報表／財測上下限與比較期間','本業、匯兌及一次性損益拆分']
            chain=[name+label, '拆解本業與一次性項目', '比較預期差，再核對估值']
        if kind=='financial':kpi='淨利差、信用成本、ROE、資本適足性與保險損益';invalid='金融本業獲利或資產品質惡化';confirm='本業收益改善且信用成本未惡化'
        basis='有明確獲利改善／惡化方向±24，僅絕對數值則0；未完成盈餘驚喜校準'
    else:
        summary=f'{name}：'+(chain[0] if chain else '新事件')+'。'+(chain[-1] if chain else '')
        action=f'{name}：'+confirm
        if cat=='orders' and re.search(r'擬|預計|計畫|傳出|洽談',text):prior=8;flags.append('計畫／傳闻不視為已簽約')
        if cat=='promotion':action=f'{name}促銷只追蹤有效新增用戶與補貼，不上修 EPS';missing=['補貼由誰負擔','有效新增客戶與留存率'];summary='曝光與贈點不是新增淨利；先算獲客成本。';invalid='補貼高於新增客戶貢獻，或新增用戶未留存'
        elif cat=='profile':action='移出新聞訊號，只保留為行情查詢入口';missing=[]
        elif cat=='governance':missing=['正式決議與股東權益是否改變'];action=f'閱讀{name}會議決議；會議時數不構成 EPS 方向'
        elif cat=='partnership':missing=['付費客戶／合約金額','商轉與認列時點'];action=f'{name}先追蹤商轉里程碑；合作未落到付費合約前不加碼此因子'
        elif cat=='disruption':missing=['損害範圍與可恢復日期','保險理賠及營運損失'];action=f'{name}先評估受影響產能或費用，暫不把反彈當成危機解除'
        else:missing=['事件金額及與本公司盈餘連結']
    # Headline-only remains explicitly bounded; do not call this a trust probability.
    readable=bool(clean(item.get('excerpt')))
    ef=.95 if item.get('verified_document') and readable else .72 if readable else .55
    rf=1 if rel=='direct' else 0
    raw=clamp(prior,-100,100);score=round(raw*ef*rf,1)
    age=max(0,(cutoff-published).total_seconds()/86400);decay=2**(-age/7);active=round(score*decay,1)
    if not readable:flags.append('內容層級：僅標題，未取得可讀內文；標題明列的數字仍可擷取')
    if rel!='direct':flags.append('無法確認是本公司事件：不計入');summary='公司關聯未確認。'+summary
    return {**{k:v for k,v in item.items() if k not in ('body','full_text')},
      'version':VERSION,'analysis_version':ENGINE,'category':cat,'category_label':LABELS.get(cat,cat),'issuer_kind':kind,
      'relation':rel,'source_assessment':source_status(item),'evidence':evidence,
      'metrics':list(metrics.values()),'derived_metrics':derived,'quantities':[],
      'included':cat!='profile' and rel=='direct','impact_score':score,'active_score':active,
      'score_breakdown':{'raw':round(raw,4),'evidence_factor':ef,'relation_factor':rf,'decay':round(decay,4),'basis':basis,
        'formula':f'{raw:.2f} × {ef} × {rf} = {score:+.1f}；7日半衰期後 {active:+.1f}',
        'meaning':'研究強弱尺度，未校準；不是股價報酬或機率'},
      'increment_type':increment,'summary':summary,'flags':flags,'materiality':'排除' if cat=='profile' else '營運資訊' if increment=='actual_change' else '預估或待驗證訊號',
      'impact_label':'淨方向未定' if score==0 else '正向研究訊號' if score>0 else '負向研究訊號',
      'channel':channel,'chain':chain,'horizon':horizon,'watch_metric':kpi,'confirmation':confirm,'invalidation':invalid,
      'action':action,'risk':invalid,'missing':missing,'analysis_engine':engine,
      'analysis_quality':'未校準，不是上漲機率','analyzed_at':cutoff.isoformat(),
      'model_evidence':model_hint.get('evidence') if model_hint and validate_hint(model_hint,evidence) else None}

def aggregate(events):
    rows=[e for e in events if e.get('included')]
    if not rows:return {'score':None,'events':0,'positive':0,'negative':0,'neutral':0,'explanation':'缺少可確認公司關聯的新聞因子，不用50冒充已分析'}
    # Include zero-valued events in the bounded average. Copies already clustered.
    value=sum(number(e.get('active_score'),number(e.get('impact_score'),0)) for e in rows)/len(rows)
    return {'score':round(clamp(50+value/2),1),'events':len(rows),'positive':sum(e.get('impact_score',0)>0 for e in rows),
      'negative':sum(e.get('impact_score',0)<0 for e in rows),'neutral':sum(e.get('impact_score',0)==0 for e in rows),
      'explanation':f'{len(rows)}組相關事件時效折減後平均 {value:+.2f}，新聞因子＝50＋平均÷2；不是把每篇分數加在股票總分上'}
