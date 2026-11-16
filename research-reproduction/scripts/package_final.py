"""Non-destructive, byte-deduplicated final package with integrity checks."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'base-article-reproduction-20261009.zip'
if out.exists():raise FileExistsError('Preserve existing archive; select a new filename before another packaging run')
assert json.loads((ROOT/'final-report/quality-assurance.json').read_text())['status']=='passed'
assert (ROOT/'final-report/base-article-reproduction-report.pdf').is_file()
excluded={'archive-layout-aliases.json','final-artifact-manifest.json','package-summary.json'}
def include(p):
    r=p.relative_to(ROOT)
    if not p.is_file() or p.name in excluded or p.suffix=='.zip':return False
    if '__pycache__' in r.parts or '.ipynb_checkpoints' in r.parts:return False
    if r.parts[0]=='environments' and any(x.endswith('-venv') or x=='jupyter' for x in r.parts):return False
    if r.parts[:2]==('final-report','qa'):return False
    if p.name=='kubeconfig.yaml' or p.suffix in ['.sock','.db','.db-journal']:return False
    return True
paths=sorted((p for p in ROOT.rglob('*') if include(p)),key=lambda p:(not str(p.relative_to(ROOT)).startswith('baseline-original'),str(p)))
manifest={};aliases={};canonical={};unique=[]
for p in paths:
    name=p.relative_to(ROOT).as_posix();sha=hashlib.sha256(p.read_bytes()).hexdigest()
    manifest[name]={'bytes':p.stat().st_size,'sha256':sha}
    if sha in canonical:aliases[name]={'source':canonical[sha],'sha256':sha}
    else:canonical[sha]=name;unique.append(p)
(ROOT/'archive-layout-aliases.json').write_text(json.dumps(aliases,indent=2))
(ROOT/'final-artifact-manifest.json').write_text(json.dumps(manifest,indent=2))
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in unique+[ROOT/'archive-layout-aliases.json',ROOT/'final-artifact-manifest.json']:
        z.write(p,'research-reproduction/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for name,m in manifest.items():
        stored=aliases.get(name,{}).get('source',name)
        assert hashlib.sha256(z.read('research-reproduction/'+stored)).hexdigest()==m['sha256'],name
summary={'path':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'logical_files':len(paths),'unique_payload_files':len(unique),'duplicate_paths':len(aliases),'duplicate_bytes_avoided':sum(manifest[p]['bytes'] for p in aliases),'archive_all_payload_hashes_verified':True,'old_archive_preserved':True}
(ROOT/'final-report/package-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
