"""Build public read-only planning inputs; never stores the user's money or trades.
Official quote cross-check is fail-closed. Missing date must NEVER certify a quote.
"""
from __future__ import annotations
import argparse,hashlib,math
from pathlib import Path
from datetime import datetime,timezone
import requests
from stocklab17.audit import read,write
from stocklab17.calendar import SEED,configured,expected_close
from stocklab17.hygiene import clean_bars
from stocklab17.planner import make_plan
from stocklab16.indicators import enrich

ACCOUNT={'equity':4000,'available_cash':4000,'risk_fraction':.05,'position_fraction':1,'gross_fraction':1,'portfolio_risk_fraction':.05,'sector_fraction':1,'min_commission':20,'holding_sessions':10,'max_positions':1}

def parse_date(raw):
    import re
    ds=re.sub(r'\D','',str(raw or ''))
    try:
        if len(ds)==7:ds=str(int(ds[:3])+1911)+ds[3:]
        if len(ds)!=8:return None
        return datetime.strptime(ds,'%Y%m%d').date().isoformat()
    except (ValueError,OverflowError):return None

def parse_quotes(rows,market):
    result={}
    for r in rows if isinstance(rows,list) else []:
        code=str(r.get('Code') or r.get('SecuritiesCompanyCode') or r.get('SecuritiesCode') or '').strip()
        day=parse_date(r.get('Date') or r.get('date') or r.get('資料日期'))
        raw=r.get('ClosingPrice') or r.get('Close') or r.get('收盤價')
        try:price=float(str(raw).replace(',',''))
        except (ValueError,TypeError):continue
        if code and day and math.isfinite(price) and price>0:result[code+('.TW' if market=='twse' else '.TWO')]={'date':day,'close':price,'source':market}
    return result

def parse_twse_dated(payload,requested):
    """Parse official dated MI_INDEX table. Never infer response date from request."""
    if not isinstance(payload,dict):return {}
    actual=parse_date(payload.get('date'))
    if actual!=requested:return {}
    tables=list(payload.get('tables',[])) if isinstance(payload.get('tables'),list) else []
    if payload.get('fields') and payload.get('data'):tables.append({'fields':payload['fields'],'data':payload['data']})
    for suffix in range(1,15):
        if payload.get('fields'+str(suffix)) and payload.get('data'+str(suffix)):
            tables.append({'fields':payload['fields'+str(suffix)],'data':payload['data'+str(suffix)]})
    out={}
    for tb in tables:
        fields=[str(x).strip() for x in tb.get('fields',[])]
        if '證券代號' not in fields or '收盤價' not in fields:continue
        ci,pi=fields.index('證券代號'),fields.index('收盤價')
        for row in tb.get('data',[]):
            try:
                code=str(row[ci]).strip();price=float(str(row[pi]).replace(',',''))
                if code and math.isfinite(price) and price>0:out[code+'.TW']={'date':actual,'close':price,'source':'TWSE dated MI_INDEX'}
            except (ValueError,TypeError,IndexError):pass
    return out

def verify_stock(last,quote):
    if not quote:return {'status':'unverified','reason':'官方日期／價格未取得，不把Yahoo資料當已核對'}
    if not all(isinstance(x,(int,float)) and math.isfinite(x) and x>0 for x in [quote.get('close'),last.get('close')]):return {'status':'unverified','reason':'官方或來源價格無效'}
    if quote.get('date')!=last.get('date'):return {'status':'date_mismatch','reason':'官方與日K日期不一致','official':quote}
    # Conservative relative tolerance to provider rounding, not a broad percent tolerance.
    if abs(quote['close']-last.get('close',0))>max(.001,quote['close']*.00001):return {'status':'price_mismatch','reason':'官方收盤與來源價格不符','official':quote}
    return {'status':'matched','reason':'同日期官方收盤一致；不代表盤中現價或獲利驗證','official':quote}

def run(root,verify=False):
    root=Path(root);path=root/'data/latest.json'
    if not path.exists():raise ValueError('需要原本 data/latest.json；不以假資料充數')
    snap=read(path);verified={};errors=[];cal=configured();requested=expected_close(snap['generated_at'],cal)
    if verify:
        for market,url in [('twse','https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'),('tpex','https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes')]:
            try:
                r=requests.get(url,timeout=20);r.raise_for_status();verified.update(parse_quotes(r.json(),market))
            except Exception as e:errors.append({'source':market,'error':type(e).__name__})
        # A date-specific official response is the fallback when bulk output has no date.
        need=any(s['symbol'].endswith('.TW') and verified.get(s['symbol'],{}).get('date')!=requested for s in snap['stocks'])
        if need:
            try:
                res=requests.get('https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX',params={'date':requested.replace('-',''),'type':'ALLBUT0999','response':'json'},timeout=20)
                res.raise_for_status();dated=parse_twse_dated(res.json(),requested);verified.update(dated)
                if not dated:errors.append({'source':'twse-dated','error':'no_matching_response_date_or_table'})
            except Exception as e:errors.append({'source':'twse-dated','error':type(e).__name__})
    stocks=[];sourcehash=hashlib.sha256(path.read_bytes()).hexdigest()
    for s in snap['stocks']:
        bars,issues=clean_bars(s.get('candles',[]),snap['generated_at']);bars=enrich([{k:b.get(k) for k in ('date','open','high','low','close','volume','corporate_action')} for b in bars]);last=bars[-1] if bars else {}
        small={**s,'candles':bars[-180:],'quarantined_count':len(issues),'quote_verification':verify_stock(last,verified.get(s['symbol']))}
        small['reference_plan']=make_plan(s,snap['generated_at'],ACCOUNT,[])
        stocks.append(small)
    out={'version':'19.0.0','generated_at':snap['generated_at'],'as_of':snap['as_of'],'prepared_at':datetime.now(timezone.utc).isoformat(),'source_snapshot_sha256':sourcehash,'source_mode':snap.get('mode'),'demo':bool(snap.get('demo')),'stocks':stocks,'top_picks':snap.get('top_picks',[]),'calendar':cal,'verification_errors':errors,'official_verification_attempted':verify,'health':{'required_price_date':requested,'official_matched':sum(s['quote_verification']['status']=='matched' for s in stocks),'stocks':len(stocks),'generated_at':snap['generated_at'],'meaning':'資料不可用與投資不建議分開呈現'},'notes':['規則條件不是預期收益','免費延遲收盤資料，券商現價必須自己核對','個人實際成交保留本機；授權Google後同步私人試算表，不送到GitHub']}
    write(root/'data/life/latest.json',out);print('life data',len(stocks),'stocks; verified',sum(s['quote_verification']['status']=='matched' for s in stocks));return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--verify',action='store_true');a=p.parse_args();run(a.root,a.verify)
if __name__=='__main__':main()
