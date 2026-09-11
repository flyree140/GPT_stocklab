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
    for file in ['index.html','tutorial.html','.nojekyll']:
        shutil.copy2(root/file,target/file)
    shutil.copytree(root/'assets',target/'assets')
    if (root/'data').is_dir():
        shutil.copytree(root/'data',target/'data',ignore=shutil.ignore_patterns('system','.cache','qwen_cache.json','*token*','*secret*'))
    manifest=read_json(root/'data/manifest.json',{}) or {}
    production=bool(manifest.get('snapshots'))
    write_json(target/'runtime.json',{'version':'16.1.2','mode':'production' if production else 'demo','deployment':'github-pages'})
    return target
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output');args=p.parse_args();print(stage(target=args.output))
