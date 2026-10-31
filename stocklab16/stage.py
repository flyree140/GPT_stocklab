"""Build a Pages folder using relative URLs (also under /GPT_stocklab/).
Never publishes Qwen state, credentials, Python source or diagnostic caches.
"""
from pathlib import Path
import shutil,argparse
from .common import ROOT,read_json,write_json

def stage(root=ROOT,target=None):
    root=Path(root);target=Path(target or root/'_site')
    if target==root or root.is_relative_to(target):raise ValueError('Invalid stage destination')
    if target.exists():shutil.rmtree(target)
    target.mkdir(parents=True)
    for file in ['index.html','research.html','tutorial.html','audit.html','planner.html','.nojekyll','BUILD_REPORT.md']:
        shutil.copy2(root/file,target/file)
    for file in ['lab.html','lab-guide.html','life19.html','model192.html','guide192.html','guide193.html','developer1932.html','pipeline1932.html']:
        if (root/file).exists():shutil.copy2(root/file,target/file)
    shutil.copytree(root/'assets',target/'assets')
    # Runtime calendar may extend a known year; the refresh job rejects past-day changes.
    verified=read_json(root/'data/calendar/latest.json',{}) or {}
    if verified.get('start') and verified.get('end') and isinstance(verified.get('closed'),list):
        write_json(target/'assets/paper-calendar.json',verified)
    if (root/'cloud-setup.html').exists():shutil.copy2(root/'cloud-setup.html',target/'cloud-setup.html')
    if (root/'cloud-config.json').exists():
        cfg=read_json(root/'cloud-config.json',{}) or {}
        write_json(target/'cloud-config.json',{'client_id':str(cfg.get('client_id',''))})
    if (root/'data').is_dir():
        shutil.copytree(root/'data',target/'data',ignore=shutil.ignore_patterns('system','features192','.cache','qwen_cache.json','*token*','*secret*','private','ledger-backups','*私人帳本*','*實際流水*'))
    manifest=read_json(root/'data/manifest.json',{}) or {}
    production=bool(manifest.get('snapshots'))
    write_json(target/'runtime.json',{'version':'19.3.2','mode':'production' if production else 'demo','deployment':'github-pages'})
    return target
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output');args=p.parse_args();print(stage(target=args.output))
