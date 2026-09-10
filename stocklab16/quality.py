from __future__ import annotations
import json, subprocess
from pathlib import Path
from .common import ROOT

def main():
    errors=[]
    required=['index.html','assets/app.mjs','assets/styles.css','assets/charts.mjs','assets/engine.mjs','data/latest.json','data/manifest.json','data/universe.json','config/stocks.json']
    for rel in required:
        p=ROOT/rel
        if not p.exists() or p.stat().st_size==0: errors.append('missing '+rel)
    for base in [ROOT/'data',ROOT/'config']:
        for p in base.rglob('*.json'):
            try:json.loads(p.read_text(encoding='utf-8'))
            except Exception as e:errors.append(f'invalid json {p.relative_to(ROOT)}: {e}')
    for rel in ['assets/app.mjs','assets/charts.mjs','assets/engine.mjs']:
        try: subprocess.run(['node','--check',str(ROOT/rel)],check=True,capture_output=True,text=True)
        except Exception as e: errors.append(f'js syntax {rel}: {e}')
    if errors:
        print('QUALITY FAILED');[print('-',e) for e in errors];raise SystemExit(1)
    print('QUALITY PASSED')
if __name__=='__main__':main()
