"""Forecaster-independent dual residual calibration and empirical latency Twin."""
from collections import deque
import math,time
import numpy as np
from sklearn.isotonic import IsotonicRegression

class Bound:
    def __init__(self,scores,alpha=.1,gamma=.01,window=40):
        self.scores=deque([float(s) for s in scores],maxlen=window);self.target=alpha;self.alpha=alpha;self.gamma=gamma
    def margin(self):
        # Clipping is an engineering guard; no unmodified ACI theorem is claimed.
        a=np.clip(self.alpha,.025,.4);m=len(self.scores)
        rank=min(m,max(1,math.ceil((m+1)*(1-a))))
        return max(0,float(np.sort(self.scores)[rank-1])) if m else 0
    def update(self,score,margin):
        miss=score>margin;self.alpha=float(np.clip(self.alpha+self.gamma*(self.target-int(miss)),.025,.4));self.scores.append(float(score));return not miss

class Twin:
    def __init__(self,profile):
        fit=[r for r in profile if r['partition']=='fit']
        self.model=IsotonicRegression(out_of_bounds='clip',y_min=1)
        self.model.fit([r['rps']*r['cpu_ms']/r['replicas'] for r in fit],[r['effective_p99_ms'] for r in fit])
        self.xmax=max(r['rps']*r['cpu_ms']/r['replicas'] for r in fit)
        cal=[r for r in profile if r['partition']=='calibration']
        self.cal_scores=[r['effective_p99_ms']-self.predict(r['rps'],r['replicas'],r['cpu_ms']) for r in cal]
        self.cpu_reference=float(np.median([r['cpu_ms'] for r in fit]))
    def predict(self,rate,n,cpu):return float(self.model.predict([max(0,rate)*cpu/max(1,n)])[0])

class Controller:
    def __init__(self,profile,mode,initial_rates,period=8,limit=6,slo=500):
        self.mode=mode;self.twin=Twin(profile);self.period=period;self.limit=limit;self.slo=slo
        self.rates=list(initial_rates);self.cpu=self.twin.cpu_reference
        errors=[initial_rates[i]-self.forecast(initial_rates[:i],1) for i in range(3,len(initial_rates))]
        self.demand=Bound(errors or [0]*12);self.mapping=Bound(self.twin.cal_scores)
        self.previous=None;self.hold=0;self.pending=[]
    @staticmethod
    def forecast(rates,horizon):
        if not rates:return 0.
        level=float(np.mean(rates[-3:]));trend=float(np.mean(np.diff(rates[-3:]))) if len(rates)>1 else 0
        return max(0,level+max(0,trend)*horizon)
    def decide(self,obs,index):
        begin=time.perf_counter();rate=obs['rps'];ready=max(1,obs['ready']);cpu=obs.get('cpu_ms')
        horizon=1 if self.mode=='no_delay' else 2
        completed=[];history=self.rates+[rate];last=len(history)-1
        # Score only forecasts whose entire horizon has been observed.
        for p in self.pending:
            if last>=p['origin']+p['horizon']:
                realized=max(history[p['origin']+1:p['origin']+p['horizon']+1])
                completed.append(self.demand.update(realized-p['point'],p['margin']))
        self.pending=[p for p in self.pending if last<p['origin']+p['horizon']]
        map_covered=None
        if self.previous is not None:
            # Score the prediction issued before this observation; no target leak.
            mapping_score=obs['effective_p99_ms']-self.twin.predict(rate,ready,self.cpu)
            map_covered=self.mapping.update(mapping_score,self.previous['margin'])
        if cpu is not None:self.cpu=.5*float(cpu)+.5*self.cpu
        self.rates.append(rate)
        point=max(rate,self.forecast(self.rates,horizon))
        use_d=self.mode in ['full','workload_only','no_delay'];use_m=self.mode in ['full','twin_only','no_delay']
        dm=self.demand.margin() if use_d else 0;mm=self.mapping.margin() if use_m else 0
        upper=point+dm
        targets=[]
        for n in range(1,self.limit+1):
            x=upper*self.cpu/n
            pred=self.twin.predict(upper,n,self.cpu)
            if pred+mm<=self.slo and x<=self.twin.xmax:targets.append(n)
        wanted=min(targets) if targets else self.limit
        current=obs['desired']
        if wanted>=current:self.hold=0;target=wanted
        else:
            self.hold+=1;target=wanted if self.hold>=3 and ready>=current else current
        forecast_record={'origin':last,'horizon':horizon,'point':point,'margin':dm}
        self.pending.append(forecast_record)
        # One-step Twin prediction uses only current observations and ready count.
        self.previous={'prediction':self.twin.predict(rate,ready,self.cpu),'margin':mm}
        return {'target':int(target),'point_rps':point,'upper_rps':upper,'demand_margin':dm,'twin_margin_ms':mm,'cpu_estimate_ms':self.cpu,'feasible':bool(targets),'demand_coverage_updates':completed,'twin_covered':map_covered,'predicted_next_p99_ms':self.previous['prediction'],'elapsed_ms':(time.perf_counter()-begin)*1000}
