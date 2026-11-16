"""Check all paired-input identities and reproduce selected plant rollouts."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
from simulate import run
ROOT=Path(__file__).resolve().parent
p=json.loads((ROOT/'simulation-protocol.json').read_text())
current=(ROOT/'simulate.py').read_bytes()
original=current.replace(b"json.dumps({'summary':s,'observations':o},indent=2,default=lambda value: value.item() if isinstance(value, np.generic) else value)",b"json.dumps({'summary':s,'observations':o},indent=2)")
assert current != original and hashlib.sha256(original).hexdigest()==p['simulation_script_sha256']
assert hashlib.sha256((ROOT/'controller_v2.py').read_bytes()).hexdigest()==p['live_controller_sha256']
d=pd.read_csv(ROOT/'results/simulation/scores.csv')
assert len(d)==1000 and not d[['seed','regime','controller']].duplicated().any()
assert d.groupby(['seed','regime']).arrivals_cpu_sha256.nunique().eq(1).all()
assert d.groupby(['seed','regime']).requests.nunique().eq(1).all()
assert d.violation_fraction.between(0,1).all() and d.mean_desired_replicas.between(1,16).all() and d.mean_ready_replicas.between(1,16).all()
development=[]
for n in ['development-capacity-01','development-capacity-02','development-capacity-03']:development+=json.loads((ROOT/n/'summary.json').read_text())
legacy=json.loads((ROOT.parent/'contribution/results/profile-01/profile.json').read_text())
for seed,regime,mode in [(0,'smooth','guarded'),(24,'service_drift','no_horizon')]:
    r,observations=run(seed,regime,mode,development,legacy)
    stored=d[(d.seed==seed)&(d.regime==regime)&(d.controller==mode)].iloc[0]
    for k in ['requests','violation_fraction','p99_ms','mean_desired_replicas','mean_ready_replicas']:assert np.isclose(r[k],stored[k]),k
    assert r['arrivals_cpu_sha256']==stored.arrivals_cpu_sha256
report={'status':'passed','rollouts':len(d),'common_inputs_verified_across_all_policies':True,'selected_end_to_end_rollouts_reproduced':2,'original_simulation_hash_verified_after_reversing_serialization_only_fix':True,'live_controller_hash_verified':True}
(ROOT/'results/simulation-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
