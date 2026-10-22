"""Explicit calendar coverage: do not invent trading sessions or future holidays."""
from datetime import date,datetime,time,timedelta
from zoneinfo import ZoneInfo
TZ=ZoneInfo('Asia/Taipei')
# TWSE annual schedule; review emergency closures and future years.
SEED={'start': '2026-01-01', 'end': '2026-12-31', 'closed': ['2026-01-01', '2026-02-12', '2026-02-13', '2026-02-15', '2026-02-16', '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20', '2026-02-27', '2026-02-28', '2026-04-03', '2026-04-04', '2026-04-05', '2026-04-06', '2026-05-01', '2026-06-19', '2026-09-25', '2026-09-28', '2026-10-09', '2026-10-10', '2026-10-25', '2026-10-26', '2026-12-25'], 'source': 'https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html', 'verified_on': '2026-10-20', 'note': '年度例假；臨時休市需維護config/market-calendar.json，不以猜測補行情'}
def configured():
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    p=root/'config/market-calendar.json'
    if p.exists():
        try:
            data=json.loads(p.read_text())
            if all(k in data for k in ('start','end','closed')):return data
        except (ValueError,OSError):pass
    return SEED

def parse_time(value):
    d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return (d if d.tzinfo else d.replace(tzinfo=TZ)).astimezone(TZ)
def is_session(day,calendar=None):
    c=calendar or configured();d=date.fromisoformat(str(day)[:10])
    return d.weekday()<5 and d.isoformat() not in c.get('closed',[])
def covered(day,calendar=None):
    c=calendar or configured();return c['start']<=str(day)[:10]<=c['end']
def clock(day,hour=9,minute=0):
    return datetime.combine(date.fromisoformat(day),time(hour,minute),tzinfo=TZ)
def expected_close(at,calendar=None):
    t=parse_time(at);d=t.date()
    if t.time()<time(13,30):d-=timedelta(days=1)
    for _ in range(30):
        if is_session(d.isoformat(),calendar):return d.isoformat()
        d-=timedelta(days=1)
    raise ValueError('calendar has no usable session')
def future_sessions(at,count=25,calendar=None):
    t=parse_time(at);d=t.date();out=[]
    for _ in range(150):
        day=d.isoformat()
        if is_session(day,calendar) and clock(day)>t:out.append(day)
        if len(out)>=count:return out
        d+=timedelta(days=1)
    return out
