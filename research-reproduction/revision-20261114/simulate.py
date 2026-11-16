"""Independent queueing stress plant with paired inputs and isolated ablations."""
from pathlib import Path
import sys,json,csv,math,copy,ast,inspect,textwrap,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'contribution'))
from controller import Controller
import controller_v2
from controller_v2 import GuardedController
REGIMES=['smooth','burst','service_drift','slow_readiness','observation_delay']
MODES=['guarded','no_reserve','no_emergency','no_horizon','legacy','cpu_proxy','static16','static8']

def ablation_class(name,assignment,value):
    # Transform only the named assignment in the frozen, trusted local method.
    tree=ast.parse(textwrap.dedent(inspect.getsource(GuardedController.decide)))
    count=0
    class Remove(ast.NodeTransformer):
        def visit_Assign(self,node):
            nonlocal count
            if any(isinstance(t,ast.Name) and t.id==assignment for t in node.targets):
                node.value=ast.Constant(value=value);count+=1
            return node
    tree=Remove().visit(tree);ast.fix_missing_locations(tree);namespace={}
    exec(compile(tree,f'<isolated-{name}-ablation>','exec'),controller_v2.__dict__,namespace)
    assert count==1
    return type(name,(GuardedController,),{'decide':namespace['decide']})

NoEmergency=ablation_class('NoEmergency','emergency',False)
NoHorizon=ablation_class('NoHorizon','horizon',1)

def trace(seed,regime,cpu):
    rng=np.random.default_rng(seed);blocks=[]
    for k in range(64):
        rate=max(3.,10+6*np.sin(k/5)+max(0,min(k-12,8)))
        if regime!='smooth' and k%20 in [8,9,10]:rate+=25
        units=1.8 if regime=='service_drift' and k>=32 else 1.
        count=rng.poisson(rate*8);arrivals=np.sort(rng.uniform(k*8,(k+1)*8,count))
        service=rng.lognormal(np.log(cpu*units/1000)-.5*.3**2,.3,count)/.5
        blocks.append(list(zip(arrivals,service)))
    return blocks

def run(seed,regime,mode,development,legacy_profile):
    cpu=float(np.median([r['cpu_ms'] for r in development if r['units']==1]))
    blocks=trace(seed,regime,cpu)
    if mode=='legacy':ctrl=Controller(legacy_profile,'full',[5.]*12,limit=16)
    elif mode in ['guarded','no_reserve']:ctrl=GuardedController(development,mode,initial_cpu=cpu)
    elif mode=='no_emergency':ctrl=NoEmergency(development,initial_cpu=cpu)
    elif mode=='no_horizon':ctrl=NoHorizon(development,initial_cpu=cpu)
    else:ctrl=None
    desired=16 if mode=='static16' else 8;servers=[0.]*desired;pending=[];rows=[];observations=[];history=[];usage_history=[]
    delay=24 if regime=='slow_readiness' else 8
    for k,arrivals in enumerate(blocks):
        begin=k*8;end=(k+1)*8
        for t in list(pending):
            if t<=begin:servers.append(t);pending.remove(t)
        ready=len(servers)
        assert 1<=ready<=16 and 1<=desired<=16
        for at,service in arrivals:
            j=int(np.argmin(servers));work_start=max(at,servers[j]);work_end=work_start+service;reject=work_start-at>2
            status=429 if reject else (200 if work_end-at<=3 else 0)
            latency=2000 if reject else min(3000,(work_end-at)*1000)
            if not reject:servers[j]=work_end
            rows.append({'arrival':float(at),'finish':float(at+2 if reject else min(at+3,work_end)),'cpu_start':float(work_start),'cpu_end':float(work_end),'cpu_ms':float(service*500) if status==200 else None,'status':status,'latency_ms':latency,'bad':status!=200 or latency>500})
        done=[r for r in rows if begin<=r['finish']<end];lat=[r['latency_ms'] for r in done]
        effective=[max(2000,r['latency_ms']) if r['status']!=200 else r['latency_ms'] for r in done]+[(end-r['arrival'])*1000 for r in rows if r['arrival']<end<r['finish']]
        work=[r['cpu_ms'] for r in done if r['cpu_ms'] is not None]
        used=sum(max(0,min(end,r['cpu_end'])-max(begin,r['cpu_start']))*.5 for r in rows if r['status']!=429)
        bad=sum(r['bad'] for r in done)
        sample={'rps':len(arrivals)/8,'requests':len(done),'slo_bad_count':bad,'slo_violation_fraction':bad/max(1,len(done)),'effective_p99_ms':float(np.percentile(effective,99)) if effective else 0.,'cpu_ms':float(np.median(work)) if work else None,'cpu_p90_ms':float(np.percentile(work,90)) if work else None,'desired':desired,'ready':ready,'clock_seconds':end}
        history.append(sample);usage_history.append(used/(8*.25*max(1,ready)))
        observed=copy.deepcopy(history[max(0,k-1)] if regime=='observation_delay' else sample)
        observed.update(desired=desired,ready=ready,clock_seconds=end)
        if ctrl:decision=ctrl.decide(observed,k);target=decision['target']
        elif mode.startswith('static'):target=16 if mode=='static16' else 8;decision={}
        else:
            use=usage_history[max(0,k-1)] if regime=='observation_delay' else usage_history[-1]
            target=max(1,min(16,math.ceil(ready*min(2,use)/.7)))
            if target<desired and k%3:target=desired
            decision={}
        if target<desired and ready<desired:target=desired
        if target>desired:pending.extend([end+delay]*(target-desired))
        elif target<desired and ready>=desired:servers=sorted(servers)[:target]
        observations.append({'cycle':k,'desired':desired,'ready':ready,'target':target,'sample':sample,'decision':decision});desired=target
    result={'seed':seed,'regime':regime,'controller':mode,'requests':len(rows),'violation_fraction':float(np.mean([r['bad'] for r in rows])),'p99_ms':float(np.percentile([r['latency_ms'] for r in rows],99)),'mean_desired_replicas':float(np.mean([o['desired'] for o in observations])),'mean_ready_replicas':float(np.mean([o['ready'] for o in observations])),'slo_met':float(np.mean([r['bad'] for r in rows]))<=.01,'arrivals_cpu_sha256':hashlib.sha256(json.dumps(blocks).encode()).hexdigest()}
    return result,observations

def main():
    out=ROOT/'results/simulation';out.mkdir(exist_ok=False)
    development=[]
    for n in ['development-capacity-01','development-capacity-02','development-capacity-03']:development+=json.loads((ROOT/n/'summary.json').read_text())
    legacy=json.loads((ROOT.parent/'contribution/results/profile-01/profile.json').read_text());scores=[]
    for seed in range(25):
        for regime in REGIMES:
            for mode in MODES:
                s,o=run(seed,regime,mode,development,legacy);scores.append(s)
                if seed==0:(out/f'{regime}-{mode}.json').write_text(json.dumps({'summary':s,'observations':o},indent=2,default=lambda value: value.item() if isinstance(value, np.generic) else value))
        print('simulation seed',seed,'completed',flush=True)
    with (out/'scores.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(scores[0]));w.writeheader();w.writerows(scores)
    (out/'status.json').write_text(json.dumps({'status':'completed','trials':len(scores),'seeds':25,'regimes':REGIMES,'controllers':MODES,'plant':'Independent Poisson/lognormal multi-server queue; central dispatch; does not generate labels from the fitted response Twin','observation_delay':'All demand/response/CPU feedback delayed; replica state current','ablations':'Single frozen-source assignment removed for emergency or planning-horizon ablation'},indent=2))

if __name__=='__main__':main()
