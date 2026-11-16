"""Separate paired audit of the exploratory reserve-matched live cohort."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'reserve-followup'
p=json.loads((DATA/'frozen-protocol.json').read_text());rows=[]
assert hashlib.sha256((ROOT/'reserve_followup.py').read_bytes()).hexdigest()==p['followup_wrapper_sha256']
assert hashlib.sha256((ROOT/'controller_v2.py').read_bytes()).hexdigest()==p['controller_sha256']
assert hashlib.sha256((ROOT/'experiments.py').read_bytes()).hexdigest()==p['base_harness_sha256']
for scenario,cfg in p['scenarios'].items():
    for seed in p['seeds']:
        for mode in p['controllers']:
            valid=[]
            for f in sorted((DATA/'results/live').glob(f'{scenario}-{seed}-{mode}-attempt*/summary.json')):
                s=json.loads(f.read_text())
                if not s['protocol_valid']:continue
                d=pd.read_csv(f.parent/'requests.csv');samples=json.loads((f.parent/'replicas.json').read_text())
                assert len(d)==s['requests']==s['expected_requests'] and not d.request_id.duplicated().any()
                assert np.isclose((d.status.ne(200)|d.latency_ms.gt(500)).mean(),s['slo_violation_fraction'])
                assert np.isclose(np.percentile(d.latency_ms,99),s['p99_ms'])
                assert all(8<=r['desired']<=16 for r in samples if 'desired' in r)
                valid.append(s)
            assert valid
            rows.append(valid[0])
assert len(rows)==18
d=pd.DataFrame(rows);d.to_csv(DATA/'results/scores.csv',index=False);results=[];rng=np.random.default_rng(191115)
for scenario in p['scenarios']:
    g=d[(d.scenario==scenario)&(d.controller=='guarded')].set_index('seed').sort_index()
    h=d[(d.scenario==scenario)&(d.controller=='cpu_hpa')].set_index('seed').sort_index()
    delta=100*(g.slo_violation_fraction-h.slo_violation_fraction).to_numpy();boot=rng.choice(delta,(10000,3),replace=True).mean(axis=1)
    results.append({'scenario':scenario,'n':3,'guarded_met':int(g.slo_violation_fraction.le(.01).sum()),'hpa_reserve_met':int(h.slo_violation_fraction.le(.01).sum()),'guarded_bad_percent':float(100*g.slo_violation_fraction.mean()),'hpa_reserve_bad_percent':float(100*h.slo_violation_fraction.mean()),'guarded_pod_minutes':float(g.desired_pod_minutes.mean()),'hpa_reserve_pod_minutes':float(h.desired_pod_minutes.mean()),'paired_bad_pp':float(delta.mean()),'paired95':[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))]})
report={'status':'completed','trials':18,'requests':int(d.requests.sum()),'same_minimum_eight_and_maximum_sixteen_verified':True,'results':results,'scope':'Exploratory follow-up specified after early primary outcomes to test minimum-replica confounding. Frozen controller unchanged. Three fresh paired repetitions, separate from the original 75-comparison cohort.'}
(DATA/'results/summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
