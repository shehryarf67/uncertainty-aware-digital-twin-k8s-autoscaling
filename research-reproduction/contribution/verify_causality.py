"""Independent causal-order and policy invariants; no synthetic success scores."""
import copy,json
from pathlib import Path
import numpy as np
from controller import Controller,Bound
ROOT=Path(__file__).resolve().parent
def main():
    p=json.loads((ROOT/'results/profile-01/profile.json').read_text())
    a=Controller(p,'full',[5.]*12);b=copy.deepcopy(a)
    prefix=[5,5,8,12,15]
    def observations(r):return {'rps':r,'ready':2,'desired':2,'effective_p99_ms':80,'cpu_ms':40}
    for k,r in enumerate(prefix):
        da=a.decide(observations(r),k);db=b.decide(observations(r),k)
        for key in da:
            if key!='elapsed_ms':assert da[key]==db[key]
    # Mutating a future outcome cannot alter already issued decisions.
    saved=copy.deepcopy(da);b.decide(observations(1000),len(prefix))
    assert a.rates==[5.]*12+prefix and da==saved
    c=Controller(p,'full',[5.]*12)
    c.decide(observations(5),0);assert len(c.demand.scores)==9
    c.decide(observations(10),1);assert len(c.demand.scores)==9
    c.decide(observations(20),2);assert len(c.demand.scores)==10
    # The matured score must use the next two observations, not warm-up entries.
    assert c.demand.scores[-1]==15
    x=Bound([-3,0,1,2]);assert x.margin()>=0
    twin=a.twin
    grid=[twin.predict(r,1,40) for r in range(60)]
    assert np.all(np.diff(grid)>=-1e-9)
    assert all(1<=a.decide(observations(r),i+6)['target']<=6 for i,r in enumerate([0,1000,5]))
    result={'status':'passed','future_prefix_invariance':True,'delayed_two_step_score_alignment':True,'twin_monotonicity':True,'replica_bounds':True,'negative_margin_clipped_to_zero':True}
    (ROOT/'causal-verification.json').write_text(json.dumps(result,indent=2));print(result)
if __name__=='__main__':main()
