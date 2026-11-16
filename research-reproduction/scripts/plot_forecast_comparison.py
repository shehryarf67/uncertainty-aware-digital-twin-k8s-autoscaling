from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'final-report/figures';out.mkdir(parents=True,exist_ok=True)
for dataset,run in [('nasa','run-02'),('fifa','run-01')]:
    corrected=pd.read_csv(ROOT/'corrected-evaluation/results'/dataset/run/'predictions.csv')
    original=pd.read_csv(ROOT/'results'/dataset/('run-02' if dataset=='nasa' else 'run-01')/'predictions.csv').iloc[corrected.target_row]
    raw=pd.read_csv(ROOT/'baseline-original/datasets'/f'{dataset}.csv')['count']
    author=original.y_predicted.to_numpy()*(raw.max()-raw.min())+raw.min() if dataset=='fifa' else original.y_predicted.to_numpy()
    fig,ax=plt.subplots(figsize=(11,3.3));ds=pd.to_datetime(corrected.target_ds)
    ax.plot(ds,corrected.target_y_raw,lw=.6,label='Actual')
    ax.plot(ds,author,lw=.6,alpha=.55,label='Author scoring alignment')
    ax.plot(ds,corrected.predicted_y_raw,lw=.6,alpha=.8,label='Causal corrected')
    ax.set(xlabel='Target timestamp',ylabel='Requests per minute',title=f'{dataset.upper()} test forecasts on common one-minute target rows')
    ax.legend(fontsize=8);fig.autofmt_xdate();fig.tight_layout();fig.savefig(out/f'{dataset}-comparison.png',dpi=180);plt.close(fig)
