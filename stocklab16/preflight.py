"""Skip only the scheduled backup when today already has a successful live snapshot."""
import os
from .common import ROOT,read_json,now
if __name__=='__main__':
    p=read_json(ROOT/'data/latest.json',{}) or {}
    backup=os.getenv('GITHUB_EVENT_NAME')=='schedule' and os.getenv('TRIGGER_SCHEDULE')=='17 13 * * *'
    skip=backup and p.get('as_of')==now().date().isoformat() and p.get('mode')=='live' and bool(p.get('stocks'))
    value='true' if skip else 'false'
    print('skip='+value)
    out=os.getenv('GITHUB_OUTPUT')
    if out:
        with open(out,'a') as f:f.write('skip='+value+'\n')
