"""Real Kubernetes service profiling and controlled repeated controller tests."""
import argparse,asyncio,csv,json,os,time,subprocess,random
from pathlib import Path
import numpy as np,httpx
from controller import Controller,Twin
ROOT=Path(__file__).resolve().parent
API='http://127.0.0.1:8001';NS='/apis/apps/v1/namespaces/twin-research/deployments/twin-service'
NODE=subprocess.check_output(['hostname','-I'],text=True).split()[0]
URL=f'http://{NODE}:30081/work'
def api(method,path,body=None):
    r=httpx.request(method,API+path,json=body,headers={'Content-Type':'application/merge-patch+json'} if method=='PATCH' else None,timeout=15);r.raise_for_status();return r.json() if r.content else {}
def state():
    d=api('GET',NS);return {'desired':d['spec']['replicas'],'ready':d.get('status',{}).get('readyReplicas',0)}
def scale(n):return api('PATCH',NS+'/scale',{'spec':{'replicas':int(n)}})
async def ready(n):
    start=time.monotonic()
    while time.monotonic()-start<150:
        s=await asyncio.to_thread(state)
        if s['ready']==n and s['desired']==n:return
        await asyncio.sleep(1)
    raise RuntimeError('Readiness timed out')
async def traffic(client,rps,units,seconds,seed,records,block,start0):
    # Common seeded jitter in each request slot; no future schedule enters control.
    rng=random.Random(seed);start=time.monotonic();tasks=[]
    async def hit(scheduled):
        sent=time.monotonic();status=0;data={};err=''
        try:
            response=await client.get(URL,params={'units':units});status=response.status_code
            if status==200:data=response.json()
        except Exception as e:err=str(e)
        latency=(time.monotonic()-sent)*1000
        records.append({'block':block,'elapsed':sent-start0,'latency_ms':latency,'status':status,'cpu_ms':data.get('cpu_ms'),'pod':data.get('pod',''),'schedule_delay_ms':(sent-scheduled)*1000,'slo_bad':status!=200 or latency>500,'error':err})
    for i in range(int(rps*seconds)):
        scheduled=start+(i+rng.random()*.15)/rps
        await asyncio.sleep(max(0,scheduled-time.monotonic()))
        tasks.append(asyncio.create_task(hit(scheduled)))
    await asyncio.sleep(max(0,start+seconds-time.monotonic()))
    # Fixed three-second drain for every policy: controlled batch cycles, not
    # uninterrupted production traffic. No response from a future cycle is used.
    await asyncio.gather(*tasks)
    await asyncio.sleep(max(0,start+seconds+3-time.monotonic()))
    return time.monotonic()-start
def stats(records):
    l=[r['latency_ms'] for r in records];effective=[r['latency_ms'] if r['status']==200 else max(2000,r['latency_ms']) for r in records]
    cpu=[r['cpu_ms'] for r in records if r['cpu_ms'] is not None]
    return {'p95_ms':float(np.percentile(l,95)),'p99_ms':float(np.percentile(l,99)),'effective_p99_ms':float(np.percentile(effective,99)),'cpu_ms':float(np.median(cpu)) if cpu else None,'failed':sum(r['status']!=200 for r in records),'slo_violation_fraction':sum(r['slo_bad'] for r in records)/len(records),'requests':len(records)}
def write_requests(path,records):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
async def profile():
    folder=ROOT/'results/profile-01';folder.mkdir(parents=True,exist_ok=False);scale(1);await ready(1)
    conditions=[(r,u,'fit') for u in [.75,1.,1.25] for r in [5,8,11,14,17,20]]+[(r,u,'calibration') for u in [.8,1.2] for r in [6,9,12,15,18,21]]
    records=[];rows=[];start=time.monotonic()
    async with httpx.AsyncClient(timeout=3,limits=httpx.Limits(max_connections=200,max_keepalive_connections=0)) as c:
        warm=[];await traffic(c,5,1,5,0,warm,-1,start)
        for i,(r,u,part) in enumerate(conditions):
            a=len(records);duration=await traffic(c,r,u,5,1000+i,records,i,start);s=stats(records[a:])
            rows.append({'block':i,'rps':r,'units':u,'replicas':1,'partition':part,'duration_seconds':duration,**s})
            print('profile',i,r,u,s['p99_ms'],s['failed'],flush=True)
            (folder/'profile.json').write_text(json.dumps(rows,indent=2))
    write_requests(folder/'requests.csv',records)
    (folder/'status.json').write_text(json.dumps({'status':'completed','profile_blocks':len(rows),'scope':'separate CPU service, five-second offered load and fixed three-second drain per cycle'},indent=2))
async def experiments():
    profile=json.loads((ROOT/'results/profile-01/profile.json').read_text())
    # Four workload phases plus an unseen service-cost shift, all fixed before tests.
    rates=[5,5,5,5,10,15,20,25,45,45,15,10,25,30,15,5]
    units=[1.]*12+[1.8]*4
    modes=['point','workload_only','twin_only','full','cpu_hpa']
    for seed in [101,202,303]:
        order=modes.copy();random.Random(seed).shuffle(order)
        for mode in order:
            folder=ROOT/'results/live-01'/f'{seed}-{mode}';folder.mkdir(parents=True,exist_ok=False)
            path='/apis/autoscaling/v2/namespaces/twin-research/horizontalpodautoscalers'
            try:await asyncio.to_thread(api,'DELETE',path+'/research-cpu')
            except httpx.HTTPStatusError as e:
                if e.response.status_code!=404:raise
            scale(1);await ready(1)
            if mode=='cpu_hpa':
                body={'apiVersion':'autoscaling/v2','kind':'HorizontalPodAutoscaler','metadata':{'name':'research-cpu','namespace':'twin-research'},'spec':{'scaleTargetRef':{'apiVersion':'apps/v1','kind':'Deployment','name':'twin-service'},'minReplicas':1,'maxReplicas':6,'metrics':[{'type':'Resource','resource':{'name':'cpu','target':{'type':'Utilization','averageUtilization':70}}}],'behavior':{'scaleDown':{'stabilizationWindowSeconds':24},'scaleUp':{'stabilizationWindowSeconds':0}}}}
                await asyncio.to_thread(api,'POST',path,body)
            controller=Controller(profile,mode,[5.]*12)
            records=[];obs=[];start=time.monotonic()
            async with httpx.AsyncClient(timeout=3,limits=httpx.Limits(max_connections=200,max_keepalive_connections=0)) as c:
                warm=[]
                for _ in range(2):await traffic(c,5,1,5,seed,warm,-1,start)
                start=time.monotonic()
                for i,(r,u) in enumerate(zip(rates,units)):
                    s=await asyncio.to_thread(state);before=time.monotonic()-start;a=len(records)
                    duration=await traffic(c,r,u,5,seed*100+i,records,i,start);measurement=stats(records[a:])
                    # Replica state is sampled at cycle start; future readiness is not known.
                    sample={'rps':len(records[a:])/5,**s,**measurement}
                    decision=controller.decide(sample,i)
                    if mode!='cpu_hpa' and decision['target']!=s['desired']:await asyncio.to_thread(scale,decision['target'])
                    try:
                        metrics=await asyncio.to_thread(api,'GET','/apis/metrics.k8s.io/v1beta1/namespaces/twin-research/pods')
                    except Exception:metrics={'items':[]}
                    obs.append({'block':i,'elapsed':before,'duration_seconds':duration,'offered_units':u,'sample':sample,'decision':decision,'pod_metrics':metrics})
                    print('live',seed,mode,i,'replicas',s,'p99',round(measurement['p99_ms'],1),'bad',round(measurement['slo_violation_fraction'],3),flush=True)
                    (folder/'observations.json').write_text(json.dumps(obs,indent=2))
            write_requests(folder/'requests.csv',records)
            summary={'status':'completed','seed':seed,'controller':mode,'protocol':'five-second traffic plus fixed three-second drain; randomized controller order; two warm-up cycles','order':order,'elapsed_seconds':time.monotonic()-start,**stats(records)}
            summary['sampled_desired_pod_minutes']=sum(o['sample']['desired']*o['duration_seconds']/60 for o in obs)
            summary['max_schedule_delay_ms']=max(r['schedule_delay_ms'] for r in records)
            summary['phase_valid']=all(o['duration_seconds']<9 for o in obs) and summary['max_schedule_delay_ms']<500
            (folder/'summary.json').write_text(json.dumps(summary,indent=2))
            print('completed',seed,mode,summary['phase_valid'],flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['profile','experiments']);a=p.parse_args();asyncio.run(profile() if a.command=='profile' else experiments())
