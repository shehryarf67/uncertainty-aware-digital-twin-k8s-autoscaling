"""Independently check final evidence without retraining or fabricating results."""
from pathlib import Path
import hashlib,json,csv
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error,mean_absolute_error,r2_score
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
checks={}
manifest=read(ROOT/'reports/artifact-manifest.json')
protected=['baseline-original/','baseline-experiments/','results/','datasets/']
count=0
for name,m in manifest.items():
    if any(name.startswith(prefix) for prefix in protected):
        p=ROOT/name
        assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==m['sha256'],name
        count+=1
checks['prior_baseline_files_hash_checked']=count
assert hashlib.sha256((ROOT/'README-forecasting-baseline.md').read_bytes()).hexdigest()==manifest['README.md']['sha256']
checks['original_readme_preserved']=True
audit=read(ROOT/'reports/source-audit.json')
published={'nasa':{'MSE':63.836,'RMSE':7.990,'MAE':6.164,'R2':.900,'TPT_ms':3492},'fifa':{'MSE':.000011,'RMSE':.003358,'MAE':.000675,'R2':.998318,'TPT_ms':3971}}
assert audit['published_prophet_lstm']==published
checks['printed_paper_hybrid_values_checked']=True
original=[]
for p in (ROOT/'results').glob('*/*/metrics.json'):
    if read(p.parent/'execution-status.json')['status']!='completed':continue
    m=read(p);d=pd.read_csv(p.parent/'predictions.csv');d=d[d.partition=='test']
    values={'MSE':mean_squared_error(d.y,d.y_predicted),'RMSE':np.sqrt(mean_squared_error(d.y,d.y_predicted)),'MAE':mean_absolute_error(d.y,d.y_predicted),'R2':r2_score(d.y,d.y_predicted)}
    for k,v in values.items():assert np.isclose(v,m[k],rtol=1e-10,atol=1e-12),(p,k)
    original.append(str(p.relative_to(ROOT)))
assert len(original)==4
checks['original_metrics_recomputed']=original
assert read(ROOT/'corrected-evaluation/verification.json')['status']=='passed'
checks['corrected_model_and_causal_checks']='passed; see corrected-evaluation/verification.json'
source_count=0
for repo,folder in [('proactive-autoscaler-for-keda-kubernetes','author-scaler'),('springboot-sample-api-with-prometheus','author-app')]:
    src=ROOT.parent/'artifacts/guruge-audit'/repo
    for p in src.rglob('*'):
        if p.is_file() and '.git' not in p.parts and 'models' not in p.parts and 'target' not in p.parts:
            target=ROOT/'kubernetes-autoscaling'/folder/p.relative_to(src)
            assert target.read_bytes()==p.read_bytes(),str(target)
            source_count+=1
assert (ROOT/'kubernetes-autoscaling/runtime-scaler/keda-grpc-server.py').read_bytes()==(ROOT/'kubernetes-autoscaling/author-scaler/keda-grpc-server.py').read_bytes()
checks['author_source_files_identical']=source_count
assert 'BUILD SUCCESS' in (ROOT/'logs/author-app-build-agent.log').read_text()
test=list((ROOT/'kubernetes-autoscaling/author-app/target/surefire-reports').glob('TEST-*.xml'))
assert test and all('failures="0"' in p.read_text() and 'errors="0"' in p.read_text() for p in test)
checks['original_application_tests_passed']=True
comparison=read(ROOT/'kubernetes-autoscaling/results/comparison.json');run=comparison['run_id'];records=[]
for c in ['forecast','hpa']:
    folder=ROOT/'kubernetes-autoscaling/results'/c/run;s=read(folder/'summary.json');obs=read(folder/'observations.json');ph=read(folder/'phases.json')
    assert s['status']=='completed' and s['protocol_valid'] is True
    req=pd.read_csv(folder/'requests.csv')
    assert len(req)==6870 and len(ph)==16 and len(obs)>40
    assert obs[0]['elapsed']<10
    for r in s['scenarios']:
        sub=req[req.scenario==r['scenario']]
        assert len(sub)==r['requests']
        assert int(sub.failed.sum())==r['failed']
        bad=(sub.status.ne(200)|sub.latency_ms.gt(500)).mean()
        assert np.isclose(bad,r['slo_violation_fraction']) and bool(bad<=.01)==r['slo_met']
        for percentile,key in [(95,'p95_ms'),(99,'p99_ms')]:assert np.isclose(np.percentile(sub.latency_ms,percentile),r[key])
        lo=min(p['elapsed'] for p in ph if p['scenario']==r['scenario']);hi=max(p['elapsed'] for p in ph if p['scenario']==r['scenario'])+s['phase_seconds']
        selected=[o for o in obs if lo<=o['elapsed']<hi]
        area=sum(o['desired']*(min(hi,selected[i+1]['elapsed'] if i+1<len(selected) else hi)-o['elapsed'])/60 for i,o in enumerate(selected))
        assert np.isclose(area,r['sampled_pod_minutes'])
        matched=next(x for x in comparison['scenarios'] if x['controller']==c and x['scenario']==r['scenario'])
        for k in ['requests','failed','p95_ms','p99_ms','sampled_pod_minutes','slo_violation_fraction']:assert np.isclose(matched[k],r[k])
        records.append({'controller':c,'scenario':r['scenario'],'requests':len(sub),'verified':True})
    if c=='forecast':assert max(o['ready'] for o in obs)>1 and max(o['desired'] for o in obs)>1
checks['cluster_actual_records']=records
checks['cluster_protocol_run']=run
checks['literature_claims']='Targeted primary-source review; novelty unproven; R2 abstract only; no claimed new-method results'
(ROOT/'final-report/quality-assurance.json').write_text(json.dumps({'status':'passed','checks':checks},indent=2))
print(json.dumps(checks,indent=2))
