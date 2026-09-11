from __future__ import annotations
import hashlib, json, math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

VERSION='16.1.2'
ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo('Asia/Taipei')

def now(): return datetime.now(TZ)
def dt(value):
    if isinstance(value, datetime): return value
    text=str(value or '').strip()
    if not text: raise ValueError('empty datetime')
    parsed=datetime.fromisoformat(text.replace('Z','+00:00'))
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=TZ)
    return parsed

def number(value, default=None):
    try:
        if value in (None,''): return default
        x=float(value)
        return default if math.isnan(x) or math.isinf(x) else x
    except Exception: return default

def clamp(value, lo=0, hi=100): return max(lo,min(hi,float(value)))
def digest(parts): return hashlib.sha256('|'.join(map(str,parts)).encode()).hexdigest()
def read_json(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception: return default

def write_json(path, data):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    import os, tempfile
    payload=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=p.parent,delete=False) as f:
        f.write(payload); tmp=Path(f.name)
    os.replace(tmp,p)
