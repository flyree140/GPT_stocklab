from __future__ import annotations
from datetime import date,timedelta
from .common import number,now
from .indicators import enrich

def history(symbol, as_of, days=420):
    try:
        import yfinance as yf
        end=date.fromisoformat(as_of)+timedelta(days=1); start=end-timedelta(days=days*2)
        df=yf.download(symbol,start=start.isoformat(),end=end.isoformat(),auto_adjust=False,actions=True,progress=False,threads=False,timeout=25)
        if getattr(df.columns,'nlevels',1)>1: df.columns=df.columns.get_level_values(0)
        rows=[]
        for idx,row in df.tail(days).iterrows():
            c=number(row.get('Close')); o=number(row.get('Open')); h=number(row.get('High')); l=number(row.get('Low')); v=number(row.get('Volume'),0)
            if None in (c,o,h,l): continue
            if idx.strftime('%Y-%m-%d')>as_of:continue
            rows.append({'date':idx.strftime('%Y-%m-%d'),'open':o,'high':h,'low':l,'close':c,'volume':v,'corporate_action':bool(number(row.get('Dividends'),0) or number(row.get('Stock Splits'),0))})
        return enrich(rows)
    except Exception as exc:
        print('history unavailable',symbol,exc); return []

def current_info(symbol):
    try:
        import yfinance as yf
        info=yf.Ticker(symbol).get_info() or {}
        rev=number(info.get('revenueGrowth')); pe=number(info.get('trailingPE')); eps=number(info.get('trailingEps'))
        return {'revenue_growth_reported':rev*100 if rev is not None else None,'revenue_growth_basis':'Yahoo revenueGrowth；比較期間未核對，非月營收','eps':eps,'pe':pe,'pb':number(info.get('priceToBook')),'roe':number(info.get('returnOnEquity'))*100 if number(info.get('returnOnEquity')) is not None else None,'profit_growth':number(info.get('earningsGrowth'))*100 if number(info.get('earningsGrowth')) is not None else None,'available_at':now().isoformat(),'source':'Yahoo Finance（需以公司公告複核）','issuer_sector':info.get('industry')}
    except Exception:return {'revenue_yoy':None,'eps':None,'pe':None}

def market_score(rows):
    if len(rows)<60:return None
    last=rows[-1]
    score=50+(14 if last['close']>last['ma20'] else -14)+(10 if last['close']>last['ma60'] else -10)
    return max(0,min(100,score))
