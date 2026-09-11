from __future__ import annotations
from .common import number

def mean(values):
    vals=[number(x) for x in values if number(x) is not None]
    return sum(vals)/len(vals) if vals else None

def enrich(rows):
    out=[]; closes=[]; gains=[]; losses=[]; trs=[]; e12=e26=sig=None; k=d=50.0; ag=al=None
    for i,src in enumerate(rows):
        r=dict(src); c=number(r.get('close'))
        if c is None: continue
        prev=closes[-1] if closes else c; closes.append(c)
        high=number(r.get('high'),c); low=number(r.get('low'),c)
        trs.append(max(high-low,abs(high-prev),abs(low-prev)))
        if i:
            diff=c-prev; gains.append(max(diff,0)); losses.append(max(-diff,0))
        if len(gains)>=14:
            if ag is None: ag=mean(gains[:14]); al=mean(losses[:14])
            else: ag=(ag*13+gains[-1])/14; al=(al*13+losses[-1])/14
            r['rsi']=100 if al==0 and ag>0 else 50 if al==0 else 100-100/(1+ag/al)
        else:r['rsi']=None
        e12=c if e12 is None else c*2/13+e12*11/13
        e26=c if e26 is None else c*2/27+e26*25/27
        macd=e12-e26; sig=macd if sig is None else macd*.2+sig*.8
        r['macd']=macd if len(closes)>=26 else None; r['signal']=sig if len(closes)>=26 else None; r['histogram']=macd-sig if len(closes)>=26 else None
        win=rows[max(0,i-8):i+1]; lo=min(number(x.get('low'),c) for x in win); hi=max(number(x.get('high'),c) for x in win)
        rsv=50 if hi==lo else (c-lo)/(hi-lo)*100; k=k*2/3+rsv/3; d=d*2/3+k/3
        r['k']=k if len(closes)>=9 else None; r['d']=d if len(closes)>=9 else None
        r['ma5']=mean(closes[-5:]) if len(closes)>=5 else None; r['ma20']=mean(closes[-20:]) if len(closes)>=20 else None; r['ma60']=mean(closes[-60:]) if len(closes)>=60 else None
        r['atr']=mean(trs[-14:]) if len(trs)>=14 else None
        if len(closes)>=20:
            r['support']=min(number(x.get('low'),c) for x in rows[i-19:i+1]); r['resistance']=max(number(x.get('high'),c) for x in rows[i-19:i+1])
        else:r['support']=r['resistance']=None
        out.append(r)
    return out
