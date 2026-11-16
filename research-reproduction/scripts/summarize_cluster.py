"""Summarize measured cluster evidence and plot; no synthetic outcomes."""
from pathlib import Path
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'kubernetes-autoscaling/results'
records=[]
ap=argparse.ArgumentParser();ap.add_argument('--run-id',default='run-03');args=ap.parse_args()
def cpu(s):
    for suffix,scale in [('n',1e-9),('u',1e-6),('m',1e-3)]:
        if s.endswith(suffix):return float(s[:-len(suffix)])*scale
    return float(s)
def mem(s):
    for suffix,scale in [('Ki',2**10),('Mi',2**20),('Gi',2**30)]:
        if s.endswith(suffix):return float(s[:-len(suffix)])*scale
    return float(s)
for path in sorted(out.glob(f'*/{args.run_id}/summary.json')):
    s=json.loads(path.read_text());obs=json.loads((path.parent/'observations.json').read_text());ph=json.loads((path.parent/'phases.json').read_text())
    assert s.get('protocol_valid') is True, 'Selected run failed scheduling checks'
    req=pd.read_csv(path.parent/'requests.csv')
    utilization=[];memory=[]
    for o in obs:
        pods=[p for p in o['pod_metrics']['items'] if p['metadata']['name'].startswith('sample-api-')]
        cores=sum(cpu(c['usage']['cpu']) for p in pods for c in p['containers'])
        mib=sum(mem(c['usage']['memory']) for p in pods for c in p['containers'])/2**20
        utilization.append(100*cores/(.25*len(pods)) if pods else np.nan);memory.append(mib)
    for r in s['scenarios']:
        phases=[p['elapsed'] for p in ph if p['scenario']==r['scenario']];lo=min(phases);hi=max(phases)+s['phase_seconds']
        indices=[i for i,o in enumerate(obs) if lo<=o['elapsed']<hi]
        subset=req[req.scenario==r['scenario']]
        assert len(subset)==r['requests'] and int(subset.failed.sum())==r['failed']
        assert np.isclose(np.percentile(subset.latency_ms,95),r['p95_ms'])
        assert np.isclose(np.percentile(subset.latency_ms,99),r['p99_ms'])
        r['mean_cpu_utilization_percent_of_request']=float(np.nanmean([utilization[i] for i in indices])) if indices else None
        r['mean_app_memory_mib']=float(np.mean([memory[i] for i in indices])) if indices else None
        r['run_id']=path.parent.name;r['monitor_samples']=len(indices)
        records.append(r)
    fig,axs=plt.subplots(3,1,figsize=(11,6),sharex=True)
    times=[o['elapsed']/60 for o in obs]
    axs[0].step(times,[o['desired'] for o in obs],where='post',label='Desired replicas')
    axs[0].step(times,[o['ready'] for o in obs],where='post',label='Ready replicas',linestyle='--');axs[0].set_ylabel('Replicas');axs[0].legend(loc='upper right',fontsize=8)
    max_replicas=max(max(o['desired'],o['ready']) for o in obs)
    axs[0].set_ylim(0,max_replicas+1);axs[0].set_yticks(range(max_replicas+2))
    twin=axs[0].twinx();twin.step([p['elapsed']/60 for p in ph]+[(ph[-1]['elapsed']+s['phase_seconds'])/60],[p['rps'] for p in ph]+[0],where='post',color='grey',alpha=.5);twin.set_ylabel('Offered requests/s')
    axs[1].plot(times,utilization);axs[1].axhline(70,color='grey',ls='--');axs[1].set_ylabel('CPU / request %')
    req['bin']=(req.elapsed//10).astype(int);groups=req.groupby('bin').latency_ms
    axs[2].plot(groups.quantile(.95).index*10/60,groups.quantile(.95),label='P95 per 10 s')
    axs[2].plot(groups.quantile(.99).index*10/60,groups.quantile(.99),label='P99 per 10 s');axs[2].axhline(500,color='grey',ls='--',label='500 ms threshold');axs[2].set_ylabel('Latency ms');axs[2].set_xlabel('Elapsed minutes');axs[2].legend(fontsize=8)
    for ax in axs:
        for name in ['stable','increasing','spike','decreasing']:
            t=min(p['elapsed'] for p in ph if p['scenario']==name)/60
            ax.axvline(t,color='grey',lw=.5)
        ax.grid(alpha=.2)
    axs[0].set_title(f"{s['scenarios'][0]['controller'].upper()} local integration run with four consecutive workload scenarios")
    fig.tight_layout();fig.savefig(path.parent/'cluster-plot.png',dpi=160);plt.close(fig)
if len(records)!=8:raise RuntimeError(f'Expected eight executed controller/scenario records, found {len(records)}')
(out/'comparison.json').write_text(json.dumps({'run_id':args.run_id,'scope':'one local integration sequence per controller; short phases; not replication of a published Kubernetes benchmark; earlier run-01 preserved as diagnostic evidence','scenarios':records},indent=2))
flat=[{k:v for k,v in r.items() if k!='scaling_response'} for r in records]
pd.DataFrame(flat).to_csv(out/'comparison.csv',index=False)
print(json.dumps(flat,indent=2))
