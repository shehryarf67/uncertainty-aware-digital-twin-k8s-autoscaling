"""Independent numerical and causal-input checks; no training."""
from pathlib import Path
import json, os, hashlib
os.environ.update(TF_NUM_INTRAOP_THREADS='4',TF_NUM_INTEROP_THREADS='2',OMP_NUM_THREADS='4')
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error,mean_absolute_error,r2_score
from sklearn.preprocessing import MinMaxScaler
from keras.models import load_model
ROOT=Path(__file__).resolve().parents[1]
rows=[]; checks=[]
def scores(y,p):return {'MSE':float(mean_squared_error(y,p)),'RMSE':float(np.sqrt(mean_squared_error(y,p))),'MAE':float(mean_absolute_error(y,p)),'R2':float(r2_score(y,p))}
for path in sorted((ROOT/'corrected-evaluation/results').glob('*/*/metrics.json')):
    out=path.parent;m=json.loads(path.read_text());p=pd.read_csv(out/'predictions.csv');a=pd.read_csv(out/'feature-audit.csv')
    assert json.loads((out/'execution-status.json').read_text())['status']=='completed'
    for k,v in scores(p.target_y,p.predicted_y).items():assert np.isclose(v,m[k],rtol=1e-10,atol=1e-12)
    assert ((pd.to_datetime(p.target_ds)-pd.to_datetime(p.origin_ds))==pd.Timedelta(minutes=1)).all()
    assert (p.source_row+1==p.target_row).all() and p.target_row.min()>=m['outer_train_rows']
    assert m['scale_last_row']<m['neural_validation_first_target']<m['outer_train_rows']
    raw=pd.read_csv(ROOT/'baseline-original/datasets'/f"{m['dataset']}.csv")['count'].to_numpy(float)
    assert hashlib.sha256((ROOT/'baseline-original/datasets'/f"{m['dataset']}.csv").read_bytes()).hexdigest()==m['data_sha256']
    scaler=MinMaxScaler().fit((raw if m['dataset']=='fifa' else a.residual.to_numpy())[:m['scale_last_row']+1,None])
    stored=m['raw_scaler'] if m['dataset']=='fifa' else m['residual_scaler']
    assert np.allclose(scaler.data_min_,stored['min']) and np.allclose(scaler.data_max_,stored['max'])
    neural=load_model(out/'lstm.keras'); rp=neural.predict(p.origin_scaled_residual.to_numpy().reshape(-1,1,1),verbose=0)
    if m['dataset']=='nasa':rp=scaler.inverse_transform(rp)
    assert np.allclose(rp[:,0],p.predicted_residual,rtol=2e-6,atol=2e-5)
    assert np.allclose(p.predicted_y,p.prophet_target+p.predicted_residual)
    # Counterfactual test: alter all observations at and after a selected target,
    # while using a frozen training-fitted scaler/Prophet and only origin residual.
    selected=int(p.target_row.iloc[len(p)//2]);perturbed=raw.copy();perturbed[selected:]*=1000
    def origin_feature(observations):
        if m['dataset']=='fifa':return scaler.transform([[observations[selected-1]]])[0,0]-a.prophet.iloc[selected-1]
        return scaler.transform([[observations[selected-1]-a.prophet.iloc[selected-1]]])[0,0]
    assert origin_feature(raw)==origin_feature(perturbed)
    span=raw.max()-raw.min();minimum=raw.min()
    targets=p.target_row.to_numpy(int)
    # Same target rows, and both raw-count and the author scale, for fair comparison.
    for name,pred in [('corrected',p.predicted_y_raw.to_numpy()),('persistence',p.origin_y_raw.to_numpy()),('prophet',a.prophet.iloc[targets].to_numpy()*(m['raw_scaler']['max'][0]-m['raw_scaler']['min'][0])+m['raw_scaler']['min'][0] if m['dataset']=='fifa' else a.prophet.iloc[targets].to_numpy())]:
        for units,y,pr in [('raw_count',p.target_y_raw,pred),('author_units',(p.target_y_raw-minimum)/span,(pred-minimum)/span)] if m['dataset']=='fifa' else [('raw_count',p.target_y_raw,pred)]:
            rows.append({'dataset':m['dataset'],'run_id':m['run_id'],'method':name,'units':units,'n':len(p),**scores(y,pr)})
    for bpath in sorted((ROOT/'results'/m['dataset']).glob('*/metrics.json')):
        b=pd.read_csv(bpath.parent/'predictions.csv').iloc[targets]
        pred=b.y_predicted.to_numpy()*span+minimum if m['dataset']=='fifa' else b.y_predicted.to_numpy()
        for units,y,pr in [('raw_count',p.target_y_raw,pred),('author_units',(p.target_y_raw-minimum)/span,(pred-minimum)/span)] if m['dataset']=='fifa' else [('raw_count',p.target_y_raw,pred)]:
            rows.append({'dataset':m['dataset'],'run_id':bpath.parent.name,'method':'original_common_targets','units':units,'n':len(p),**scores(y,pr)})
    checks.append({'dataset':m['dataset'],'run_id':m['run_id'],'score_recomputation':True,'saved_model_inference_matches':True,'one_minute_origins':True,'training_prefix_scaler_extrema':True,'future_observation_perturbation_does_not_change_origin_input':True,'scored_targets':len(p),'excluded_gap_targets':m['test_gap_targets_excluded']})
pd.DataFrame(rows).to_csv(ROOT/'corrected-evaluation/comparisons.csv',index=False)
(ROOT/'corrected-evaluation/verification.json').write_text(json.dumps({'status':'passed','checks':checks,'scope':'fixed trained model rolling inputs; no claim of recursive multi-step forecasting'},indent=2))
print(json.dumps(checks,indent=2))
