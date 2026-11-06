"""Current global sidecars. No trade/ledger mutations; network bounded and optional."""
from __future__ import annotations
import argparse, hashlib
from pathlib import Path
from stocklab16.common import now, dt, read_json, write_json
from .global_sources import GlobalCollector, VERSION
from .global_rules import assemble

def run(root,collector=None,clock=None,network=True):
 root=Path(root);clock=clock or now;start=clock();src=root/'data/latest.json'
 snap=read_json(src,{}) or {}
 if not snap:raise ValueError('缺正式 data/latest.json，不以示範替代')
 if snap.get('demo'):raise ValueError('正式更新拒絕合成快照')
 if dt(snap['generated_at'])>start:raise ValueError('future_source_snapshot')
 source_hash=hashlib.sha256(src.read_bytes()).hexdigest()
 cfg=read_json(root/'config/global-research.json',{}) or {}
 collector=collector or GlobalCollector(root,clock=clock)
 if network:
  quotes,events=collector.collect()
 else:
  quotes=[];events=[]
 # Explicit local exposure evidence is optional; never silently invented from a ticker.
 profiles=read_json(root/'config/global-exposures.json',{}) or {}
 cutoff=clock().isoformat();payload=assemble(quotes,events,snap.get('stocks',[]),cutoff,profiles)
 payload.update(version=VERSION,mode='current_global_research',demo=False,source_snapshot_sha256=source_hash,
    source_snapshot_at=snap['generated_at'],collection=collector.report(),network_requested=network,
    rules_version='global-research-v1-unvalidated')
 directory=root/'data/global194/runs';stamp=clock().strftime('%Y%m%dT%H%M%S%f')
 dest=directory/(stamp+'.json')
 if dest.exists():raise FileExistsError(dest)
 write_json(dest,payload);write_json(root/'data/global194/latest.json',payload)
 return payload

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--no-network',action='store_true');a=p.parse_args()
 result=run(Path(a.root).resolve(),network=not a.no_network)
 print('Global sidecar:',result['generated_at'],result['coverage'],result['risk']['code'])
