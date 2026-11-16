"""Package source and evidence; exclude installed runtime and transient caches."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def include(path):
    rel = path.relative_to(ROOT)
    if path.suffix == '.zip' or '__pycache__' in rel.parts:
        return False
    if len(rel.parts)>1 and rel.parts[:2] in [('environments','forecast-venv'),('environments','jupyter')]:
        return False
    return path.is_file()


def main():
    verification = json.loads((ROOT/'reports'/'verification.json').read_text(encoding='utf-8'))
    assert verification['status']=='passed'
    paths = [p for p in ROOT.rglob('*') if include(p) and p.name!='artifact-manifest.json']
    manifest = {str(p.relative_to(ROOT)).replace('\\','/'):
                {'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(paths)}
    manifest_path = ROOT/'reports'/'artifact-manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    output = ROOT/'prophet-lstm-reproduction.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths+[manifest_path]:
            z.write(p,arcname='research-reproduction/'+str(p.relative_to(ROOT)).replace('\\','/'))
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
    print(json.dumps({'path':str(output),'bytes':output.stat().st_size,
                      'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'n_files':len(paths)+1},indent=2))


if __name__ == '__main__':
    main()
