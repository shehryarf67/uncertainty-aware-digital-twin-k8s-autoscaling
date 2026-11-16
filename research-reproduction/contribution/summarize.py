"""Independent aggregation of all pre-specified trials, including failures."""
from pathlib import Path
import json,csv,hashlib,statistics
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent
LABELS={'point':'Point Twin','workload_only':'Demand calibration','twin_only':'Twin calibration','full':'Dual calibration','cpu_hpa':'CPU HPA','no_delay':'No readiness horizon','reactive_proxy':'Reactive proxy','static6':'Static six'}
def cpu(s):
    for suffix,k in [('n',1e-9),('u',1e-6),('m',.001)]:
        if s.endswith(suffix):return float(s[:-len(suffix)])*k
    return float(s)
def main():
    rows=[]
    for f in sorted((ROOT/'results/live-01').glob('*/summary.json')):
        s=json.loads(f.read_text());d=pd.read_csv(f.parent/'requests.csv');o=json.loads((f.parent/'observations.json').read_text())
        assert len(d)==s['requests']==1400 and s['status']=='completed' and len(o)==16
        assert int(d.status.ne(200).sum())==s['failed']
        assert np.isclose((d.status.ne(200)|d.latency_ms.gt(500)).mean(),s['slo_violation_fraction'])
        assert np.isclose(np.percentile(d.latency_ms,99),s['p99_ms'])
        utilization=[]
        for a in o:
            pods=a['pod_metrics'].get('items',[])
            if pods:utilization.append(100*sum(cpu(c['usage']['cpu']) for p in pods for c in p['containers'])/(.25*len(pods)))
        covers=[v for a in o for v in a['decision']['demand_coverage_updates']];m=[a['decision']['twin_covered'] for a in o if a['decision']['twin_covered'] is not None]
        s.update(mean_cpu_percent=float(np.mean(utilization)) if utilization else None,demand_coverage=float(np.mean(covers)),twin_residual_coverage=float(np.mean(m)),mean_controller_ms=float(np.mean([a['decision']['elapsed_ms'] for a in o])),infeasible_decisions=sum(not a['decision']['feasible'] for a in o),mean_desired_replicas=float(np.mean([a['sample']['desired'] for a in o])),scale_actions=sum(a['decision']['target']!=a['sample']['desired'] for a in o) if s['controller']!='cpu_hpa' else sum(o[i]['sample']['desired']!=o[i-1]['sample']['desired'] for i in range(1,len(o))))
        rows.append(s)
    assert len(rows)==15,'All prespecified live runs must be retained before final analysis'
    df=pd.DataFrame(rows);df.to_csv(ROOT/'results/live-scores.csv',index=False)
    aggregate=[]
    keys=['slo_violation_fraction','p95_ms','p99_ms','sampled_desired_pod_minutes','mean_desired_replicas','mean_cpu_percent','demand_coverage','twin_residual_coverage','mean_controller_ms','infeasible_decisions']
    for mode,group in df.groupby('controller'):
        assert len(group)==3
        aggregate.append({'controller':mode,'label':LABELS[mode],'n':3,**{k:float(group[k].mean()) for k in keys},'violation_min':float(group.slo_violation_fraction.min()),'violation_max':float(group.slo_violation_fraction.max()),'valid_runs':int(group.phase_valid.sum()),'slo_met_runs':int(group.slo_violation_fraction.le(.01).sum())})
    simulation=pd.read_csv(ROOT/'results/simulation-01/scores.csv');assert len(simulation)==350
    sim_rows=[]
    for (regime,mode),g in simulation.groupby(['regime','controller']):
        assert len(g)==10
        sim_rows.append({'regime':regime,'controller':mode,'label':LABELS[mode],'n':10,**{k:float(g[k].mean()) for k in ['violation_fraction','mean_desired_replicas','p99_ms','demand_coverage','twin_residual_coverage','mean_controller_ms','infeasible_decisions']}})
    paired=[];rng=np.random.default_rng(777)
    for regime in simulation.regime.unique():
        subset=simulation[simulation.regime==regime]
        full=subset[subset.controller=='full'].set_index('seed').sort_index()
        for other in ['point','workload_only','twin_only','no_delay','reactive_proxy']:
            b=subset[subset.controller==other].set_index('seed').sort_index()
            delta=(full.violation_fraction-b.violation_fraction).to_numpy()*100
            boot=np.mean(rng.choice(delta,(5000,10),replace=True),axis=1)
            paired.append({'regime':regime,'comparison':'full minus '+other,'delta_violation_percentage_points':float(delta.mean()),'bootstrap95_low':float(np.quantile(boot,.025)),'bootstrap95_high':float(np.quantile(boot,.975))})
    profile=json.loads((ROOT/'results/profile-01/profile.json').read_text())
    from controller import Twin
    t=Twin(profile);cal=[r for r in profile if r['partition']=='calibration']
    errors=[abs(r['effective_p99_ms']-t.predict(r['rps'],r['replicas'],r['cpu_ms'])) for r in cal]
    report={'status':'completed','scope':'pilot empirical study; simulation and Kubernetes results kept separate','live':aggregate,'simulation':sim_rows,'simulation_paired_bootstrap':paired,'profile':{'fit_blocks':18,'calibration_blocks':12,'calibration_mae_ms':float(np.mean(errors)),'note':'calibration MAE is not independent test fidelity'},'all_live_protocol_checks_passed':bool(df.phase_valid.all()),'total_live_requests':int(df.requests.sum())}
    (ROOT/'results/summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'live':aggregate,'all_live_protocol_checks_passed':report['all_live_protocol_checks_passed']},indent=2))
if __name__=='__main__':main()
