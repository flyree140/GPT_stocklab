"""Offline clean-extract, HTTP route and non-destructive overlay acceptance.
No live financial data or credentials are used. Historical v16 release fixture
provided with --old-zip is only copied into a temporary directory.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,tempfile,threading,zipfile,shutil,re
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urljoin,urlparse

SKIP={'.git','.cache','__pycache__','.pytest_cache','.venv','_site'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def files(root):
 return [p for p in sorted(root.rglob('*')) if p.is_file() and not any(x in SKIP for x in p.relative_to(root).parts)]
def run(cmd,cwd):
 p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=120)
 result={'command':' '.join(cmd),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 if p.returncode:raise AssertionError(result)
 return result
class QuietHandler(SimpleHTTPRequestHandler):
 def log_message(self,*a):pass

def http_checks(root,tmp):
 site=Path(tmp)/'http-root'/'GPT_stocklab';run([sys.executable,'-m','stocklab16.stage','--output',str(site)],root)
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(site.parent)))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 base=f'http://127.0.0.1:{server.server_port}/GPT_stocklab/'
 tested=[]
 def get(path):
  url=urljoin(base,path)
  with urlopen(url,timeout=5) as response:
   assert response.status==200,(path,response.status);body=response.read();tested.append({'path':path,'status':response.status,'bytes':len(body)});return body
 try:
  html=get('index.html').decode();tutorial=get('tutorial.html').decode();get('runtime.json');get('assets/styles.css');get('assets/favicon.svg')
  assert 'tutorial.html' in html;assert 'learn-eps' in tutorial
  for module in ['app.mjs','charts.mjs','engine.mjs']:get('assets/'+module)
  # Every local tutorial link, imports, and CSS/script link must resolve.
  for path in re.findall(r'(?:src|href)="([^"]+)"',html):
   if path.startswith('#') or urlparse(path).scheme:continue
   get(path.split('#')[0])
  for path in re.findall(r"from\s+['\"](\./[^'\"]+)['\"]",(site/'assets/app.mjs').read_text()):get('assets/'+path[2:])
  runtime=json.loads((site/'runtime.json').read_text());prefix='data/' if runtime['mode']=='production' else 'data/demo/'
  manifest=json.loads(get(prefix+'manifest.json'))
  for row in manifest['snapshots']:
   data=get(row['path']);obj=json.loads(data);assert obj['as_of']==row['date']
   if row.get('sha256'):assert hashlib.sha256(data).hexdigest()==row['sha256']
  # Private API key/quota cache is absent from the Pages directory.
  assert not (site/'data/system').exists()
  try:get('data/system/qwen-state.json');raise AssertionError('private state published')
  except HTTPError as exc:assert exc.code==404
  return {'passed':True,'runtime_mode':runtime['mode'],'base_path':'/GPT_stocklab/','routes':tested,'private_state_status':404}
 finally:server.shutdown();server.server_close();thread.join(timeout=3)

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--old-zip',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args();r=args.root.resolve()
 protected_prefixes=['data/latest.json','data/manifest.json','data/market/','data/snapshots/','config/stocks.json','config/settings.json']
 archive_conflicts=[f.relative_to(r).as_posix() for f in files(r) if any(f.relative_to(r).as_posix()==q or f.relative_to(r).as_posix().startswith(q) for q in protected_prefixes)]
 assert not archive_conflicts,archive_conflicts
 report={'scope':'offline release and existing v16 fixture overlay','no_production_overwrites_in_package':True,'source_checks':[]}
 for cmd in [[sys.executable,'-m','stocklab16.quality'],[sys.executable,'-m','pytest','-q'],['node','tests/test_engine.mjs']]:report['source_checks'].append(run(cmd,r))
 with tempfile.TemporaryDirectory(prefix='stocklab-package-') as tmp:
  tmp=Path(tmp);report['fresh_site_http']=http_checks(r,tmp/'fresh')
  if args.old_zip:
   old=tmp/'existing-v16';old.mkdir()
   with zipfile.ZipFile(args.old_zip) as z:
    assert z.testzip() is None
    for name in z.namelist():
     target=(old/name).resolve();assert target.is_relative_to(old.resolve()),'unsafe fixture'
    z.extractall(old)
   protected={f.relative_to(old).as_posix():sha(f) for f in files(old) if f.relative_to(old).parts[0] in {'data','config'}}
   snapshots={p:h for p,h in protected.items() if p.startswith('data/snapshots/')};markets={p:h for p,h in protected.items() if p.startswith('data/market/')};configs={p:h for p,h in protected.items() if p.startswith('config/')}
   for f in files(r):
    dest=old/f.relative_to(r);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
   changed=[p for p,h in protected.items() if not (old/p).is_file() or sha(old/p)!=h]
   assert not changed,changed
   initial_manifest=json.loads((old/'data/manifest.json').read_text());report['overlay']={'existing_fixture':args.old_zip.name,'protected_files':len(protected),'changed_on_overlay':changed}
   report['migration_command']=run([sys.executable,'-m','stocklab16.migrate'],old)
   migration=json.loads((old/'data/system/migration-report.json').read_text())
   report['migration']={'rows':migration['rows'],'original_snapshots':len(snapshots),'unchanged_original_snapshots':all(sha(old/p)==h for p,h in snapshots.items()),'unchanged_market_histories':all(sha(old/p)==h for p,h in markets.items()),'unchanged_custom_configuration':all(sha(old/p)==h for p,h in configs.items())}
   assert report['migration']['unchanged_original_snapshots'];assert report['migration']['unchanged_market_histories'];assert report['migration']['unchanged_custom_configuration'];assert any(x['status']=='recomputed' for x in migration['rows'])
   newer=json.loads((old/'data/manifest.json').read_text());assert newer['latest']==initial_manifest['latest']
   for row in migration['rows']:
    if row['status']=='recomputed':assert json.loads((old/row['result']).read_text())['mode']=='retrospective_reanalysis'
   report['existing_data_checks']=[run([sys.executable,'-m','stocklab16.quality'],old),run([sys.executable,'-m','pytest','-q'],old)]
   report['production_site_http']=http_checks(old,tmp/'production')
 report['passed']=True;args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':True,'overlay':report.get('overlay'), 'http_route_count':sum(len(v.get('routes',[])) for v in report.values() if isinstance(v,dict))},ensure_ascii=False))
if __name__=='__main__':main()
