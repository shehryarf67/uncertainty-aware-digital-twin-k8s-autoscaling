"""Capacity-calibrated, readiness-aware guard; no future traffic inputs."""
from collections import deque
import math,time
import numpy as np
from sklearn.isotonic import IsotonicRegression

class GuardedController:
    def __init__(self,development,mode='guarded',initial_rates=(5.,5.),initial_cpu=50.,limit=16,period=8.):
        self.mode=mode;self.limit=limit;self.period=period;self.reserve=8 if mode=='guarded' else 1
        x=[r['rps']*r['cpu_ms']/r['replicas'] for r in development]
        self.model=IsotonicRegression(out_of_bounds='clip',y_min=1).fit(x,[r['effective_p99_ms'] for r in development])
        supported=[v for v,r in zip(x,development) if r['slo_violation_fraction']<=.01 and r['p99_ms']<=400]
        assert supported,'A measured safe development operating point is required'
        self.safe_work=min(200.,.8*max(supported));self.xmax=max(x)
        self.rates=list(initial_rates);self.cpu_history=deque([initial_cpu],maxlen=4)
        self.scores=deque(maxlen=40);self.pending=[];self.factor=1.;self.clean=0;self.down=0
        self.startup=8.;self.pending_scale=None;self.requests=0;self.bad=0;self.emergency_hold=0

    def decide(self,obs,index):
        started=time.perf_counter();rate=float(obs['rps']);current=int(obs['desired']);ready=int(obs['ready'])
        clock=float(obs.get('clock_seconds',(index+1)*self.period))
        if self.pending_scale is not None and ready>=self.pending_scale[1]:
            self.startup=max(self.period,.5*self.startup+.5*(clock-self.pending_scale[0]));self.pending_scale=None
        horizon=max(2,min(6,math.ceil(self.startup/self.period)+1))
        history=self.rates+[rate];origin=len(history)-1;coverage=[]
        for p in self.pending:
            if origin>=p['origin']+p['horizon']:
                score=max(history[p['origin']+1:p['origin']+p['horizon']+1])-p['point']
                coverage.append(score<=p['margin']);self.scores.append(float(score))
        self.pending=[p for p in self.pending if origin<p['origin']+p['horizon']]
        self.rates.append(rate)
        c=obs.get('cpu_p90_ms') or obs.get('cpu_ms')
        if c is not None:self.cpu_history.append(float(c))
        cpu=max(self.cpu_history)
        recent=self.rates[-3:];trend=max(0.,recent[-1]-recent[-2]) if len(recent)>1 else 0.
        point=max(max(recent),rate+horizon*trend)
        # At 99% nominal coverage with <=40 scores, the finite rank is their max.
        rank=min(len(self.scores),math.ceil((len(self.scores)+1)*.99))
        margin=max(0.,sorted(self.scores)[rank-1]) if rank else 0.
        upper=point+margin
        requests=int(obs.get('requests',0));bad=int(obs.get('slo_bad_count',round(requests*obs.get('slo_violation_fraction',0))))
        self.requests+=requests;self.bad+=bad
        miss=float(obs.get('slo_violation_fraction',0));tail=float(obs['effective_p99_ms'])
        if miss>.005 or tail>450:
            self.factor=max(.5,self.factor*.85);self.clean=0;self.emergency_hold=3
        else:
            self.clean+=1
            if self.clean>=8:self.factor=min(1.,self.factor+.025)
        required=math.ceil(upper*cpu/(self.safe_work*self.factor))+2
        wanted=max(self.reserve,min(self.limit,required))
        emergency=miss>.01 or tail>500 or self.emergency_hold>0
        if emergency:wanted=self.limit;self.emergency_hold=max(0,self.emergency_hold-1)
        budget_hold=self.bad/max(1,self.requests)>.005
        # Avoid cancelling capacity still becoming ready; remove at most one pod.
        if wanted>=current:target=wanted;self.down=0
        else:
            self.down+=1
            target=max(wanted,current-1) if self.down>=3 and ready>=current and self.clean>=3 and not budget_hold else current
        if target>current:self.pending_scale=(clock,target)
        pred=float(self.model.predict([upper*cpu/max(1,target)])[0])
        supported=upper*cpu/max(1,target)<=self.xmax
        self.pending.append({'origin':origin,'horizon':horizon,'point':point,'margin':margin})
        return {'target':int(target),'point_rps':point,'upper_rps':upper,'demand_margin':margin,'cpu_estimate_ms':cpu,'safe_cpu_work_ms_per_second':self.safe_work,'risk_capacity_factor':self.factor,'reserve':self.reserve,'planning_horizon':horizon,'estimated_startup_seconds':self.startup,'predicted_p99_ms':pred,'supported':supported,'feasible':bool(supported and pred<=500 and required<=self.limit),'demand_coverage_updates':coverage,'cumulative_violation_fraction':self.bad/max(1,self.requests),'budget_hold':budget_hold,'emergency':emergency,'elapsed_ms':(time.perf_counter()-started)*1000}
