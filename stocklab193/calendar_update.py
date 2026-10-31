"""Refresh ONLY exchange-published years; do not label weekdays as known sessions.
On transport/parser failure retain the calendar. Existing dates must agree.
"""
from __future__ import annotations
import re,json,os
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from stocklab193.budget import load,write

SOURCE='https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule'

def parse_year(payload,year):
    rows=payload.get('data',[]) if isinstance(payload,dict) else []
    if not rows:raise ValueError('Official calendar has no rows for requested year')
    closed=[];seen=set()
    for row in rows:
        if not isinstance(row,list) or len(row)<2:raise ValueError('Unexpected official calendar schema')
        text=str(row[0]).strip();m=re.search(r'(\d{3,4})[/-](\d{1,2})[/-](\d{1,2})',text)
        if not m:raise ValueError('Unrecognized calendar date: '+text)
        y,mo,day=map(int,m.groups());y=y+1911 if y<1911 else y
        if y!=year:raise ValueError('Official endpoint returned another year')
        d=date(y,mo,day).isoformat();seen.add(d);name=str(row[1])
        if any(w in name for w in ('開始交易','最後交易')):continue
        closed.append(d)
    if len(seen)<5:raise ValueError('Too few holiday entries; refusing to extend known coverage')
    return {'start':f'{year}-01-01','end':f'{year}-12-31','closed':sorted(set(closed))}

def refresh(root=None,fetcher=None):
    root=Path(root or Path(__file__).resolve().parents[1]);p=root/'data/calendar/latest.json'
    base=load(p,None) or load(root/'assets/paper-calendar.json',{})
    if not base:raise ValueError('No fallback calendar')
    now=datetime.now(ZoneInfo('Asia/Taipei'));statuses=[]
    if fetcher is None:
        import requests
        def fetcher(year):
            x=requests.get(SOURCE,params={'date':year,'response':'json'},headers={'User-Agent':'StockLab-PaperLab/19.3 personal research'},timeout=12)
            x.raise_for_status();return x.json()
    result=dict(base)
    for year in (now.year,now.year+1):
        try:
            part=parse_year(fetcher(year),year)
            overlap_start=max(result['start'],part['start']);overlap_end=min(result['end'],part['end'])
            if overlap_start<=overlap_end:
                old={x for x in result['closed'] if overlap_start<=x<=overlap_end};new={x for x in part['closed'] if overlap_start<=x<=overlap_end}
                if old!=new:raise ValueError('Existing dates differ; manual review required, no silent rewrite')
            end_year=int(result['end'][:4])
            if year>end_year+1:raise ValueError('Non-contiguous calendar extension')
            result.update(start=min(result['start'],part['start']),end=max(result['end'],part['end']),closed=sorted(set(result['closed']+part['closed'])))
            statuses.append({'year':year,'status':'official_rows_validated'})
        except Exception as e:statuses.append({'year':year,'status':'retained_previous','reason':str(e)[:250]})
    result.update(source=SOURCE,checked_at=now.isoformat(),refresh=statuses,note='Only populated TWSE years; exceptional closures still require official updates. No weekday guessing.')
    write(p,result);print(json.dumps({'coverage_end':result['end'],'years':statuses},ensure_ascii=False));return result
if __name__=='__main__':refresh()
