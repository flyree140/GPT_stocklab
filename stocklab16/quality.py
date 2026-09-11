"""Offline release checks. Never scan third-party model caches as application JSON."""
from pathlib import Path
import json,subprocess,hashlib,re,tempfile
from .common import ROOT,read_json
from .storage import validate_snapshot,settings_file

def check(root=ROOT):
    root=Path(root);errors=[]
    required=['index.html','tutorial.html','assets/app.mjs','assets/styles.css','assets/charts.mjs','assets/engine.mjs',
              'stocklab16/taxonomy.py','runtime.json','data/demo/latest.json','data/demo/manifest.json',
              'config/stocks.default.json','config/settings.default.json']
    for rel in required:
        p=root/rel
        if not p.is_file() or not p.stat().st_size:errors.append('missing: '+rel)
    count=0
    for directory in ['data','config']:
        for p in (root/directory).rglob('*.json'):
            if '.cache' in p.parts or p.is_symlink():continue
            try:json.loads(p.read_text());count+=1
            except Exception as e:errors.append(f'JSON {p.relative_to(root)}: {e}')
    for prefix in ['data','data/demo']:
        manifest=read_json(root/prefix/'manifest.json',{}) or {}
        for row in manifest.get('snapshots',[]):
            for r in [row]+row.get('runs',[]):
                rel=r.get('path','');p=(root/rel).resolve()
                if not rel or not p.is_relative_to(root.resolve()) or not p.is_file():errors.append('manifest path missing/unsafe '+rel);continue
                if r.get('sha256') and hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:errors.append('hash mismatch '+rel)
                payload=read_json(p,{}) or {}
                if str(payload.get('version','')).startswith('16.1'):
                    errors.extend(rel+': '+e for e in validate_snapshot(payload))
    for p in (root/'assets').glob('*.mjs'):
        try:
            r=subprocess.run(['node','--check',str(p)],capture_output=True,text=True,timeout=15)
            if r.returncode:errors.append(r.stderr)
        except Exception as e:errors.append('Node check '+str(e))
    html=(root/'tutorial.html').read_text()
    for code in re.findall(r'<script[^>]*>(.*?)</script>',html,re.S):
        with tempfile.NamedTemporaryFile('w',suffix='.js',encoding='utf-8') as f:
            f.write(code);f.flush();r=subprocess.run(['node','--check',f.name],capture_output=True,text=True,timeout=15)
            if r.returncode:errors.append('tutorial script '+r.stderr)
    return {'ok':not errors,'errors':errors,'json_count':count}

def main():
    r=check();print(json.dumps(r,ensure_ascii=False,indent=2))
    if not r['ok']:raise SystemExit(1)
if __name__=='__main__':main()
