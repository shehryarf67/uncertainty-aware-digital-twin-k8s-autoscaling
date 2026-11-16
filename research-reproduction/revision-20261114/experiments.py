"""Repeated real-cluster trials with absolute-time traffic and independent sampling."""
from pathlib import Path
import asyncio,csv,json,time,random,sys,traceback,argparse,hashlib
import numpy as np,httpx
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'contribution'))
from controller import Controller
from controller_v2 import GuardedController
API='http://127.0.0.1:8001';NS='/apis/apps/v1/namespaces/twin-research/deployments/twin-service'
HPA='/apis/autoscaling/v2/namespaces/twin-research/horizontalpodautoscalers'

def api(method,path,body=None):
    for attempt in range(3):
        try:
            r=httpx.request(method,API+path,json=body,headers={'Content-Type':'application/merge-patch+json'} if method=='PATCH' else None,timeout=15)
            r.raise_for_status();return r.json() if r.content else {}
        except (httpx.TransportError,httpx.HTTPStatusError) as e:
            if isinstance(e,httpx.HTTPStatusError) and e.response.status_code<500:raise
            if attempt==2:raise
            time.sleep(1)

def state():
    d=api('GET',NS);return {'desired':int(d['spec']['replicas']),'ready':int(d.get('status',{}).get('readyReplicas',0))}
def scale(n):return api('PATCH',NS+'/scale',{'spec':{'replicas':int(n)}})
async def wait_ready(n):
    end=time.monotonic()+180
    while time.monotonic()<end:
        s=await asyncio.to_thread(state)
        if s['desired']==s['ready']==n:return
        await asyncio.sleep(1)
    raise RuntimeError('Replica readiness timeout')
def summarize(rows):
    if not rows:return {'requests':0,'slo_bad_count':0,'slo_violation_fraction':0.,'p95_ms':0.,'p99_ms':0.,'effective_p99_ms':0.,'cpu_ms':None,'cpu_p90_ms':None,'failed':0}
    lat=[r['latency_ms'] for r in rows];cpu=[r['cpu_ms'] for r in rows if r['cpu_ms'] is not None]
    bad=sum(r['status']!=200 or r['latency_ms']>500 for r in rows)
    return {'requests':len(rows),'slo_bad_count':bad,'slo_violation_fraction':bad/len(rows),'p95_ms':float(np.percentile(lat,95)),'p99_ms':float(np.percentile(lat,99)),'effective_p99_ms':float(np.percentile([max(2000,r['latency_ms']) if r['status']!=200 else r['latency_ms'] for r in rows],99)),'cpu_ms':float(np.median(cpu)) if cpu else None,'cpu_p90_ms':float(np.percentile(cpu,90)) if cpu else None,'failed':sum(r['status']!=200 for r in rows)}

async def produce(client,url,rates,units,active_seconds,seed,start,rows,sent,tasks):
    rng=random.Random(seed)
    async def hit(block,request_id,scheduled,u):
        sent_at=time.monotonic()-start;sent[request_id]=sent_at;status=0;data={};error=''
        try:
            response=await client.get(url,params={'units':u});status=response.status_code
            if status==200:data=response.json()
        except Exception as e:error=type(e).__name__
        finish=time.monotonic()-start
        rows.append({'request_id':request_id,'block':block,'sent_seconds':sent_at,'finished_seconds':finish,'latency_ms':(finish-sent_at)*1000,'status':status,'cpu_ms':data.get('cpu_ms'),'queue_ms':data.get('queue_ms'),'service_wall_ms':data.get('service_wall_ms'),'pod':data.get('pod',''),'schedule_delay_ms':(start+sent_at-scheduled)*1000,'error':error})
    for block,(rate,u) in enumerate(zip(rates,units)):
        for i in range(int(rate*active_seconds)):
            scheduled=start+block*8+(i+rng.random()*.15)/rate
            await asyncio.sleep(max(0,scheduled-time.monotonic()))
            tasks.append(asyncio.create_task(hit(block,f'{block}-{i}',scheduled,u)))
    await asyncio.sleep(max(0,start+len(rates)*8-time.monotonic()))
    await asyncio.gather(*tasks)

async def monitor(start,stop,samples):
    while not stop.is_set():
        begin=time.monotonic()
        try:samples.append({'time':begin-start,**await asyncio.to_thread(state)})
        except Exception as e:samples.append({'time':begin-start,'error':type(e).__name__})
        try:await asyncio.wait_for(stop.wait(),timeout=max(.01,1-(time.monotonic()-begin)))
        except asyncio.TimeoutError:pass

def save_csv(path,rows):
    if not rows:return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

async def trial(protocol,scenario,seed,mode,attempt=1):
    name=f'{scenario}-{seed}-{mode}-attempt{attempt:02d}';out=ROOT/'results/live'/name
    out.mkdir(parents=True,exist_ok=False);rows=[];observations=[];samples=[];stop=asyncio.Event();status='failed';mon=None;producer=None;tasks=[]
    cfg=protocol['scenarios'][scenario];limit=protocol['replica_limit'];initial=limit if mode=='static' else protocol['initial_replicas']
    try:
        try:await asyncio.to_thread(api,'DELETE',HPA+'/research-cpu')
        except httpx.HTTPStatusError as e:
            if e.response.status_code!=404:raise
        await asyncio.to_thread(scale,initial);await wait_ready(initial)
        node=api('GET','/api/v1/nodes')['items'][0]
        ip=next(x['address'] for x in node['status']['addresses'] if x['type']=='InternalIP');url=f'http://{ip}:30081/work'
        async with httpx.AsyncClient(timeout=3,limits=httpx.Limits(max_connections=200,max_keepalive_connections=0)) as client:
            warm=[];warm_sent={};warm_tasks=[];warm_start=time.monotonic()
            await produce(client,url,[5,5],[1,1],5,seed,warm_start,warm,warm_sent,warm_tasks)
            warm_stats=summarize(warm)
            development=[]
            for run in ['development-capacity-01','development-capacity-02','development-capacity-03']:
                development.extend(json.loads((ROOT/run/'summary.json').read_text()))
            if mode in ['guarded','no_reserve']:
                ctrl=GuardedController(development,mode,[5.,5.],warm_stats['cpu_p90_ms'] or 50.,limit)
            elif mode=='legacy':
                profile=json.loads((ROOT.parent/'contribution/results/profile-01/profile.json').read_text())
                ctrl=Controller(profile,'full',[5.]*12,limit=limit)
            else:ctrl=None
            if mode=='cpu_hpa':
                body={'apiVersion':'autoscaling/v2','kind':'HorizontalPodAutoscaler','metadata':{'name':'research-cpu','namespace':'twin-research'},'spec':{'scaleTargetRef':{'apiVersion':'apps/v1','kind':'Deployment','name':'twin-service'},'minReplicas':1,'maxReplicas':limit,'metrics':[{'type':'Resource','resource':{'name':'cpu','target':{'type':'Utilization','averageUtilization':70}}}],'behavior':{'scaleDown':{'stabilizationWindowSeconds':24},'scaleUp':{'stabilizationWindowSeconds':0}}}}
                await asyncio.to_thread(api,'POST',HPA,body)
            sent={};start=time.monotonic();mon=asyncio.create_task(monitor(start,stop,samples))
            producer=asyncio.create_task(produce(client,url,cfg['rates'],cfg['units'],cfg['active_seconds'],seed,start,rows,sent,tasks))
            for block in range(len(cfg['rates'])):
                cutoff=(block+1)*8;await asyncio.sleep(max(0,start+cutoff-time.monotonic()))
                now=time.monotonic()-start;completed=[r for r in rows if cutoff-8<=r['finished_seconds']<cutoff]
                measurement=summarize(completed)
                finished={r['request_id'] for r in rows if r['finished_seconds']<cutoff}
                ages=[(cutoff-t)*1000 for i,t in sent.items() if t<cutoff and i not in finished]
                effective=[max(2000,r['latency_ms']) if r['status']!=200 else r['latency_ms'] for r in completed]+ages
                if effective:measurement['effective_p99_ms']=float(np.percentile(effective,99))
                observed_arrivals=sum(cutoff-8<=t<cutoff for t in sent.values())
                s=await asyncio.to_thread(state)
                sample={**measurement,**s,'rps':observed_arrivals/cfg['active_seconds'],'clock_seconds':now}
                decision=ctrl.decide(sample,block) if ctrl else {'target':limit if mode=='static' else s['desired'],'elapsed_ms':0.}
                if mode not in ['cpu_hpa','static'] and decision['target']!=s['desired']:await asyncio.to_thread(scale,decision['target'])
                observations.append({'block':block,'cutoff_seconds':cutoff,'decision_time_seconds':now,'observed_arrivals':observed_arrivals,'pending_responses':len(ages),'sample':sample,'decision':decision})
                (out/'observations.json').write_text(json.dumps(observations,indent=2))
                save_csv(out/'requests.csv',rows)
                print(name,block,'ready',s['ready'],'desired',s['desired'],'target',decision['target'],'bad',round(measurement['slo_violation_fraction'],4),flush=True)
            await producer;producer=None
            elapsed=time.monotonic()-start;status='completed'
    except Exception:
        (out/'failure.txt').write_text(traceback.format_exc());print('FAILED',name,traceback.format_exc(),flush=True)
    finally:
        if producer is not None:
            producer.cancel();await asyncio.gather(producer,return_exceptions=True)
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        stop.set()
        if mon is not None:await mon
        save_csv(out/'requests.csv',rows)
        (out/'observations.json').write_text(json.dumps(observations,indent=2));(out/'replicas.json').write_text(json.dumps(samples,indent=2))
    expected=sum(int(r*cfg['active_seconds']) for r in cfg['rates'])
    valid_samples=[x for x in samples if 'desired' in x]
    gaps=[b['time']-a['time'] for a,b in zip(valid_samples,valid_samples[1:])]
    allocation=sum(a['desired']*(b['time']-a['time'])/60 for a,b in zip(valid_samples,valid_samples[1:]))
    if status=='completed' and valid_samples:allocation+=valid_samples[-1]['desired']*max(0,elapsed-valid_samples[-1]['time'])/60
    report={'status':status,'trial':name,'scenario':scenario,'seed':seed,'controller':mode,'attempt':attempt,'initial_replicas':initial,'replica_limit':limit,'expected_requests':expected,**summarize(rows),'desired_pod_minutes':allocation,'max_schedule_delay_ms':max((r['schedule_delay_ms'] for r in rows),default=0),'max_sampler_gap_seconds':max(gaps,default=0),'monitor_errors':sum('error' in x for x in samples),'max_decision_lateness_seconds':max((o['decision_time_seconds']-o['cutoff_seconds'] for o in observations),default=0)}
    report['protocol_valid']=status=='completed' and len(rows)==expected and len(observations)==len(cfg['rates']) and report['max_schedule_delay_ms']<500 and report['max_sampler_gap_seconds']<3 and report['monitor_errors']==0 and report['max_decision_lateness_seconds']<1
    (out/'summary.json').write_text(json.dumps(report,indent=2));print('COMPLETED',name,json.dumps(report),flush=True)
    return report

async def main():
    protocol=json.loads((ROOT/'frozen-protocol.json').read_text())
    (ROOT/'results').mkdir(exist_ok=True)
    for seed in protocol['seeds']:
        scenarios=list(protocol['scenarios']);random.Random(seed+999).shuffle(scenarios)
        for scenario in scenarios:
            modes=protocol['controllers'].copy();random.Random(seed+sum(map(ord,scenario))).shuffle(modes)
            for mode in modes:
                results=[]
                for attempt in [1,2]:
                    f=ROOT/'results/live'/f'{scenario}-{seed}-{mode}-attempt{attempt:02d}'/'summary.json'
                    if f.exists():r=json.loads(f.read_text())
                    else:r=await trial(protocol,scenario,seed,mode,attempt)
                    results.append(r)
                    if r['protocol_valid']:break
                if not any(r['protocol_valid'] for r in results):
                    raise RuntimeError('Two invalid attempts require investigation; both retained')
    (ROOT/'results/live-status.json').write_text(json.dumps({'status':'completed','scheduled_comparisons':len(protocol['seeds'])*len(protocol['scenarios'])*len(protocol['controllers']),'all_attempts_retained':True},indent=2))

if __name__=='__main__':asyncio.run(main())
