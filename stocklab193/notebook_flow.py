"""A (CPU) -> Drive handoff -> B (GPU). No reliance on A's in-memory variables."""
from __future__ import annotations
import json,re,hashlib,os,tempfile
from pathlib import Path
from datetime import datetime,timezone
from stocklab192.schema import load_jsonl,save_jsonl,check_record,digest,timestamp
from stocklab192.prepare import split_records
from stocklab192.train import validate_parts,budget_for

def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def jsonwrite(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf8',dir=path.parent,delete=False) as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);temp=Path(f.name)
    temp.replace(path)

def auto_boundaries(rows):
    dates=sorted({timestamp(r['decision_at']).isoformat() for r in rows})
    if len(dates)<6:raise ValueError('正式教材至少需要6個不同時點供時間切分；請增加獨立事件。不可用隨機切分藏住重複事件。')
    a=max(0,int(len(dates)*.70)-1);b=max(a+1,int(len(dates)*.85)-1)
    return dates[a],dates[b],dates[-1]

def prepare_job(project,job,source,profile,program_sha,boundaries=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',job):raise ValueError('JOB_NAME只用英文、數字、底線、連字號')
    if profile not in ('smoke','reviewed'):raise ValueError('unknown profile')
    project=Path(project).resolve();target=project/'jobs'/job;rows=load_jsonl(source)
    errors=[{'id':r.get('id'),'errors':check_record(r,True)} for r in rows if check_record(r,True)]
    if errors:
        jsonwrite(project/'validation_errors.json',errors)
        raise ValueError(f'{len(errors)}筆教材有錯誤，請看validation_errors.json。CPU已停止，勿開GPU。')
    if profile=='reviewed' and any(r.get('synthetic') for r in rows):raise ValueError('正式教材混入合成資料；不允許發佈教學權重')
    if boundaries is None:
        boundaries=('2025-01-17T23:59:59+08:00','2025-01-21T23:59:59+08:00','2025-01-26T23:59:59+08:00') if profile=='smoke' else auto_boundaries(rows)
    parts,report=split_records(rows,*boundaries,allow_synthetic=profile=='smoke');validate_parts(parts,profile=='smoke')
    budget=budget_for(profile)
    if len(parts['train'])>budget['max_records']:raise ValueError(f'訓練有{len(parts["train"])}筆，超過本輪{budget["max_records"]}筆。先選定有代表性的事件，不自動偷偷刪樣本。')
    identity={'profile':profile,'program_sha256':program_sha,'source_sha256':file_sha(source),'dataset_sha256':{k:digest(v) for k,v in parts.items()},'boundaries':report['boundaries']}
    ready_path=target/'READY.json'
    if ready_path.exists():
        old=json.loads(ready_path.read_text())
        if old.get('identity')!=identity:raise ValueError('這個JOB_NAME已有不同教材或程式；請用新的名稱，不覆寫舊實驗')
        verify_job(ready_path,program_sha)
        jsonwrite(project/'LAST_READY.json',{'path':str(ready_path)})
        return old
    target.mkdir(parents=True,exist_ok=True);data=target/'data'
    for k,v in parts.items():save_jsonl(data/(k+'.jsonl'),v)
    report['dataset_sha256']=identity['dataset_sha256'];jsonwrite(data/'split_report.json',report)
    ready={'version':'19.3','status':'ready','job':job,'profile':profile,'data_dir':str(data),'run_dir':str(target/'run'),
      'identity':identity,'file_hashes':{k:file_sha(data/(k+'.jsonl')) for k in parts},'counts':report['counts'],
      'budget':budget,'created_at':datetime.now(timezone.utc).isoformat(),
      'synthetic_smoke_only':profile=='smoke','accuracy_validated':False,'profitability_validated':False,
      'note':'結構通過不代表標準答案必然正確。B會再次核對hash；不需上傳程式資料夾。'}
    jsonwrite(ready_path,ready);jsonwrite(project/'LAST_READY.json',{'path':str(ready_path)});return ready

def ready_location(project,job=''):
    project=Path(project).resolve()
    if job:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',job):raise ValueError('無效JOB_NAME')
        p=project/'jobs'/job/'READY.json'
    else:
        pointer=project/'LAST_READY.json'
        if not pointer.exists():raise ValueError('Drive還沒有A準備好的教材；先完成A。不是要上傳StockLab192資料夾。')
        p=Path(json.loads(pointer.read_text())['path']).resolve()
    if not p.is_relative_to(project):raise ValueError('拒絕跨出你的訓練專案路徑')
    return p

def verify_job(ready_path,program_sha):
    p=Path(ready_path);ready=json.loads(p.read_text())
    if ready.get('status')!='ready':raise ValueError('A尚未完成資料檢查')
    if ready['identity']['program_sha256']!=program_sha:raise ValueError('A與B不是同一套程式版本，請使用同一發布包的A和B')
    base=p.parent.resolve();data=Path(ready['data_dir']).resolve();run=Path(ready['run_dir']).resolve()
    if not data.is_relative_to(base) or not run.is_relative_to(base):raise ValueError('教材或權重路徑不符')
    parts={}
    for k in ('train','validation','test'):
        f=data/(k+'.jsonl')
        if file_sha(f)!=ready['file_hashes'][k]:raise ValueError(k+'教材已變更；不要沿用舊READY，請重新建立不同JOB_NAME')
        parts[k]=load_jsonl(f)
        if digest(parts[k])!=ready['identity']['dataset_sha256'][k]:raise ValueError('dataset semantic hash mismatch')
    validate_parts(parts,ready['profile']=='smoke');return ready

def audit_checkpoint_manifest(ready):
    run=Path(ready['run_dir']);manifest=run/'run_manifest.json'
    if not manifest.exists():return 'new'
    old=json.loads(manifest.read_text())
    if old.get('training_data_sha256')!=ready['identity']['dataset_sha256']:raise ValueError('舊權重與目前教材不符，不自動續訓')
    if old.get('training_finished') and (run/'adapter/stocklab_manifest.json').exists():return 'completed'
    checkpoints=list((run/'checkpoints').glob('checkpoint-*/trainer_state.json'))
    if not checkpoints:raise ValueError('上次未完成且沒有checkpoint。不要重覆亂跑；以新JOB_NAME重新A準備後再B。')
    return 'resume'
