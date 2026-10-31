"""Each scheduled window runs once. The evening window is NOT skipped by the earlier run."""
import os
from datetime import datetime
from .common import ROOT,read_json,now

def already_completed(snapshot,schedule,current):
    if snapshot.get('mode')!='live' or not snapshot.get('stocks') or snapshot.get('as_of')!=current.date().isoformat():return False
    windows={'17 0 * * *':817,'37 10 * * *':1837,'17 13 * * *':2117}
    if schedule not in windows:return False
    try:
        stamp=datetime.fromisoformat(str(snapshot['generated_at']).replace('Z','+00:00')).astimezone(current.tzinfo)
    except (KeyError,ValueError):return False
    return stamp.date()==current.date() and stamp.hour*100+stamp.minute>=windows[schedule]

if __name__=='__main__':
    snap=read_json(ROOT/'data/latest.json',{}) or {}
    skip=os.getenv('GITHUB_EVENT_NAME')=='schedule' and already_completed(snap,os.getenv('TRIGGER_SCHEDULE'),now())
    value='true' if skip else 'false';print('skip='+value)
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('skip='+value+'\n')
