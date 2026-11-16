"""Causal calibration on saved, already executed corrected forecasts; no refit."""
from pathlib import Path
import json,math,csv
import numpy as np,pandas as pd
from controller import Bound
ROOT=Path(__file__).resolve().parent
def main():
    output=ROOT/'results/forecast-calibration-01';output.mkdir(parents=True,exist_ok=False);summary=[]
    for dataset,run in [('nasa','run-02'),('fifa','run-01')]:
        d=pd.read_csv(ROOT.parent/'corrected-evaluation/results'/dataset/run/'predictions.csv')
        y=d.target_y_raw.to_numpy();pred=d.predicted_y_raw.to_numpy();cut=int(.2*len(d))
        score=y-pred;split=float(np.sort(score[:cut])[min(cut-1,math.ceil((cut+1)*.9)-1)])
        aci=Bound(score[:cut]);records=[]
        for i in range(cut,len(d)):
            margin=aci.margin();upper=pred[i]+margin
            records.append({'target_ds':d.target_ds.iloc[i],'actual':y[i],'point':pred[i],'split_upper':pred[i]+max(0,split),'adaptive_upper':upper,'adaptive_margin':margin,'alpha_before':aci.alpha,'covered':bool(y[i]<=upper)})
            aci.update(score[i],margin)
        r=pd.DataFrame(records);r.to_csv(output/f'{dataset}-bounds.csv',index=False)
        summary.append({'dataset':dataset,'original_test_targets':len(d),'prefix_calibration_targets':cut,'scored_targets':len(r),'nominal_coverage':.9,'point_coverage':float((r.actual<=r.point).mean()),'split_coverage':float((r.actual<=r.split_upper).mean()),'adaptive_coverage':float(r.covered.mean()),'split_margin_raw_count':max(0,split),'mean_adaptive_margin_raw_count':float(r.adaptive_margin.mean()),'first_scored_target':str(r.target_ds.iloc[0]),'last_scored_target':str(r.target_ds.iloc[-1])})
    (output/'summary.json').write_text(json.dumps({'status':'completed','scope':'First 20 percent of original corrected test targets are calibration prefix; remaining 80 percent is a separate rolling evaluation; predictor weights unchanged; these are workload bounds, not latency guarantees','datasets':summary},indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
