"""Create a shareable source/input bundle without changing experiment evidence."""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'partner-code-20261010.zip'
if OUT.exists():raise FileExistsError(OUT)

README=r'''# Partner code handoff

This bundle contains the code used for Guruge and Priyadarshana (2025) reproduction: untouched author notebooks, separate causal forecasting scripts, author application and scaler source, K3s/KEDA/HPA configuration, workload generator, dependency locks, supplied minute-count datasets and released model checkpoints. The accompanying report explains the executed results and methodological limitations.

Large experiment outputs, installed environments, Git history, compiled Java artifacts and live databases are omitted. This is a source/input handoff; use the separate complete reproduction archive for original executed notebooks, logs and prediction CSVs. No new uncertainty-aware Digital Twin or novel controller is implemented.

## Start here

Extract the ZIP and open PowerShell in its `research-reproduction` directory. Python 3.12 on Windows is the validated forecasting platform. Restore deduplicated file paths before running anything:

```powershell
python scripts/restore_archive_layout.py
python -m venv environments/forecast-venv
& environments/forecast-venv/Scripts/python.exe -m pip install -r environments/requirements-working.txt
& environments/forecast-venv/Scripts/python.exe -m pip check
```

Identical datasets and checkpoint models are stored once. The restoration command uses hard links where possible and copies otherwise; it refuses conflicting files.

Run the faithful author calculation or the separately labelled correction, using new run IDs:

```powershell
& environments/forecast-venv/Scripts/python.exe scripts/run_baseline.py --dataset nasa --run-id partner-01
& environments/forecast-venv/Scripts/python.exe scripts/run_baseline.py --dataset fifa --run-id partner-01
& environments/forecast-venv/Scripts/python.exe scripts/run_corrected.py --dataset nasa --run-id partner-01
& environments/forecast-venv/Scripts/python.exe scripts/run_corrected.py --dataset fifa --run-id partner-01
& environments/forecast-venv/Scripts/python.exe scripts/verify_corrected.py
& environments/forecast-venv/Scripts/python.exe scripts/plot_forecast_comparison.py
```

These command forms and scripts were executed in the original project; `partner-01` is a suggested new output ID, not a pre-existing run. Run sequentially. Full-run QA/report packaging scripts require original or newly generated results; they are not expected to pass immediately in this source-only bundle. `verify_final.py` additionally refers to the surrounding original audit repositories. Git-based source verification requires cloning the recorded author revision because Git history is omitted here.

## Kubernetes

Use WSL2 Ubuntu 24.04 with systemd. The recorded deployment used standalone K3s/containerd, not Docker Desktop Kubernetes. Installation commands require root and network access. Build the original Java source before deploying because the compiled JAR is omitted:

```powershell
$linuxRoot = (wsl -d Ubuntu -- wslpath -a $PWD.Path).Trim()
Start-Process wsl.exe -ArgumentList '-d','Ubuntu','--','sleep','7200' -WindowStyle Hidden
wsl -d Ubuntu -u root -- bash "$linuxRoot/scripts/install_k3s_local.sh"
wsl -d Ubuntu -u root -- /opt/guruge-reproduction/bin/k3s kubectl --kubeconfig /opt/guruge-reproduction/kubeconfig.yaml wait --for=condition=Ready node/guruge-local --timeout=180s
wsl -d Ubuntu -u root -- bash "$linuxRoot/scripts/build_author_app.sh"
wsl -d Ubuntu -u root -- bash "$linuxRoot/scripts/deploy_k3s_stack.sh"
wsl -d Ubuntu -u root -- bash "$linuxRoot/scripts/start_linux_scaler.sh"
$nodeIP = (wsl -d Ubuntu -u root -- hostname -I).Trim().Split(' ')[0]
& environments/forecast-venv/Scripts/python.exe scripts/run_cluster_scenarios.py --controller forecast --run-id partner-01 --phase-seconds 30 --warmup-seconds 60 --url "http://${nodeIP}:30080"
& environments/forecast-venv/Scripts/python.exe scripts/run_cluster_scenarios.py --controller hpa --run-id partner-01 --phase-seconds 30 --warmup-seconds 60 --url "http://${nodeIP}:30080"
& environments/forecast-venv/Scripts/python.exe scripts/summarize_cluster.py --run-id partner-01
wsl -d Ubuntu -u root -- systemctl stop guruge-scaler guruge-k3s
```

Individual setup components were executed successfully; the revised fresh-install sequence was not independently exercised on a second computer. Generated hostPath/node addresses must be regenerated for your extraction location using the build/start scripts. Keep services running and WSL alive during experiments. Windows and Linux dependency locks are separate. Author scaler numerical logic is unchanged; gRPC stubs are regenerated for compatibility. Licences and attribution remain with each author component.

`README-full-reproduction.md` contains the full project guide; some of its links and verification commands refer to outputs omitted from this smaller handoff. `final-report/base-article-reproduction-report.pdf` is the completed study report. `partner-bundle-manifest.json` records SHA-256 hashes for the included logical paths; `archive-layout-aliases.json` maps duplicate paths to their stored source. `reports/source-audit.json` records official repositories, revisions and dataset hashes.
'''

def selected(p):
    r=p.relative_to(ROOT);parts=r.parts
    if not p.is_file() or any(x in parts for x in ['.git','__pycache__','target','.ipynb_checkpoints']):return False
    if p.suffix in ['.zip','.db','.db-journal','.sock'] or p.name=='kubeconfig.yaml':return False
    if parts[0]=='scripts':return True
    if parts[0]=='baseline-original':return 'images' not in parts
    if parts[0]=='environments':return len(parts)==2
    if parts[0]=='kubernetes-autoscaling':return parts[1] not in ['results']
    if parts[0]=='reports':return p.name in ['source-audit.json','published-tables-source.txt','prior-audit-evidence.json','errors-and-changes.json'] or parts[1]=='preprocessing-source'
    if r.as_posix()=='final-report/base-article-reproduction-report.pdf':return True
    return p.name=='README-forecasting-baseline.md' and len(parts)==1

paths=[]
for folder in ['scripts','baseline-original','environments','kubernetes-autoscaling','reports','final-report']:
    base=ROOT/folder
    if folder=='environments':paths.extend(p for p in base.iterdir() if selected(p))
    elif folder=='final-report':paths.append(base/'base-article-reproduction-report.pdf')
    else:
        import os
        for directory,dirs,files in os.walk(base):
            dirs[:]=[d for d in dirs if d not in ['.git','__pycache__','target','results','.ipynb_checkpoints']]
            paths.extend(Path(directory)/f for f in files if selected(Path(directory)/f))
paths.append(ROOT/'README-forecasting-baseline.md')
payload={p.relative_to(ROOT).as_posix():p.read_bytes() for p in paths}
payload['README-full-reproduction.md']=(ROOT/'README.md').read_bytes()
payload['README.md']=README.encode()
canonical={};aliases={};manifest={};stored={}
for name in sorted(payload,key=lambda n:(not n.startswith('baseline-original/'),n)):
    data=payload[name];sha=hashlib.sha256(data).hexdigest()
    manifest[name]={'bytes':len(data),'sha256':sha}
    if sha in canonical:aliases[name]={'source':canonical[sha],'sha256':sha}
    else:canonical[sha]=name;stored[name]=data
stored['archive-layout-aliases.json']=json.dumps(aliases,indent=2).encode()
stored['partner-bundle-manifest.json']=json.dumps(manifest,indent=2).encode()
with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name,data in stored.items():z.writestr('research-reproduction/'+name,data)
    for directory in ['logs','results','baseline-experiments','corrected-evaluation/results','kubernetes-autoscaling/results','final-report/figures']:
        z.writestr('research-reproduction/'+directory+'/',b'')
with zipfile.ZipFile(OUT) as z:
    assert z.testzip() is None
    for name,m in manifest.items():
        source=aliases.get(name,{}).get('source',name)
        assert hashlib.sha256(z.read('research-reproduction/'+source)).hexdigest()==m['sha256'],name
print(json.dumps({'path':str(OUT),'bytes':OUT.stat().st_size,'logical_files':len(manifest),'deduplicated_paths':len(aliases),'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'all_payload_hashes_verified':True},indent=2))
