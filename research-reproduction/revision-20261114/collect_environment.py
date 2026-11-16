"""Record reproducibility facts without authentication or machine identifiers."""
from pathlib import Path
import json,sys,importlib.metadata,platform,datetime
from experiments import api,NS
ROOT=Path(__file__).resolve().parent
node=api('GET','/api/v1/nodes')['items'][0]['status']
deployment=api('GET',NS)['spec']['template']['spec']['containers'][0]
pods=api('GET','/api/v1/namespaces/twin-research/pods')['items']
images=sorted({c['imageID'] for p in pods for c in p.get('status',{}).get('containerStatuses',[])})
r={'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),'dependencies':{n:importlib.metadata.version(n) for n in ['numpy','pandas','scikit-learn','httpx']},'kubernetes':api('GET','/version'),'node':{k:node['nodeInfo'][k] for k in ['architecture','containerRuntimeVersion','kernelVersion','kubeletVersion','operatingSystem','osImage']},'capacity':{k:node['capacity'][k] for k in ['cpu','memory']},'application':{'image':deployment['image'],'resolved_image_ids':images,'resources':deployment['resources'],'readiness_probe':deployment['readinessProbe']},'scope':'Only local research environment facts; no kubeconfig, auth tokens or machine identity'}
(ROOT/'environment.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
