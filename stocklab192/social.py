"""As-of social attention. These are sample statistics, not market-wide truth.
No network collection is enabled by default; no author text is published by summary.
"""
from __future__ import annotations
import hashlib,re,math,json
from datetime import timedelta
from collections import Counter
from statistics import median
from .schema import timestamp


def normalize(text):return re.sub(r'\s+',' ',str(text).strip().lower())

def summarize(posts,cutoff,*,source_ok=False,baseline=None,collection_key='default',limit=5000):
    if not source_ok:return {'status':'missing','values':{},'missing':['社群來源未授權、未執行或連線失敗；不可填0熱度'],'sample_scope':True}
    cut=timestamp(cutoff);start=cut-timedelta(hours=24);seen=set();authors=Counter();sent=[];raw=0;unique=0;excluded=0
    for p in posts[:limit]:
        try:
            if not p.get('analysis_allowed'):excluded+=1;continue
            # Reading historical posts today does not reconstruct then-current likes/counts.
            if timestamp(p['observed_at'])>cut or timestamp(p['available_at'])>cut:excluded+=1;continue
            if not start<timestamp(p['published_at'])<=cut:continue
            if not p.get('issuer_verified'):excluded+=1;continue
            raw+=1;key=hashlib.sha256(normalize(p['text']).encode()).hexdigest()
            if key in seen:continue
            seen.add(key);unique+=1
            author=p.get('author_hash')
            if author:authors[str(author)]+=1
            label=p.get('sentiment')
            if label in ('positive','negative','neutral') and p.get('sentiment_method') in ('human','validated_classifier'):
                # cap repeated author's effect; missing identity does not become a new independent user
                if author and authors[str(author)]<=3:sent.append({'positive':1,'negative':-1,'neutral':0}[label])
        except (KeyError,ValueError,TypeError):excluded+=1
    history=[]
    for b in baseline or []:
        try:
            if b.get('collection_key')!=collection_key or not b.get('source_ok'):continue
            t=timestamp(b['cutoff'])
            if not start-timedelta(days=20)<=t<=start:continue
            if b.get('window_hours')!=24:continue
            count = b.get('unique_posts', (b.get('values') or {}).get('unique_posts'))
            if count is None or float(count) < 0:continue
            history.append(float(count))
        except (KeyError,ValueError,TypeError):continue
    center=median(history) if len(history)>=5 else None
    mad=median([abs(x-center) for x in history]) if center is not None else None
    z=(unique-center)/(1.4826*mad) if mad and mad>0 else None
    return {'status':'partial' if unique<10 or len(history)<5 else 'available','values':{
      'raw_posts':raw,'unique_posts':unique,'known_unique_authors':len(authors),
      'duplicate_fraction':(raw-unique)/raw if raw else None,
      'largest_author_fraction':max(authors.values())/unique if authors and unique else None,
      'reviewed_sentiment_balance':sum(sent)/len(sent) if sent else None,
      'sentiment_labeled_posts':len(sent),'attention_robust_z':z,'baseline_windows':len(history)},
      'available_at':cutoff,'cutoff':cutoff,'collection_key':collection_key,'source_ok':True,'window_hours':24,
      'missing':(['樣本少於10篇'] if unique<10 else [])+(['至少5個同口徑歷史窗口才能比較熱度'] if len(history)<5 else []),
      'excluded':excluded,'sample_scope':True,'training_permission_not_implied':True,
      'notes':['只代表採樣平台與查詢範圍。','疑似集中或重複不等於確定機器人。','熱度可同時代表利多、爭議或出貨；不可單獨放行試買。','留言按讚以當時擷取值為準，不以今天累計量倒填舊日。']}


def fetch_author_feed(actor,*,permission_confirmed=False,limit=30):
    """Optional public Bluesky author-feed sample, not keyword-wide coverage.
    Do not change hosts/methods to evade 401/403/429. Training rights remain false.
    """
    if not permission_confirmed:raise ValueError('先核對來源條款並確認允許此次採樣；預設不抓取')
    import requests
    from datetime import datetime,timezone
    r=requests.get('https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed',
        params={'actor':actor,'limit':min(30,max(1,int(limit))),'filter':'posts_no_replies'},timeout=20)
    if r.status_code in (401,403,429):return {'ok':False,'status':r.status_code,'posts':[],'reason':'授權／限流；停止，不繞過'}
    r.raise_for_status();now=datetime.now(timezone.utc).isoformat();out=[]
    for item in r.json().get('feed',[]):
        p=item.get('post',{});record=p.get('record',{});author=p.get('author',{}).get('did','')
        out.append({'id':p.get('uri'),'text':record.get('text',''),'published_at':record.get('createdAt'),
           'available_at':now,'observed_at':now,'source':'Bluesky-author-sample','analysis_allowed':True,
           'training_allowed':False,'issuer_verified':False,'author_hash':hashlib.sha256(author.encode()).hexdigest() if author else None,
           'sentiment':None,'sentiment_method':None})
    return {'ok':True,'posts':out,'note':'必須先做公司關聯核對；公開可讀不等於有權拿來微調。'}
