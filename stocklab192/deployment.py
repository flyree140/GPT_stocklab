"""Pinned safetensors-only adapter package. No pickle weights, no remote code."""
from pathlib import Path
import json,hashlib,re
from .schema import MODEL_ID,MODEL_REVISION,SCHEMA_VERSION,prompt_hash
ALLOWED={'adapter_model.safetensors','adapter_config.json','stocklab_manifest.json'}

def validate_adapter(path,allow_smoke=False):
    p=Path(path)
    for name in ALLOWED:
        if not (p/name).is_file() or (p/name).is_symlink():raise ValueError('adapter missing/unsafe '+name)
    m=json.loads((p/'stocklab_manifest.json').read_text());c=json.loads((p/'adapter_config.json').read_text())
    if m.get('model')!=MODEL_ID or m.get('revision')!=MODEL_REVISION:raise ValueError('base revision mismatch')
    if m.get('schema')!=SCHEMA_VERSION or m.get('prompt_sha256')!=prompt_hash():raise ValueError('schema/prompt mismatch')
    if m.get('synthetic_smoke_only') and not allow_smoke:raise ValueError('synthetic smoke adapter cannot enter website research')
    if not m.get('training_finished'):raise ValueError('training incomplete')
    if c.get('peft_type')!='LORA' or c.get('task_type')!='CAUSAL_LM':raise ValueError('only LoRA causal LM allowed')
    if c.get('base_model_name_or_path')!=MODEL_ID:raise ValueError('adapter base mismatch')
    if not isinstance(c.get('r'),int) or not 1<=c['r']<=16:raise ValueError('unsupported adapter rank')
    if set(c.get('target_modules',[]))-{'q_proj','v_proj'} or not c.get('target_modules'):raise ValueError('unsupported targets')
    if c.get('modules_to_save') or c.get('bias') not in ('none',None):raise ValueError('unexpected full parameter modules')
    size=sum((p/n).stat().st_size for n in ALLOWED)
    if size>80*1024**2:raise ValueError('adapter exceeds 80MiB')
    digest=hashlib.sha256((p/'adapter_model.safetensors').read_bytes()).hexdigest()
    if digest!=m.get('adapter_sha256'):raise ValueError('adapter weights hash mismatch')
    return m

def download_adapter(repo,revision,root):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('HF repo must be owner/name')
    if not re.fullmatch(r'[0-9a-f]{40}',revision):raise ValueError('adapter revision must be immutable 40-character commit SHA')
    from huggingface_hub import HfApi,snapshot_download
    info=HfApi().model_info(repo,revision=revision,files_metadata=True)
    sizes={x.rfilename:x.size for x in info.siblings if x.rfilename in ALLOWED}
    if set(sizes)!=ALLOWED or any(x is None for x in sizes.values()) or sum(sizes.values())>80*1024**2:raise ValueError('remote adapter missing/too large')
    local=snapshot_download(repo,revision=revision,allow_patterns=sorted(ALLOWED),local_dir=str(root))
    validate_adapter(local);return Path(local)

def publish(adapter,repo,*,permission_confirmed=False):
    if not permission_confirmed:raise ValueError('先確認訓練資料與衍生權重允許此使用；預設不發布')
    m=validate_adapter(adapter)
    from huggingface_hub import HfApi
    api=HfApi();api.create_repo(repo_id=repo,private=True,exist_ok=True)
    # Existing public repo is not silently made private: require private before upload.
    if not api.model_info(repo).private:raise ValueError('先建立私人模型repo；不要意外公開adapter')
    api.upload_folder(repo_id=repo,folder_path=str(adapter),allow_patterns=sorted(ALLOWED),commit_message='StockLab19.2 reviewed evidence LoRA (shadow only)')
    sha=api.model_info(repo).sha
    return {'STOCKLAB_ADAPTER_REPO':repo,'STOCKLAB_ADAPTER_REVISION':sha,'STOCKLAB_192_ENABLED':'1','HF_TOKEN':'GitHub Secret: read-only token for this repo; never paste in code'}
