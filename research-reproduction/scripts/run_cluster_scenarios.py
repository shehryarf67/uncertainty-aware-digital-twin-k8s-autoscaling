"""Authored open-loop HTTP workload and Kubernetes evidence collector."""
import argparse, asyncio, csv, json, subprocess, time, math
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
KCMD=['wsl','-d','Ubuntu','-u','root','--','/opt/guruge-reproduction/bin/k3s','kubectl','--kubeconfig','/opt/guruge-reproduction/kubeconfig.yaml']
def kube(*args):
    p=subprocess.run(KCMD+list(args),capture_output=True,text=True,encoding='utf8',timeout=220 if 'rollout' in args else 40)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout
async def run(args):
    import numpy as np
    config=json.loads((ROOT/'kubernetes-autoscaling/configurations/scenarios.json').read_text())
    folder=ROOT/'kubernetes-autoscaling/results'/args.controller/args.run_id
    if folder.exists():raise FileExistsError(folder)
    folder.mkdir(parents=True)
    # Do not run competing controllers on the same deployment.
    kube('delete','scaledobject','author-forecast','-n','guruge-repro','--ignore-not-found=true')
    kube('delete','hpa','cpu-hpa','-n','guruge-repro','--ignore-not-found=true')
    # Wait for KEDA-owned HPA deletion before switching ownership.
    for _ in range(20):
        if not json.loads(kube('get','hpa','-n','guruge-repro','-o','json'))['items']:break
        await asyncio.sleep(1)
    else:raise RuntimeError('Previous HPA still owns deployment')
    kube('scale','deployment/sample-api','-n','guruge-repro','--replicas=1')
    kube('apply','-f',str(ROOT/'kubernetes-autoscaling/manifests'/('forecast.yaml' if args.controller=='forecast' else 'hpa.yaml')).replace('C:\\','/mnt/c/').replace('\\','/'))
    kube('rollout','status','deployment/sample-api','-n','guruge-repro','--timeout=180s')
    # Native Linux path used through WSL; generated below instead for Windows C: path.
    requests=[];observations=[];phase_events=[];errors=[]
    limits=httpx.Limits(max_connections=200,max_keepalive_connections=100)
    async with httpx.AsyncClient(timeout=10,limits=limits) as client:
        # Equal warm-up after controller ownership switch; discard its timings.
        print(args.controller,'warm-up started',flush=True)
        for _ in range(args.warmup_seconds*5):
            warm_start=time.perf_counter()
            try:await client.get(args.url+'/sample')
            except Exception:pass
            await asyncio.sleep(max(0,.2-(time.perf_counter()-warm_start)))
        kube('rollout','status','deployment/sample-api','-n','guruge-repro','--timeout=180s')
        global_start=time.perf_counter();stop=False
        async def observe():
            while not stop:
                t=time.perf_counter()-global_start
                try:
                    d=json.loads(await asyncio.to_thread(kube,'get','deployment/sample-api','-n','guruge-repro','-o','json'))
                    h=json.loads(await asyncio.to_thread(kube,'get','hpa','-n','guruge-repro','-o','json'))
                    cpu=json.loads(await asyncio.to_thread(kube,'get','--raw','/apis/metrics.k8s.io/v1beta1/namespaces/guruge-repro/pods'))
                    observations.append({'elapsed':t,'collection_finished_elapsed':time.perf_counter()-global_start,'desired':d['spec']['replicas'],'ready':d.get('status',{}).get('readyReplicas',0),'hpa':h,'pod_metrics':cpu})
                except Exception as e:errors.append({'elapsed':t,'error':str(e)})
                await asyncio.sleep(5)
        monitor=asyncio.create_task(observe())
        async def hit(scenario,phase,rps,scheduled):
            sent=time.perf_counter();status=None;error=None
            try:
                response=await client.get(args.url+'/sample');status=response.status_code
            except Exception as e:error=str(e)
            end=time.perf_counter();lat=(end-sent)*1000
            requests.append({'scenario':scenario,'phase':phase,'offered_rps':rps,'elapsed':sent-global_start,'schedule_delay_ms':(sent-scheduled)*1000,
                             'latency_ms':lat,'status':status,'error':error,'failed':status!=200,'slo_bad':status!=200 or lat>500})
        tasks=set()
        for scenario in ['stable','increasing','spike','decreasing']:
            scenario_start=time.perf_counter()
            print(args.controller,scenario,'started',flush=True)
            for phase,rps in enumerate(config[scenario]):
                start=time.perf_counter();phase_events.append({'scenario':scenario,'phase':phase,'rps':rps,'elapsed':start-global_start})
                for i in range(int(rps*args.phase_seconds)):
                    scheduled=start+i/rps
                    await asyncio.sleep(max(0,scheduled-time.perf_counter()))
                    task=asyncio.create_task(hit(scenario,phase,rps,scheduled));tasks.add(task);task.add_done_callback(tasks.discard)
                await asyncio.sleep(max(0,start+args.phase_seconds-time.perf_counter()))
            print(args.controller,scenario,'offered traffic completed',flush=True)
        if tasks:await asyncio.gather(*list(tasks))
        stop=True;await monitor
    elapsed=time.perf_counter()-global_start
    with (folder/'requests.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(requests[0]));writer.writeheader();writer.writerows(requests)
    (folder/'observations.json').write_text(json.dumps(observations,indent=2))
    (folder/'phases.json').write_text(json.dumps(phase_events,indent=2))
    (folder/'monitor-errors.json').write_text(json.dumps(errors,indent=2))
    summaries=[]
    for name in config.keys() & {'stable','increasing','spike','decreasing'}:
        subset=[r for r in requests if r['scenario']==name]
        boundaries=[p['elapsed'] for p in phase_events if p['scenario']==name];lo=min(boundaries);hi=max(boundaries)+args.phase_seconds
        obs=[o for o in observations if lo<=o['elapsed']<hi]
        # Sampled step integration; this estimates replica-minutes, not billable cost.
        pod_minutes=sum(o['desired']*(min(hi,obs[i+1]['elapsed'] if i+1<len(obs) else hi)-o['elapsed'])/60 for i,o in enumerate(obs))
        changes=[]
        for phase in [p for p in phase_events if p['scenario']==name]:
            before=[o for o in observations if o['elapsed']<phase['elapsed']]
            initial=before[-1]['desired'] if before else (obs[0]['desired'] if obs else None)
            first=next((o for o in observations if phase['elapsed']<=o['elapsed']<phase['elapsed']+args.phase_seconds and o['desired']!=initial),None)
            changes.append({'phase':phase['phase'],'first_replica_change_seconds':None if first is None else first['elapsed']-phase['elapsed'],'censored':first is None})
        summaries.append({'scenario':name,'controller':args.controller,'requests':len(subset),'failed':sum(r['failed'] for r in subset),
           'p95_ms':float(np.percentile([r['latency_ms'] for r in subset],95)),'p99_ms':float(np.percentile([r['latency_ms'] for r in subset],99)),
           'slo_violation_fraction':sum(r['slo_bad'] for r in subset)/len(subset),'slo_met':sum(r['slo_bad'] for r in subset)/len(subset)<=.01,
           'desired_replica_min':min([o['desired'] for o in obs],default=None),'desired_replica_max':max([o['desired'] for o in obs],default=None),
           'sampled_pod_minutes':pod_minutes,'scaling_response':changes})
    phase_durations=[phase_events[i+1]['elapsed']-p['elapsed'] for i,p in enumerate(phase_events[:-1])]
    protocol_valid=all(abs(d-args.phase_seconds)<2 for d in phase_durations) and max(r['schedule_delay_ms'] for r in requests)<2000
    (folder/'summary.json').write_text(json.dumps({'status':'completed','phase_seconds':args.phase_seconds,'warmup_seconds':args.warmup_seconds,'elapsed_seconds':elapsed,'protocol_valid':protocol_valid,'phase_durations':phase_durations,'maximum_schedule_delay_ms':max(r['schedule_delay_ms'] for r in requests),'scenarios':summaries,
        'scope':'consecutive short integration scenarios, no per-scenario reset; no repeated statistical comparison; five minute downscale window can censor short phases'},indent=2))
    (folder/'deployment.json').write_text(kube('get','deployment/sample-api','-n','guruge-repro','-o','json'))
    (folder/'pods.json').write_text(kube('get','pods','-n','guruge-repro','-o','json'))
    (folder/'hpa-final.json').write_text(kube('get','hpa','-n','guruge-repro','-o','json'))
    (folder/'events.txt').write_text(kube('get','events','-n','guruge-repro','--sort-by=.lastTimestamp'))
    print(json.dumps(summaries,indent=2),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--controller',choices=['forecast','hpa'],required=True);ap.add_argument('--run-id',required=True)
    ap.add_argument('--phase-seconds',type=int,default=30);ap.add_argument('--warmup-seconds',type=int,default=60);ap.add_argument('--url',default='http://127.0.0.1:30080');args=ap.parse_args()
    asyncio.run(run(args))
