"""Causal ordering, emergency and actuation invariants before final experiments."""
from pathlib import Path
import json,copy
from controller_v2 import GuardedController
ROOT=Path(__file__).resolve().parent
development=[]
for name in ['development-capacity-01','development-capacity-02','development-capacity-03']:
    development+=json.loads((ROOT/name/'summary.json').read_text())

def obs(r=5,n=8,ready=8,tail=150,bad=0):
    return {'rps':r,'desired':n,'ready':ready,'effective_p99_ms':tail,'cpu_ms':50.,'cpu_p90_ms':55.,'requests':100,'slo_bad_count':bad,'slo_violation_fraction':bad/100}
def run(seq,mode='guarded'):
    c=GuardedController(development,mode);out=[]
    for i,o in enumerate(seq):
        d=c.decide(copy.deepcopy(o),i);d.pop('elapsed_ms');out.append(d)
    return out

prefix=[obs(5),obs(10),obs(20)]
assert run(prefix+[obs(100)])[0:3]==run(prefix+[obs(1)])[0:3]
d=run([obs(tail=2000,bad=5)])[0];assert d['target']==16 and d['emergency']
assert all(8<=d['target']<=16 for d in run([obs()]*20))
assert run([obs(n=12,ready=8)]*10)[-1]['target']>=12
assert len(run([obs()]*3)[0]['demand_coverage_updates'])==0
assert len(run([obs()]*3)[2]['demand_coverage_updates'])==1
assert run([obs()]*10,'no_reserve')[-1]['target']<8
assert run([obs(bad=3)]+[obs()]*3)[-1]['budget_hold']
report={'status':'passed','future_prefix_invariance':True,'delayed_horizon_scoring':True,'reserve_and_maximum_limits':True,'pending_capacity_not_cancelled':True,'emergency_scale_up':True,'reserve_ablation_changes_policy':True,'budget_guard':True}
(ROOT/'controller-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
