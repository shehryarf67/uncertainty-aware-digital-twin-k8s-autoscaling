"""Separate discrete-event queueing plant; never calls the Twin to make labels."""
from pathlib import Path
import json,csv,math,heapq,copy,time
import numpy as np
from controller import Controller
ROOT=Path(__file__).resolve().parent
MODES=['point','workload_only','twin_only','full','no_delay','reactive_proxy','static6']
REGIMES=['smooth','burst','service_drift','slow_readiness','observation_delay']
def trace(seed,regime,cpu_reference):
    rng=np.random.default_rng(seed);records=[];rates=[]
    for k in range(64):
        rate=10+6*np.sin(k/5)+max(0,min(k-12,8))
        if regime!='smooth' and (k%20 in [8,9,10]):rate+=25
        rate=max(3,rate);rates.append(rate)
        units=1.8 if regime=='service_drift' and k>=32 else 1.
        count=rng.poisson(rate*8)
        arrivals=np.sort(rng.uniform(k*8,(k+1)*8,count))
        # Lognormal CPU work is independently sampled, rather than Twin outputs.
        service=rng.lognormal(np.log(cpu_reference*units/1000)-.5*.3**2,.3,count)/.5
        records.append(list(zip(arrivals,service)))
    return records,rates
def run(seed,regime,mode,profile):
    ctrl=Controller(profile,mode,[5.]*12);blocks,_=trace(seed,regime,ctrl.cpu)
    delay=24 if regime=='slow_readiness' else 8
    desired=6 if mode=='static6' else 1;servers=[0.]*desired;pending=[];requests=[];observations=[];history=[]
    for k,arrivals in enumerate(blocks):
        begin=k*8;end=(k+1)*8
        for t in list(pending):
            if t<=begin:servers.append(t);pending.remove(t)
        ready=len(servers);block_records=[];cpu_work=0
        for at,service in arrivals:
            # FIFO central dispatch to the earliest free ready server.
            j=int(np.argmin(servers));service_start=max(at,servers[j]);finish=service_start+service
            rejected=service_start-at>2
            # A bounded waiting time models a finite client timeout.
            latency=min(3000,(finish-at)*1000);bad=latency>500
            status=429 if rejected else (200 if finish-at<=3 else 0)
            if not rejected:servers[j]=finish
            else:latency=2000
            row={'arrival':at,'finish':at+2 if rejected else min(at+3,finish),'start_cpu':service_start,'finish_cpu':finish,'latency_ms':latency,'status':status,'slo_bad':bad or status!=200,'cpu_ms':None if rejected else service*.5*1000,'block':k}
            block_records.append(row);requests.append(row)
        # Only completed responses are observable. Pending outcomes are censored.
        done=[r for r in requests if begin<=r['finish']<end]
        observed=[r['latency_ms'] for r in done]
        ages=[(end-r['arrival'])*1000 for r in requests if r['arrival']<end<r['finish']]
        effective=observed+[max(2000,a) if a>500 else a for a in ages]
        work=[r['cpu_ms'] for r in done if r['cpu_ms'] is not None]
        cpu_work=sum(max(0,min(end,r['finish_cpu'])-max(begin,r['start_cpu']))*.5 for r in requests if r['status']!=429)
        sample={'rps':len(arrivals)/8,'desired':desired,'ready':ready,'effective_p99_ms':float(np.percentile(effective,99)) if effective else 0,'cpu_ms':float(np.median(work)) if work else None}
        history.append(sample)
        observed_sample=copy.deepcopy(history[max(0,k-1)] if regime=='observation_delay' else sample)
        observed_sample['desired']=desired;observed_sample['ready']=ready
        decision=ctrl.decide(observed_sample,k)
        if mode=='static6':target=6
        elif mode=='reactive_proxy':
            utilization=min(ready*2,cpu_work/(8*.25*max(1,ready)))
            target=max(1,min(6,math.ceil(ready*utilization/.7)))
            if target<desired:target=desired if k%3 else target
        else:target=decision['target']
        if target<desired and ready<desired:target=desired
        if target>desired:pending.extend([end+delay]*(target-desired))
        elif target<desired and ready>=desired:
            # Drain removed servers; their already queued work is not migrated.
            servers=sorted(servers)[:target]
        observations.append({'block':k,'ready':ready,'desired':desired,'target':target,'decision':decision,'sample':sample})
        desired=target
    l=np.array([r['latency_ms'] for r in requests]);bad=np.array([r['slo_bad'] for r in requests])
    dcover=[v for o in observations for v in o['decision']['demand_coverage_updates']]
    mcover=[o['decision']['twin_covered'] for o in observations if o['decision']['twin_covered'] is not None]
    result={'seed':seed,'regime':regime,'controller':mode,'requests':len(requests),'violation_fraction':float(bad.mean()),'p95_ms':float(np.percentile(l,95)),'p99_ms':float(np.percentile(l,99)),'mean_desired_replicas':float(np.mean([o['desired'] for o in observations])),'mean_ready_replicas':float(np.mean([o['ready'] for o in observations])),'scale_actions':sum(o['target']!=o['desired'] for o in observations),'demand_coverage':float(np.mean(dcover)),'twin_residual_coverage':float(np.mean(mcover)),'mean_controller_ms':float(np.mean([o['decision']['elapsed_ms'] for o in observations])),'infeasible_decisions':sum(not o['decision']['feasible'] for o in observations)}
    return result,observations,requests
def main():
    out=ROOT/'results/simulation-01';out.mkdir(parents=True,exist_ok=False)
    profile=json.loads((ROOT/'results/profile-01/profile.json').read_text());results=[]
    for seed in range(10):
        for regime in REGIMES:
            for mode in MODES:
                r,o,requests=run(seed,regime,mode,profile);results.append(r)
                if seed==0:(out/f'{regime}-{mode}.json').write_text(json.dumps({'summary':r,'observations':o},indent=2))
        print('simulation seed',seed,'completed',flush=True)
    with (out/'scores.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    (out/'status.json').write_text(json.dumps({'status':'completed','runs':len(results),'seeds':10,'regimes':REGIMES,'controllers':MODES,'plant':'independent lognormal-service multi-server queue; 8-second cycles; simulated, not Kubernetes; draining removed-server work retained in request outcomes'},indent=2))
if __name__=='__main__':main()
