"""Pre-evaluation capacity checks, kept separate from final testing."""
from pathlib import Path
import sys,json,asyncio,time,httpx
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'contribution'))
from live import api,scale,ready,traffic,stats,write_requests,state

async def main():
    out=ROOT/'development-capacity-01';out.mkdir(exist_ok=False)
    try:api('DELETE','/apis/autoscaling/v2/namespaces/twin-research/horizontalpodautoscalers/research-cpu')
    except httpx.HTTPStatusError as e:
        if e.response.status_code!=404:raise
    all_records=[];rows=[];start=time.monotonic()
    async with httpx.AsyncClient(timeout=3,limits=httpx.Limits(max_connections=200,max_keepalive_connections=0)) as client:
        for n in [4,6]:
            scale(n);await ready(n)
            warm=[];await traffic(client,5,1,5,111,warm,-1,start)
            for r,u in [(5,1),(25,1),(45,1),(30,1.8)]:
                block=len(rows);a=len(all_records)
                duration=await traffic(client,r,u,5,9000+block,all_records,block,start)
                row={'replicas':n,'rps':r,'units':u,'duration_seconds':duration,**stats(all_records[a:])};rows.append(row)
                print(json.dumps(row),flush=True)
                (out/'summary.json').write_text(json.dumps(rows,indent=2))
    write_requests(out/'requests.csv',all_records)

if __name__=='__main__':asyncio.run(main())
