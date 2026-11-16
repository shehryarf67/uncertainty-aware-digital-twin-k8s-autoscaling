"""Reserve-matched follow-up: reuse frozen harness; HPA minimum alone becomes 8."""
from pathlib import Path
import asyncio,copy,json,hashlib
import experiments as E
ROOT=Path(__file__).resolve().parent

def main():
    p=json.loads((ROOT/'reserve-followup/frozen-protocol.json').read_text())
    assert hashlib.sha256((ROOT/'experiments.py').read_bytes()).hexdigest()==p['base_harness_sha256']
    assert hashlib.sha256((ROOT/'controller_v2.py').read_bytes()).hexdigest()==p['controller_sha256']
    original_api=E.api
    def api(method,path,body=None):
        if method=='POST' and path==E.HPA:
            body=copy.deepcopy(body);body['spec']['minReplicas']=8
        return original_api(method,path,body)
    E.api=api
    E.ROOT=ROOT/'reserve-followup'
    asyncio.run(E.main())

if __name__=='__main__':main()
