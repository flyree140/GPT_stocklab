from datetime import datetime
from pathlib import Path
import json
import pytest
from stocklab194.evidence import parse_feed,plain,meaningful,Collector,relationship,topic_tags,safe_url,norm
from stocklab16.common import read_json,write_json
AT=datetime.fromisoformat('2026-11-06T15:00:00+08:00')
SRC={'name':'測試RSS','url':'https://example.org/feed'}
TEXT='（測試來源）本文為自寫測試資料，說明已公開的市場風險資訊，並且列出事件還有哪些條件需要持續追蹤。它不代表任何真實公司或最新市場消息。'
def xml(title='虛構公司公布測試資料',desc=TEXT,at='Fri, 06 Nov 2026 06:00:00 GMT'):
 return f'<rss><channel><item><title>{title}</title><link>https://example.org/article/1</link><description><![CDATA[<p>{desc}</p>]]></description><pubDate>{at}</pubDate></item></channel></rss>'.encode()
def test_intro_retained_not_called_verified():
 rows=parse_feed(xml(),SRC,AT.isoformat());assert rows[0]['excerpt']==TEXT and not rows[0]['verified_document']
 assert rows[0]['available_at']==AT.isoformat() and rows[0]['content_status']=='rss_introduction'
def test_title_repeated_is_not_body():
 title='公司只有標題沒有內文'*10
 row=parse_feed(xml(title,title),SRC,AT.isoformat())[0];assert row['excerpt']==''
def test_future_publication_rejected():
 assert parse_feed(xml(at='Fri, 06 Nov 2026 09:00:00 GMT'),SRC,AT.isoformat())==[]
def test_past_window_rejected():
 assert parse_feed(xml(at='Fri, 09 Oct 2026 06:00:00 GMT'),SRC,AT.isoformat())==[]
def test_html_commands_not_executed():
 assert plain('<script>alert(1)</script><b>數字</b> &amp; 證據')=='數字 & 證據'
def test_dtd_rejected():
 with pytest.raises(ValueError):parse_feed(b'<!DOCTYPE rss><rss/>',SRC,AT.isoformat())
def test_invalid_private_literal_urls_rejected():
 for x in ['file:///etc/passwd','http://example.org','https://127.0.0.1/a','https://user:pass@abc.com','https://localhost/','https://169.254.169.254/']:
  assert not safe_url(x)
def test_safe_https_external():assert safe_url('https://example.org/article/1')
def test_collector_fetch_cache_reuses_observed_time(tmp_path):
 calls=[]
 def fetch(url,**kw):calls.append(url);return xml()
 write_json(tmp_path/'config/news-evidence.json',{'feeds':[SRC],'max_context_requests':1})
 a=Collector(tmp_path,fetcher=fetch,clock=lambda:AT);a.collect()
 b=Collector(tmp_path,fetcher=fetch,clock=lambda:AT);b.collect()
 assert len(calls)==1 and b.report()['sources'][0]['status']=='cache'
 assert b.items[0]['available_at']==AT.isoformat()
def test_failed_source_explicit_no_fabrication(tmp_path):
 def fail(*a,**k):raise TimeoutError('offline')
 c=Collector(tmp_path,fetcher=fail,clock=lambda:AT);assert c.collect()==[]
 assert len(c.report()['sources'])==5 and all(x['status']=='failed' for x in c.status)
def test_foreign_policy_not_stock_fact():
 e={'title':'Data center capex restriction news','topics':topic_tags('data center capex restrictions')}
 r=relationship({'name':'台積電','sector':'半導體'},e)
 assert r['type']=='sector_hypothesis' and r['changes_company_score'] is False
def test_market_risk_not_same_as_company_earnings():
 e={'title':'台股外資賣超連跌','topics':topic_tags('台股外資賣超連跌')}
 r=relationship({'name':'中華電','sector':'電信'},e);assert r['type']=='market_risk'
def test_no_unproven_company_relationship():
 assert relationship({'name':'虛構A','sector':'水泥'},{'title':'虛構B新產品','excerpt':''}) is None
def test_default_does_not_crawl_google_or_homepage(tmp_path):
 c=Collector(tmp_path,fetcher=lambda *a,**k:(_ for _ in ()).throw(AssertionError()),clock=lambda:AT)
 row={'title':'公司新聞','url':'https://news.google.com/rss/articles/opaque','source_url':'https://example.org'}
 assert c.try_document(row)==row and c.article_attempts==0
def test_enrich_same_title_provenance_not_invented(tmp_path):
 c=Collector(tmp_path,clock=lambda:AT);c.items=parse_feed(xml(),SRC,AT.isoformat())
 original={**c.items[0],'excerpt':'','content_status':'headline_only','verified_document':True}
 result=c.enrich([original],{'name':'無關公司'})[0]
 assert result['excerpt']==TEXT and result['verified_document'] is False
 assert result['available_at']==AT.isoformat()
def test_only_title_does_not_gain_evidence_weight():
 from stocklab16.events import analyze
 item=parse_feed(xml(title='虛構公司月營收年增10%',desc='虛構公司月營收年增10%'),SRC,AT.isoformat())[0]
 x=analyze(item,{'name':'虛構公司','symbol':'1234.TW'},AT.isoformat());assert x['score_breakdown']['evidence_factor']==.55
