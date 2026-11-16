"""Independent conditional response validation; no controller refitting."""
from pathlib import Path
import asyncio,json,time,httpx,numpy as np
from experiments import api,HPA,scale,wait_ready,produce,summarize,save_csv
from controller_v2 import GuardedController
ROOT=Path(__file__).resolve().parent

async def main():
    p=json.loads((ROOT/'validation-protocol.json').read_text());out=ROOT/'results/twin-validation';out.mkdir(exist_ok=False)
    development=[]
    for name in ['development-capacity-01','development-capacity-02','development-capacity-03']:development+=json.loads((ROOT/name/'summary.json').read_text())
    twin=GuardedController(development);all_rows=[];conditions=[]
    try:api('DELETE',HPA+'/research-cpu')
    except httpx.HTTPStatusError as e:
        if e.response.status_code!=404:raise
    node=api('GET','/api/v1/nodes')['items'][0]
    ip=next(x['address'] for x in node['status']['addresses'] if x['type']=='InternalIP');url=f'http://{ip}:30081/work'
    async with httpx.AsyncClient(timeout=3,limits=httpx.Limits(max_connections=200,max_keepalive_connections=0)) as client:
        for n in p['replicas']:
            scale(n);await wait_ready(n)
            await produce(client,url,[5],[1],5,11000,time.monotonic(),[],{},[])
            for rate in p['rates']:
                for units in p['work_units']:
                    block=len(conditions);rows=[];start=time.monotonic()
                    await produce(client,url,[rate],[units],5,11000+block,start,rows,{},[])
                    s=summarize(rows);x=rate*s['cpu_ms']/n;pred=float(twin.model.predict([x])[0])
                    conditions.append({'block':block,'replicas':n,'rate':rate,'units':units,'x_cpu_ms_per_second':x,'predicted_effective_p99_ms':pred,'envelope_predicts_safe':x<=twin.safe_work,'model_supported':x<=twin.xmax,'max_dispatch_delay_ms':max(r['schedule_delay_ms'] for r in rows),**s})
                    for row in rows:row['request_id']=str(block)+':'+row['request_id'];row['validation_block']=block
                    all_rows+=rows;save_csv(out/'requests.csv',all_rows)
                    (out/'conditions.json').write_text(json.dumps(conditions,indent=2));print('validation',n,rate,units,s['slo_violation_fraction'],flush=True)
    errors=[abs(r['predicted_effective_p99_ms']-r['effective_p99_ms']) for r in conditions]
    report={'status':'completed','conditions':len(conditions),'requests':len(all_rows),'effective_p99_mae_ms':float(np.mean(errors)),'median_absolute_error_ms':float(np.median(errors)),'conditions_meeting_slo':sum(r['slo_violation_fraction']<=.01 for r in conditions),'envelope_safe_conditions':sum(r['envelope_predicts_safe'] for r in conditions),'false_safe_conditions':sum(r['envelope_predicts_safe'] and r['slo_violation_fraction']>.01 for r in conditions),'all_dispatch_valid':all(r['max_dispatch_delay_ms']<500 for r in conditions),'scope':'Independent conditional response-map validation; realized CPU input; no ex-ante CPU forecasting or full-cluster counterfactual guarantee; no refitting'}
    assert report['conditions']==18 and report['requests']==2160
    (out/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':asyncio.run(main())
