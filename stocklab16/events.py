"""Evidence-first event analysis. An attractive headline is not booked profit.
Taxonomy and causal hypotheses are explicit research rules, not price forecasts.
Qwen can select a taxonomy using an exact supplied evidence span; it never writes
unverified narrative into the authoritative score/decision fields.
"""
from __future__ import annotations
import re, html
from difflib import SequenceMatcher
from urllib.parse import urlsplit
from .common import dt, digest, number, clamp, VERSION

# category, terms, estimated channel, conditional causal chain, horizon trigger,
# next KPI, confirmation condition, invalidation, headline score prior.
RULES = [
 ('profile',r'個股概覽|個股總覽|即時股價|股票代號查詢|歷史股價查詢', '非事件',
  ['行情資訊頁','沒有新增營運事件','不納入新聞訊號'], '不適用',
  '找出有發布時間的公司公告或新聞', '必須有新增且可驗證的公司事件', '靜態行情頁不能作為買賣依據', 0),
 ('promotion',r'聯名卡|贈.{0,8}(點|Point)|回饋|抽獎|優惠碼|刷卡|限時優惠|促銷', '獲客成本／留存',
  ['行銷優惠','可能增加申辦，也可能增加補貼成本','對淨利的方向仍不確定'], '活動結束後的實際申辦／留存資料',
  '新增有效客戶、每戶取得成本、留存與補貼負擔', '新增用戶貢獻的毛利高於補貼與行銷成本', '只有點數曝光，或新增客戶未能留存', 0),
 ('governance',r'股東會|董事.{0,4}改選|董事會|經營權|公司治理', '治理／股東權益',
  ['治理事件','需看決議與權利是否改變','會議時間長短本身不代表盈餘變動'], '正式決議／重訊公布時',
  '決議內容、爭議案、董事改選、股利與訴訟風險', '確認有影響現金流或股東權益的正式決議', '只描述開會時間或花絮，沒有實質決議', 0),
 ('earnings',r'月營收|營收|財報|EPS|每股盈餘|毛利率|財測|獲利|淨利', '營收／獲利',
  ['營運數字或財測變動','確認成長來源與毛利能否維持','可改變獲利預期，但不等於股價必漲'], '下一次月營收／季報核對',
  '同比與環比、一次性項目、毛利率、管理層財測', '成長不只來自基期或業外，且毛利率未惡化', '營收成長但毛利下滑，或一次性收益占主因', 42),
 ('capital',r'增資|可轉債|募資|庫藏股|減資', '資本／稀釋',
  ['資本結構變動','稀釋、資金成本或每股利益改變','須按用途與條件重新估算每股價值'], '董事會條件／發行條件確認後',
  '發行價、股數、用途、利率與對 EPS 的稀釋', '資金用途回報足以覆蓋融資成本與稀釋', '低價大量發行而用途不明確', -12),
 ('dividend',r'配息|股利|除息|現金股息', '股東現金回報',
  ['股利政策','改變現金分配而非憑空創造報酬','需同時看盈餘與現金流支撐'], '正式股利決議／除息日期確認後',
  '配發率、自由現金流、是否一次性分配', '股利由可持續現金流支撐，而非額外借款', '股息高但營運現金流不足或股價調整未計入', 15),
 ('disruption',r'停工|火災|地震|斷電|資安|駭客|召回|制裁|禁令|罰款|裁罰', '供應／成本／法遵',
  ['營運或法遵衝擊','可能增加成本、停產或損失客戶','需確認損害範圍與恢復進度'], '公司損害評估／復工公告更新時',
  '受影響產能、停工天數、罰款／保險與補救成本', '官方確認影響範圍及可量化損失', '事件排除、影響有限或已被保險充分覆蓋', -50),
 ('orders',r'訂單|得標|合約|出貨|簽約|擴產|資本支出', '訂單／現金流',
  ['合約、出貨或投資','先辨別已簽約還是洽談／產能建置','收入認列與資本支出可能不同步'], '交付／驗收與財報認列時',
  '合約金額、毛利、認列期間、取消條款與資本支出', '具體訂單可驗證且有交付／收入認列安排', '仍在洽談，或資本支出上升而需求未落實', 26),
 ('partnership',r'合作|加速器|5G|AI|策略聯盟|新創|商機|研發|新產品|布局', '成長選項／商業化',
  ['技術合作或新業務','可能打開應用與客戶，但尚未等於訂單','先列追蹤，不直接上修盈餘'], '付費客戶／合約或分部營收被揭露時',
  '付費客戶數、正式合約金額、商轉時間、分部營收', '試驗或合作轉成可驗證的付費合約', '只維持概念合作，沒有付費客戶或收入認列', 12),
 ('macro',r'利率|匯率|升息|降息|關稅|油價|原物料', '外部成本／折現率',
  ['總體條件變動','須核對公司實際曝險與避險政策','受益與受損可能同時存在'], '政策生效與公司曝險揭露後',
  '幣別、避險比率、成本轉嫁與市場需求', '曝險方向及量級獲財報或公司說明支持', '曝險小、已避險或價格轉嫁抵銷影響', 0),
]
BY_ID={r[0]:r for r in RULES}
LABELS={'profile':'靜態行情頁','promotion':'行銷促銷','governance':'公司治理','earnings':'營運財報','capital':'資本變動','dividend':'股利政策','disruption':'營運中斷／法遵','orders':'訂單與產能','partnership':'合作與商業化','macro':'總體曝險','unclear':'尚待辨識事件'}
NEGATIVE=re.compile(r'衰退|下修|虧損|下滑|減少|縮減|低於|轉弱|下跌')
POSITIVE=re.compile(r'成長|增加|上修|創高|創新高|優於|轉盈|提高')

def clean(t): return ' '.join(html.unescape(re.sub('<[^>]+>',' ',str(t or ''))).split())
def sentences(item):
    text=clean(item.get('title',''))
    body=clean(item.get('excerpt',''))
    # Keep short evidence units. No full article redistribution.
    chunks=[text]+re.split(r'[。\n；]',body)
    return [{'id':f'e{i+1}','text':s[:250]} for i,s in enumerate(dict.fromkeys(s for s in chunks if s))][:8]
def categorize(item):
    text=clean(item.get('title',''))+' '+clean(item.get('excerpt',''))
    for r in RULES:
        if re.search(r[1], text, re.I): return r[0]
    return 'unclear'
def issuer_relation(item, meta):
    text=clean(item.get('title',''))+' '+clean(item.get('excerpt',''))
    names=[meta.get('name','')]+meta.get('aliases',[])
    # Pure numeric ticker hits are not sufficient (e.g. an unrelated date/price).
    if any(n and n.lower() in text.lower() for n in names): return 'direct'
    code=meta.get('symbol','').split('.')[0]
    if code and re.search(r'(?:\(|（)'+re.escape(code)+r'(?:\)|）)',text): return 'direct'
    return 'unconfirmed'
def source_status(item):
    host=urlsplit(str(item.get('source_url') or item.get('url') or '')).hostname or ''
    official=any(host==d or host.endswith('.'+d) for d in ('twse.com.tw','tpex.org.tw','gov.tw'))
    return {'publisher':item.get('publisher') or item.get('source') or '來源待核對',
            'host':host,'kind':'交易所／政府' if official else '公司原始文件' if item.get('official_document') else '媒體／彙整',
            'coverage':'文件節錄' if item.get('evidence_level')=='document' else '摘要可讀' if item.get('excerpt') else '僅標題',
            'verified':bool(item.get('verified_document')), 'fetched_at':item.get('fetched_at'),
            'note':'來源屬性不等於新聞正確率；未驗證的摘要不得標成已確認'}

def group_items(items, meta):
    """Conservative similarity clustering: duplicates not independent confirmations."""
    result=[]
    for item in sorted(items,key=lambda a:a.get('published_at','')):
        title=clean(item.get('title',''))
        if not title: continue
        norm=re.sub(r'[^\w\u4e00-\u9fff]','',title.lower())
        # Remove publisher suffix for cross-feed copy detection.
        norm=re.sub(r'[^\w\u4e00-\u9fff]','',title.rsplit(' - ',1)[0].lower())
        found=None
        for old in result:
            if (abs((dt(item['published_at'])-dt(old['published_at'])).total_seconds())<3*86400
                and (norm==old['_norm'] or SequenceMatcher(None,norm,old['_norm']).ratio()>=.88)):
                found=old;break
        if found:
            found['copies'].append({'title':title,'url':item.get('url',''),'publisher':item.get('publisher','')})
            if len(item.get('excerpt',''))>len(found.get('excerpt','')): found['excerpt']=item['excerpt']
        else:
            result.append({**item,'title':title,'_norm':norm,'copies':[],
                           'id':digest([meta['symbol'],norm,item['published_at'][:10]])[:20]})
    for item in result: item.pop('_norm',None)
    return result

def analyze(item,meta,cutoff, model_hint=None):
    published=dt(item['published_at']); cutoff=dt(cutoff)
    available=dt(item.get('available_at') or item['published_at'])
    if max(published,available)>cutoff: raise ValueError('Article was not available at cutoff')
    cat=categorize(item); evidence=sentences(item); origin='規則事件分析'
    # A model's selected category is accepted only with a verbatim evidence span,
    # explicit taxonomy, no unprovided numbers, and no overriding a static page.
    if cat!='profile' and model_hint and validate_hint(model_hint,evidence):
        cat=model_hint['category']; origin='Qwen 證據分類＋透明規則'
    rel=issuer_relation(item,meta); rule=BY_ID.get(cat)
    if rule:
        _,_,channel,chain,horizon,kpi,confirm,invalid,prior=rule
    else:
        channel='影響路徑未明'; chain=['已出現報導','缺少可驗證的營運變動','暫不轉成投資訊號']
        horizon='補足具體事件之後';kpi='事件主體、金額、時間、原始公告';confirm='可確認具體營運變動';invalid='只剩市場評論或推測';prior=0
    text=' '.join(e['text'] for e in evidence)
    if cat=='earnings':
        prior=-42 if NEGATIVE.search(text) else 42 if POSITIVE.search(text) else 0
    # Headline and signed contract are not the same evidence strength.
    factor=.45 if not item.get('excerpt') else .70 if not item.get('verified_document') else .95
    if cat=='orders' and re.search('預計|計畫|擬|洽談|傳出',text): prior=8
    if cat=='capital' and '庫藏股' in text: prior=10
    base=prior * factor * (1 if rel=='direct' else .15)
    score=round(clamp(base,-100,100))
    age=max(0,(cutoff-published).total_seconds()/86400)
    active_score=round(score*(2**(-age/7)),1)
    impact='不具交易訊號' if cat=='profile' else '尚不能判定淨影響' if score==0 else '方向偏正、幅度待證實' if score>0 else '方向偏負、規模待釐清'
    decision='排除，避免當成新聞重複加分' if cat=='profile' else '不因本則新聞買入' if cat in ('promotion','governance','unclear') else '列入追蹤，等收入證据與價格條件' if cat=='partnership' else '先核對公司公告，再檢查估值與進場條件'
    risk='尚未有足夠資訊估算對 EPS 的影響'
    if cat=='promotion': risk='500 點是促銷誘因，不是公司新增營收或 EPS；補貼由誰負擔仍待確認'
    if cat=='governance': risk='會議超過 18 小時或凌晨結束，本身不能推導獲利方向'
    if cat=='partnership': risk='加速器／5G 合作不等於已簽約訂單，不能把商機當成認列收入'
    if cat=='profile': risk='靜態行情入口不是新的催化事件，不進入當日評分'
    # Numbers are quoted as evidence, not converted blindly to money/revenue.
    quantities=[]
    for ev in evidence:
        for m in re.finditer(r'(?:[+-]?\d[\d,.]*\s*(?:%|％|億元|萬元|億|萬|元|點|小時|家|年|日))',ev['text']):
            quantities.append({'text':m.group(0),'evidence_id':ev['id'],'meaning':'原文數字；未自動視為 EPS 或訂單金額'})
    missing=['EPS 敏感度尚未量化','無法僅憑新聞判定市場是否已反映']
    if not item.get('excerpt'):missing.insert(0,'尚未取得可讀內文')
    materiality='排除' if cat=='profile' else '低／未知' if cat in ('promotion','governance','partnership','unclear') else '待量化的營運事件'
    return {**{k:v for k,v in item.items() if k not in ('body','full_text')},
            'version':VERSION,'category':cat,'category_label':LABELS[cat],
            'relation':rel,'source_assessment':source_status(item),
            'evidence':evidence,'quantities':quantities[:6],
            'included':cat!='profile' and rel=='direct',
            'impact_score':score,'active_score':active_score,'impact_label':impact,
            'materiality':materiality,'channel':channel,'chain':chain,
            'horizon':horizon,'watch_metric':kpi,'confirmation':confirm,
            'invalidation':invalid,'action':decision,'risk':risk,'missing':missing,
            'analysis_engine':origin,'analysis_quality':'未校準；不是上漲機率',
            'analyzed_at':cutoff.isoformat(), 'future_outcome':None if False else 'not_computed'}

def validate_hint(hint, evidence):
    if not isinstance(hint,dict) or hint.get('category') not in LABELS:return False
    span=hint.get('evidence','')
    if not isinstance(span,str) or len(span.strip())<3:return False
    return any(span in ev['text'] for ev in evidence)

def aggregate(events):
    rows=[e for e in events if e.get('included')]
    if not rows:return {'score':None,'events':0,'positive':0,'negative':0,'neutral':0,'explanation':'未取得可用且相關的事件，新聞因子缺值'}
    # Bounded signed average; repeated syndication never increases strength.
    directional=[e for e in rows if e['impact_score']!=0]
    value=sum(e['active_score'] for e in directional)/max(1,len(directional))
    return {'score':round(50+value/2,1),'events':len(rows),
            'positive':sum(e['impact_score']>0 for e in rows),'negative':sum(e['impact_score']<0 for e in rows),
            'neutral':sum(e['impact_score']==0 for e in rows),
            'explanation':'0 表示淨方向未知／中性，不代表沒有風險；缺新聞保持缺值'}
