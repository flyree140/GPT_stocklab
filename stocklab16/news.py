from __future__ import annotations
import html, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import date,timedelta,timezone
from email.utils import parsedate_to_datetime
from .common import now,TZ

def fetch(company, symbol, as_of, lookback=3, limit=8):
    end=date.fromisoformat(as_of)+timedelta(days=1); start=end-timedelta(days=lookback+1)
    q=f'"{company}" OR "{symbol.split(".")[0]}" after:{start.isoformat()} before:{end.isoformat()}'
    url='https://news.google.com/rss/search?q='+urllib.parse.quote_plus(q)+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 StockLab16'})
    try:
        body=urllib.request.urlopen(req,timeout=25).read(); root=ET.fromstring(body)
    except Exception as exc:
        print('news unavailable',company,exc); return []
    out=[]
    for item in root.findall('.//item'):
        title=html.unescape((item.findtext('title') or '').strip()); link=(item.findtext('link') or '').strip(); raw=item.findtext('pubDate') or ''
        try: published=parsedate_to_datetime(raw)
        except Exception: continue
        if published.tzinfo is None: published=published.replace(tzinfo=timezone.utc)
        if not (start<=published.astimezone(TZ).date()<=date.fromisoformat(as_of)): continue
        if published>now(): continue
        source=item.find('source'); publisher=(source.text or '').strip() if source is not None else ''
        out.append({'title':title,'url':link,'source_url':source.attrib.get('url',link) if source is not None else link,'publisher':publisher,'published_at':published.isoformat(),'available_at':published.isoformat(),'fetched_at':now().isoformat()})
        if len(out)>=limit: break
    return out
