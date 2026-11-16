"""Environment compatibility check on tiny synthetic data, not paper results."""
from pathlib import Path
import importlib.metadata
import json
import os
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['TF_NUM_INTRAOP_THREADS'] = '4'
os.environ['TF_NUM_INTEROP_THREADS'] = '2'
os.environ['OMP_NUM_THREADS'] = '4'
started = time.time()

import numpy as np
import pandas as pd
import tensorflow as tf
import keras
import keras_tuner
from prophet import Prophet
from sklearn.metrics import mean_squared_error

versions = {p: importlib.metadata.version(p) for p in [
    'tensorflow', 'tensorflow-intel', 'keras', 'prophet', 'numpy', 'pandas',
    'scikit-learn', 'matplotlib', 'keras-tuner', 'cmdstanpy', 'nbclient', 'nbformat', 'ipykernel']}
print('VERSIONS', versions, flush=True)
df = pd.DataFrame({'ds': pd.date_range('2000-01-01', periods=30, freq='h'),
                   'y': np.sin(np.arange(30)) + 10})
m = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
m.fit(df)
pred = m.predict(df[['ds']])
assert len(pred) == 30 and np.isfinite(pred['yhat']).all()
net = keras.Sequential([keras.layers.Input((1,1)), keras.layers.LSTM(2), keras.layers.Dense(1)])
net.compile(optimizer='adam', loss='mean_squared_error')
net.fit(np.ones((8,1,1)), np.ones(8), batch_size=4, epochs=1, verbose=0)
test_prediction = net.predict(np.ones((8,1,1)), verbose=0)
assert test_prediction.shape == (8,1)
record = {'status': 'passed', 'python': sys.version, 'executable': sys.executable,
          'platform': platform.platform(), 'versions': versions,
          'tensorflow_devices': [str(x) for x in tf.config.list_physical_devices()],
          'tensorflow_build': tf.sysconfig.get_build_info(),
          'tiny_prophet_fit_and_predict': True, 'tiny_lstm_fit_and_predict': True,
          'elapsed_seconds': time.time()-started}
(ROOT/'environments'/'smoke-test.json').write_text(json.dumps(record, indent=2, default=str), encoding='utf-8')
print('SMOKE PASSED', json.dumps(record, indent=2, default=str), flush=True)
