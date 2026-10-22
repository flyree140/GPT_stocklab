"""Quarantine suspicious raw OHLC rows; never relabel a Sunday as Monday."""
from math import isfinite
from .calendar import is_session,parse_time,clock

def clean_bars(rows,cutoff=None,calendar=None):
    good={};issues=[]
    for r in rows:
        day=r.get('date','');reason=None
        try:
            if not is_session(day,calendar):reason='non_trading_date'
            values=[float(r[k]) for k in ('open','high','low','close')]
            o,h,l,c=values
            if not all(isfinite(x) and x>0 for x in values) or l>min(o,c) or h<max(o,c) or l>h:reason='invalid_ohlc'
            if float(r.get('volume',0))<=0:reason='zero_volume'
            if cutoff and clock(day,13,30)>parse_time(cutoff):reason='not_yet_closed'
            if day in good and any(good[day].get(k)!=r.get(k) for k in ('open','high','low','close')):reason='conflicting_duplicate'
        except (ValueError,KeyError,TypeError):reason='invalid_bar'
        if reason:issues.append({'date':day,'reason':reason,'bar':r})
        else:good[day]=r
    return [good[k] for k in sorted(good)],issues
