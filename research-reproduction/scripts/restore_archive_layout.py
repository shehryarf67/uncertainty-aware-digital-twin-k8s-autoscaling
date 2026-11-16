"""Restore deduplicated paths without replacing files or leaving the root."""
from pathlib import Path
import json,hashlib,os,shutil
ROOT=Path(__file__).resolve().parents[1]
def checked(name):
    p=(ROOT/name).resolve()
    if not p.is_relative_to(ROOT.resolve()):raise ValueError(f'Unsafe archive path {name}')
    return p
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
data=json.loads((ROOT/'archive-layout-aliases.json').read_text())
for name,item in data.items():
    target=checked(name);source=checked(item['source']);assert digest(source)==item['sha256']
    if target.exists():
        if digest(target)!=item['sha256']:raise FileExistsError(f'Conflicting existing file {target}')
        continue
    target.parent.mkdir(parents=True,exist_ok=True)
    try:os.link(source,target)
    except OSError:shutil.copy2(source,target)
print(f'Restored or verified {len(data)} duplicate paths')
