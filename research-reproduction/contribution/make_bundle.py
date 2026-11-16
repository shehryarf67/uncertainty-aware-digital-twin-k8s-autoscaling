"""Create a new handoff without overwriting the preserved baseline archive."""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
OUT=BASE/'research-paper-and-code-20261028.zip'

def main():
    assert json.loads((ROOT/'verification.json').read_text())['status']=='passed'
    assert (ROOT/'paper/research-article.pdf').exists()
    manifest={}
    with zipfile.ZipFile(BASE/'base-article-reproduction-20261009.zip') as old:
        # Preserve the prior official-source snapshot, including its hashed Git
        # identity files. Exact duplicates retain their existing alias mapping.
        files={n:old.read(n) for n in old.namelist() if not n.endswith('/')}
    # Current analysis and its exact input files supersede their archived copies.
    for folder in ['corrected-evaluation','reports']:
        for p in (BASE/folder).rglob('*'):
            if p.is_file() and not any(x in p.parts for x in ['__pycache__','.venv','.git']):
                files['research-reproduction/'+p.relative_to(BASE).as_posix()]=p.read_bytes()
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ['__pycache__','page-previews']):continue
        if p.suffix.lower() in ['.pyc'] or p.name=='bundle-manifest.json':continue
        files['research-reproduction/'+p.relative_to(BASE).as_posix()]=p.read_bytes()
    # Explicitly prevent accidental inclusion of authentication material.
    assert not any('kubeconfig' in n.lower() or '/.venv/' in n for n in files)
    for name,data in files.items():
        assert not name.startswith('/') and '..' not in Path(name).parts
        manifest[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    (ROOT/'bundle-manifest.json').write_text(json.dumps(manifest,indent=2))
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,data in sorted(files.items()):z.writestr(name,data)
        z.write(ROOT/'bundle-manifest.json','research-reproduction/contribution/bundle-manifest.json')
    with zipfile.ZipFile(OUT) as z:
        assert z.testzip() is None
        for name,record in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==record['sha256']
    print(json.dumps({'path':str(OUT),'files':len(files)+1,'bytes':OUT.stat().st_size,'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest()},indent=2))

if __name__=='__main__':main()
