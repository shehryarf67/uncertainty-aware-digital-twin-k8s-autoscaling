"""Independent request-level audit and paired-repetition analysis."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent
LABELS={'guarded':'Guarded Twin','no_reserve':'No reserve','legacy':'Original dual','cpu_hpa':'CPU HPA','static':'Fixed sixteen'}

def main():
    p=json.loads((ROOT/'frozen-protocol.json').read_text());rows=[];all_attempts=[]
    assert json.loads((ROOT/'controller-verification.json').read_text())['status']=='passed'
    for name,checksum in p['source_sha256'].items():
        normalized=name.replace('\\','/');relative=normalized.split('/research-reproduction/',1)[1]
        actual=ROOT/relative.split('/',1)[1] if relative.startswith('revision-20261114/') else ROOT.parent/relative
        assert hashlib.sha256(actual.read_bytes()).hexdigest()==checksum,relative
    for scenario,cfg in p['scenarios'].items():
        for seed in p['seeds']:
            for mode in p['controllers']:
                valid=[]
                for f in sorted((ROOT/'results/live').glob(f'{scenario}-{seed}-{mode}-attempt*/summary.json')):
                    s=json.loads(f.read_text());all_attempts.append(s)
                    if not s['protocol_valid']:continue
                    d=pd.read_csv(f.parent/'requests.csv');o=json.loads((f.parent/'observations.json').read_text());samples=json.loads((f.parent/'replicas.json').read_text())
                    assert s['status']=='completed' and len(d)==s['expected_requests']==s['requests']
                    assert len(o)==len(cfg['rates']) and not d.request_id.duplicated().any()
                    bad=d.status.ne(200)|d.latency_ms.gt(500)
                    assert bad.sum()==s['slo_bad_count'] and np.isclose(bad.mean(),s['slo_violation_fraction'])
                    assert np.isclose(np.percentile(d.latency_ms,99),s['p99_ms'])
                    assert np.isclose(np.percentile(d.latency_ms,95),s['p95_ms'])
                    assert d.status.ne(200).sum()==s['failed'] and d.latency_ms.ge(0).all()
                    assert np.allclose((d.finished_seconds-d.sent_seconds)*1000,d.latency_ms)
                    assert d.groupby('block').size().reindex(range(len(cfg['rates']))).tolist()==[r*cfg['active_seconds'] for r in cfg['rates']]
                    assert all(0<=x['ready']<=16 and 1<=x['desired']<=16 for x in samples if 'desired' in x)
                    assert max(d.schedule_delay_ms)<500 and max(a['decision_time_seconds']-a['cutoff_seconds'] for a in o)<1
                    good=[x for x in samples if 'desired' in x];area=sum(a['desired']*(b['time']-a['time'])/60 for a,b in zip(good,good[1:]))
                    # The live cost adds the terminal partial sampling interval.
                    # No archived terminal clock exists, so audit its 0--3s bound.
                    assert area-1e-6<=s['desired_pod_minutes']<=area+16*3/60
                    s.update(label=LABELS[mode],slo_met=s['slo_violation_fraction']<=.01,mean_ready_replicas=float(np.mean([x['ready'] for x in good])),mean_desired_replicas=float(np.mean([x['desired'] for x in good])),scale_actions=sum(a['decision']['target']!=a['sample']['desired'] for a in o) if mode not in ['cpu_hpa','static'] else sum(b['desired']!=a['desired'] for a,b in zip(good,good[1:])),controller_ms=float(np.mean([a['decision']['elapsed_ms'] for a in o])) if mode not in ['cpu_hpa','static'] else None)
                    valid.append(s)
                assert valid,(scenario,seed,mode)
                rows.append(valid[0])
    assert len(rows)==75
    vp=json.loads((ROOT/'validation-protocol.json').read_text())
    assert hashlib.sha256((ROOT/'validate_twin.py').read_bytes()).hexdigest()==vp['script_sha256']
    val=ROOT/'results/twin-validation';vd=pd.read_csv(val/'requests.csv');vc=json.loads((val/'conditions.json').read_text());vs=json.loads((val/'summary.json').read_text())
    assert vs['status']=='completed' and vs['all_dispatch_valid'] and len(vc)==18 and len(vd)==2160 and not vd.request_id.duplicated().any()
    for condition in vc:
        block=vd[vd.validation_block==condition['block']]
        assert len(block)==condition['requests']==condition['rate']*5
        assert np.isclose((block.status.ne(200)|block.latency_ms.gt(500)).mean(),condition['slo_violation_fraction'])
        effective=np.where(block.status.ne(200),np.maximum(2000,block.latency_ms),block.latency_ms)
        assert np.isclose(np.percentile(effective,99),condition['effective_p99_ms'])
    assert np.isclose(np.mean([abs(c['predicted_effective_p99_ms']-c['effective_p99_ms']) for c in vc]),vs['effective_p99_mae_ms'])
    assert sum(c['envelope_predicts_safe'] and c['slo_violation_fraction']>.01 for c in vc)==vs['false_safe_conditions']
    df=pd.DataFrame(rows);df.to_csv(ROOT/'results/live-scores.csv',index=False)
    rng=np.random.default_rng(191114);aggregates=[];pairs=[]
    for (scenario,mode),g in df.groupby(['scenario','controller']):
        assert len(g)==5
        boot=rng.choice(g.slo_violation_fraction.to_numpy(),(10000,5),replace=True).mean(axis=1)*100
        aggregates.append({'scenario':scenario,'controller':mode,'label':LABELS[mode],'n':5,'slo_met_runs':int(g.slo_met.sum()),'requests':int(g.requests.sum()),'mean_violation_percent':float(100*g.slo_violation_fraction.mean()),'min_violation_percent':float(100*g.slo_violation_fraction.min()),'max_violation_percent':float(100*g.slo_violation_fraction.max()),'bootstrap95_violation_percent':[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],'p99_ms':float(g.p99_ms.mean()),'pod_minutes':float(g.desired_pod_minutes.mean()),'mean_ready_replicas':float(g.mean_ready_replicas.mean()),'mean_controller_ms':float(g.controller_ms.mean()) if g.controller_ms.notna().any() else None})
    for scenario in p['scenarios']:
        new=df[(df.scenario==scenario)&(df.controller=='guarded')].set_index('seed').sort_index()
        for mode in ['legacy','no_reserve','cpu_hpa','static']:
            old=df[(df.scenario==scenario)&(df.controller==mode)].set_index('seed').sort_index()
            dv=100*(new.slo_violation_fraction-old.slo_violation_fraction).to_numpy();dc=(new.desired_pod_minutes-old.desired_pod_minutes).to_numpy()
            ix=rng.integers(0,5,(10000,5));bv=dv[ix].mean(axis=1);bc=dc[ix].mean(axis=1)
            pairs.append({'scenario':scenario,'comparison':'guarded minus '+mode,'violation_pp':float(dv.mean()),'violation95':[float(np.quantile(bv,.025)),float(np.quantile(bv,.975))],'pod_minutes_delta':float(dc.mean()),'pod_minutes95':[float(np.quantile(bc,.025)),float(np.quantile(bc,.975))],'relative_pod_minutes_percent':float(100*(new.desired_pod_minutes.mean()/old.desired_pod_minutes.mean()-1))})
    overall=[]
    for mode,g in df.groupby('controller'):
        overall.append({'controller':mode,'label':LABELS[mode],'runs':len(g),'slo_met_runs':int(g.slo_met.sum()),'mean_trial_violation_percent':float(100*g.slo_violation_fraction.mean()),'pooled_request_violation_percent':float(100*g.slo_bad_count.sum()/g.requests.sum()),'mean_pod_minutes':float(g.desired_pod_minutes.mean()),'p99_ms':float(g.p99_ms.mean())})
    report={'status':'completed','final_live_runs':75,'valid_requests':int(df.requests.sum()),'all_attempts':len(all_attempts),'invalid_attempts':sum(not a['protocol_valid'] for a in all_attempts),'all_attempt_requests':sum(a['requests'] for a in all_attempts),'aggregate':aggregates,'overall':overall,'paired_comparisons':pairs,'source_hashes_verified':True,'request_metrics_independently_recomputed':True,'allocation_audit':'Integrated sampled replica area checked with a terminal 0--3s uncertainty bound; reported live integration uses actual elapsed time','statistical_scope':'Five paired repetitions per workload; descriptive seed bootstrap intervals; per-request samples are temporally dependent; zero empirical violations do not certify zero risk'}
    (ROOT/'results/summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
