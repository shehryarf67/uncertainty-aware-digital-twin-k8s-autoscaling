"""Independent validation of executed outputs, not a new evaluation protocol."""
from pathlib import Path
import hashlib
import json
import math
import subprocess

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def source(cell):
    value = cell['source']
    return ''.join(value) if isinstance(value,list) else value


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--git', default='git')
    args = p.parse_args()
    audit = read(ROOT/'reports'/'source-audit.json')
    records = []
    for status_file in sorted((ROOT/'results').glob('*/*/execution-status.json')):
        status = read(status_file)
        if status['status'] != 'completed':
            continue
        folder = status_file.parent
        m = read(folder/'metrics.json')
        df = pd.read_csv(folder/'predictions.csv', float_precision='round_trip')
        test = df[df['partition']=='test']
        independent = {
            'MSE': float(mean_squared_error(test['y'],test['y_predicted'])),
            'RMSE': float(np.sqrt(mean_squared_error(test['y'],test['y_predicted']))),
            'MAE': float(mean_absolute_error(test['y'],test['y_predicted'])),
            'R2': float(r2_score(test['y'],test['y_predicted'])),
        }
        assert len(test) == m['n_test_scored'] == audit['datasets'][m['dataset']]['test_rows']
        assert all(math.isclose(independent[k],m[k],rel_tol=1e-11,abs_tol=1e-12) for k in independent)
        assert np.isfinite(df[['y','yhat','residual','residual_predict','y_predicted']]).all().all()
        assert np.allclose(df['yhat']+df['residual_predict'],df['y_predicted'],rtol=1e-12,atol=1e-12)
        assert np.isclose(df['y'].iloc[-1],df['y_predicted'].iloc[-1])
        assert m['epochs_completed'] <= 20
        assert len(m['history']['loss']) == m['epochs_completed']
        assert len(m['history']['val_loss']) == m['epochs_completed']
        assert math.isclose(m['TPT_ms'],m['prophet_prediction_ms']+m['lstm_prediction_ms'],abs_tol=1e-9)
        origpath = ROOT/'baseline-original'/audit['notebooks'][m['dataset']]['file']
        original = read(origpath)
        executed = read(folder/'executed.ipynb')
        assert [source(c) for c in original['cells']] == [source(c) for c in executed['cells'] if not c.get('metadata',{}).get('reproduction_added',False)]
        assert all(not any(o.get('output_type')=='error' for o in c.get('outputs',[])) for c in executed['cells'])
        assert all(c['execution_count'] is not None for c in executed['cells'] if c['cell_type']=='code')
        csvpath = ROOT/'baseline-original'/'datasets'/(m['dataset']+'.csv')
        assert hashlib.sha256(csvpath.read_bytes()).hexdigest() == audit['datasets'][m['dataset']]['sha256']
        plots = list((folder/'images').glob('*.jpeg'))
        assert len(plots) == 7 and all(x.stat().st_size>0 for x in plots)
        model_files = sorted(x.name for x in (folder/'models').iterdir())
        assert len(model_files) >= 6, 'Expected author checkpoints plus two newly trained checkpoints'
        records.append({'dataset':m['dataset'],'run_id':m['run_id'],
                        'independently_recomputed_metrics':independent,
                        'score_matches_export':True,'all_original_source_cells_identical':True,
                        'all_code_cells_executed_without_error':True,'test_sample_count':len(test),
                        'final_row_truth_fallback_confirmed':True,'n_saved_charts':len(plots),
                        'model_files':model_files})
    if not records:
        raise RuntimeError('No completed results to validate')
    original = ROOT/'baseline-original'
    status = subprocess.check_output([args.git,'-C',str(original),'status','--porcelain'],text=True)
    assert not status
    before = (ROOT/'environments'/'requirements-working.txt').read_text(encoding='utf-8-sig').splitlines()
    after_path = ROOT/'environments'/'requirements-after-runs.txt'
    if after_path.exists():
        after = after_path.read_text(encoding='utf-8-sig').splitlines()
        assert sorted(before)==sorted(after), 'Dependencies changed during notebook execution'
    else:
        raise RuntimeError('Capture requirements-after-runs.txt before final verification')
    record = {'status':'passed','baseline_git_clean':True,'package_inventory_unchanged':True,
              'completed_runs_checked':len(records),'runs':records}
    (ROOT/'reports'/'verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main()
