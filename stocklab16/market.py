from __future__ import annotations
from datetime import date,timedelta
from .common import number
from .indicators import enrich

def history(symbol, as_of, days=420):
    try:
        import yfinance as yf
        end=date.fromisoformat(as_of)+timedelta(days=1); start=end-timedelta(days=days*2)
        df=yf.download(symbol,start=start.isoformat(),end=end.isoformat(),auto_adjust=False,progress=False,threads=False,timeout=25)
        if getattr(df.columns,'nlevels',1)>1: df.columns=df.columns.get_level_values(0)
        rows=[]
        for idx,row in df.tail(days).iterrows():
            c=number(row.get('Close')); o=number(row.get('Open')); h=number(row.get('High')); l=number(row.get('Low')); v=number(row.get('Volume'),0)
            if None in (c,o,h,l): continue
            rows.append({'date':idx.strftime('%Y-%m-%d'),'open':o,'high':h,'low':l,'close':c,'volume':v})
        return enrich(rows)
    except Exception as exc:
        print('history unavailable',symbol,exc); return []

def current_info(symbol):
    try:
        import yfinance as yf
        info=yf.Ticker(symbol).get_info() or {}
        rev=number(info.get('revenueGrowth')); pe=number(info.get('trailingPE')); eps=number(info.get('trailingEps'))
        return {'revenue_yoy':rev*100 if rev is not None else None,'eps':eps,'pe':pe}
    except Exception:return {'revenue_yoy':None,'eps':None,'pe':None}

def market_score(rows):
    if len(rows)<60:return None
    last=rows[-1]
    score=50+(14 if last['close']>last['ma20'] else -14)+(10 if last['close']>last['ma60'] else -10)
    return max(0,min(100,score))
