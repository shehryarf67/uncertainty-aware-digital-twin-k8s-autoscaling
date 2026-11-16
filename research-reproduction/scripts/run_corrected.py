"""Separate causal one-minute evaluation. Authored validation, not original code."""
from pathlib import Path
import argparse, hashlib, json, os, time, traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dataset',choices=['nasa','fifa'],required=True)
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--seed',type=int,default=42)
    args=ap.parse_args()
    if not args.run_id.replace('-','').isalnum(): ap.error('Invalid run ID')
    os.environ.update(TF_NUM_INTRAOP_THREADS='4',TF_NUM_INTEROP_THREADS='2',OMP_NUM_THREADS='4')
    import numpy as np
    import pandas as pd
    import tensorflow as tf
    from prophet import Prophet
    from prophet.serialize import model_to_json
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=ROOT/'corrected-evaluation'/'results'/args.dataset/args.run_id
    if out.exists(): raise FileExistsError(out)
    out.mkdir(parents=True)
    state={'status':'running','dataset':args.dataset,'run_id':args.run_id,'started_utc':datetime.now(timezone.utc).isoformat()}
    started=time.perf_counter()
    def status(stage):
        state.update(stage=stage,elapsed_seconds=time.perf_counter()-started)
        (out/'execution-status.json').write_text(json.dumps(state,indent=2))
        print(stage,flush=True)
    try:
        tf.keras.utils.set_random_seed(args.seed)
        status('load unchanged CSV and establish chronological partitions')
        source=ROOT/'baseline-original'/'datasets'/f'{args.dataset}.csv'
        df=pd.read_csv(source).rename(columns={'minute':'ds','count':'y'})
        df['ds']=pd.to_datetime(df['ds'])
        raw=df['y'].to_numpy(dtype=float)
        n=len(df); split=int(np.floor(.7*n)); # same author outer row boundary
        assert split=={'nasa':56977,'fifa':87710}[args.dataset]
        consecutive=(df.ds.diff()==pd.Timedelta(minutes=1)).to_numpy()
        train_targets=np.flatnonzero(consecutive & (np.arange(n)<split))
        vstart=int(np.floor(.8*len(train_targets)))
        fit_targets=train_targets[:vstart]; val_targets=train_targets[vstart:]
        test_targets=np.flatnonzero(consecutive & (np.arange(n)>=split))
        # Neural validation is conditional on Prophet fitted on the outer training set.
        # Scaling sees only the earlier neural fitting prefix, including source rows.
        scale_rows=np.arange(int(fit_targets[-1])+1)
        raw_scaler=None
        if args.dataset=='fifa':
            raw_scaler=MinMaxScaler().fit(raw[scale_rows,None])
            values=raw_scaler.transform(raw[:,None])[:,0]
        else: values=raw.copy()
        train=pd.DataFrame({'ds':df.ds.iloc[:split],'y':values[:split]})
        model=Prophet(growth='linear' if args.dataset=='nasa' else 'flat',
                      changepoint_prior_scale=5.1,yearly_seasonality=False,
                      weekly_seasonality=20,daily_seasonality=50,seasonality_prior_scale=30)
        status('fit Prophet on outer training rows only')
        model.fit(train)
        prophet_started=time.perf_counter()
        yhat=model.predict(df[['ds']])['yhat'].to_numpy()
        prophet_ms=(time.perf_counter()-prophet_started)*1000
        residual=values-yhat
        residual_scaler=None
        if args.dataset=='nasa':
            residual_scaler=MinMaxScaler().fit(residual[scale_rows,None])
            feature=residual_scaler.transform(residual[:,None])[:,0]
        else: feature=residual.copy()
        def pairs(targets):
            return feature[targets-1].reshape(-1,1,1),feature[targets].reshape(-1,1)
        xf,yf=pairs(fit_targets); xv,yv=pairs(val_targets); xt,yt=pairs(test_targets)
        neural=tf.keras.Sequential([tf.keras.layers.Input(shape=(1,1)),
                  tf.keras.layers.LSTM(50,return_sequences=True),tf.keras.layers.LSTM(50),tf.keras.layers.Dense(1)])
        neural.compile(optimizer='adam',loss='mean_squared_error')
        stop=tf.keras.callbacks.EarlyStopping(monitor='val_loss',patience=5,restore_best_weights=True)
        status('fit residual LSTM with chronological validation and author 20 epoch cap')
        history=neural.fit(xf,yf,epochs=20,batch_size=16,validation_data=(xv,yv),callbacks=[stop],verbose=2)
        history={k:[float(v) for v in vs] for k,vs in history.history.items()}
        status('evaluate rolling causal forecasts at aligned target timestamps')
        pred_started=time.perf_counter(); rp=neural.predict(xt,verbose=0); lstm_ms=(time.perf_counter()-pred_started)*1000
        if residual_scaler is not None: rp=residual_scaler.inverse_transform(rp)
        predicted=yhat[test_targets]+rp[:,0]
        raw_pred=raw_scaler.inverse_transform(predicted[:,None])[:,0] if raw_scaler is not None else predicted.copy()
        # No truth fallback or clipping. Test observations are read only after their own
        # forecast origin, for subsequent one-step predictions; never the current target.
        result=pd.DataFrame({'origin_ds':df.ds.iloc[test_targets-1].to_numpy(),
                    'target_ds':df.ds.iloc[test_targets].to_numpy(),'source_row':test_targets-1,'target_row':test_targets,
                    'origin_y_raw':raw[test_targets-1],'target_y_raw':raw[test_targets],
                    'origin_residual':residual[test_targets-1], 'origin_scaled_residual':feature[test_targets-1],
                    'prophet_target':yhat[test_targets], 'predicted_residual':rp[:,0],
                    'target_y':values[test_targets], 'predicted_y':predicted,'predicted_y_raw':raw_pred})
        result.to_csv(out/'predictions.csv',index=False,float_format='%.17g')
        pd.DataFrame(history).assign(epoch=lambda x:np.arange(1,len(x)+1)).to_csv(out/'training-history.csv',index=False)
        pd.DataFrame({'ds':df.ds,'y_raw':raw,'y':values,'prophet':yhat,'residual':residual,'feature':feature}).to_csv(out/'feature-audit.csv',index=False,float_format='%.17g')
        score=lambda actual,pred:{'MSE':float(mean_squared_error(actual,pred)),'RMSE':float(np.sqrt(mean_squared_error(actual,pred))),
                                  'MAE':float(mean_absolute_error(actual,pred)),'R2':float(r2_score(actual,pred))}
        metrics={'dataset':args.dataset,'run_id':args.run_id,'method':'causal_rolling_one_minute_train_only_scaling',
                 'seed':args.seed, **score(values[test_targets],predicted),'raw_count_metrics':score(raw[test_targets],raw_pred),
                 'prophet_only_metrics':score(values[test_targets],yhat[test_targets]),
                 'last_observation_metrics':score(values[test_targets],values[test_targets-1]),
                 'n_rows':n,'outer_train_rows':split,'outer_test_rows':n-split,'test_scored':len(test_targets),
                 'test_gap_targets_excluded':n-split-len(test_targets),'fit_pairs':len(xf),'validation_pairs':len(xv),
                 'scale_last_row':int(scale_rows[-1]),'neural_validation_first_target':int(val_targets[0]),
                 'history':history,'epochs_completed':len(history['loss']),'best_validation_epoch':int(np.argmin(history['val_loss'])+1),
                 'raw_scaler':None if raw_scaler is None else {'min':raw_scaler.data_min_.tolist(),'max':raw_scaler.data_max_.tolist()},
                 'residual_scaler':None if residual_scaler is None else {'min':residual_scaler.data_min_.tolist(),'max':residual_scaler.data_max_.tolist()},
                 'prophet_all_rows_batch_prediction_ms':prophet_ms,'lstm_test_batch_prediction_ms':lstm_ms,
                 'timing_not_comparable_to_paper':True,'data_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                 'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 'validation_scope':'conditional neural validation within outer Prophet training; not independent full-pipeline validation',
                 'normalization_comparison':'FIFA corrected scaler fitted on early training prefix; raw-count and common-author-scale scores required for direct comparison'}
        (out/'metrics.json').write_text(json.dumps(metrics,indent=2))
        (out/'prophet.json').write_text(model_to_json(model))
        neural.save(out/'lstm.keras')
        fig,ax=plt.subplots(figsize=(12,3.8)); ax.plot(result.target_ds,result.target_y_raw,lw=.6,label='Actual');ax.plot(result.target_ds,result.predicted_y_raw,lw=.6,alpha=.8,label='Causal corrected forecast')
        ax.set(xlabel='Target timestamp',ylabel='Requests per observed minute',title=f'{args.dataset.upper()} chronological test set');ax.legend();fig.autofmt_xdate();fig.tight_layout();fig.savefig(out/'forecast.png',dpi=160);plt.close(fig)
        state['status']='completed';status('completed')
        print(json.dumps(metrics,indent=2),flush=True)
    except BaseException:
        state['status']='failed';status('failed');(out/'failure.txt').write_text(traceback.format_exc());raise

if __name__=='__main__':main()
