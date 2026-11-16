"""Preserve and stage official autoscaler sources; regenerate compatible stubs."""
from pathlib import Path
import shutil, subprocess, sys, json, hashlib
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT.parent/'artifacts'/'guruge-audit'
out=ROOT/'kubernetes-autoscaling'
out.mkdir(exist_ok=True)
for repo,name in [('proactive-autoscaler-for-keda-kubernetes','author-scaler'),('springboot-sample-api-with-prometheus','author-app')]:
    src=AUDIT/repo; dst=out/name
    if not dst.exists():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('.git','models'))
work=out/'runtime-scaler';work.mkdir(exist_ok=True)
for f in (out/'author-scaler').iterdir():
    if f.is_file():shutil.copy2(f,work/f.name)
(work/'models').mkdir(exist_ok=True)
for pattern in ['fbprophet-nasa-20240911_175323.json','lstm-nasa-20240911_175323.keras']:
    shutil.copy2(ROOT/'baseline-original'/'models'/pattern,work/'models'/pattern)
subprocess.run([sys.executable,'-m','grpc_tools.protoc',f'-I{work}',f'--python_out={work}',f'--grpc_python_out={work}',str(work/'externalscaler.proto')],check=True)
source=out/'author-scaler'/'keda-grpc-server.py'
assert source.read_bytes()==(work/'keda-grpc-server.py').read_bytes()
(out/'source-provenance.json').write_text(json.dumps({'scaler_code_unchanged':True,'scaler_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'compatibility_change':'Regenerated stubs with grpcio-tools 1.62.3 / protobuf 4.25.8; original stubs require newer grpc/protobuf conflicting with TensorFlow 2.17 protobuf<5',
    'models':'Official released NASA 20240911 checkpoints, not corrected models',
    'source_repositories':['https://github.com/PasanBhanu/proactive-autoscaler-for-keda-kubernetes','https://github.com/PasanBhanu/springboot-sample-api-with-prometheus']},indent=2))
print(work)
