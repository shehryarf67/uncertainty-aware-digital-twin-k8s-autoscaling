"""Verify pinned baseline, datasets, notebook code and published target values."""
from pathlib import Path
import csv
import hashlib
import json
import math
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '354f0042ae7d5812dc7a44335a56b4992e853483'
PUBLISHED = {
    'nasa': {'MSE': 63.836, 'RMSE': 7.990, 'MAE': 6.164, 'R2': 0.900, 'TPT_ms': 3492.0},
    'fifa': {'MSE': 0.000011, 'RMSE': 0.003358, 'MAE': 0.000675, 'R2': 0.998318, 'TPT_ms': 3971.0},
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--git', default='git')
    args = p.parse_args()
    original = ROOT / 'baseline-original'
    commit = subprocess.check_output([args.git, '-C', str(original), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == COMMIT
    status = subprocess.check_output([args.git, '-C', str(original), 'status', '--porcelain'], text=True)
    assert not status, 'Original repository has changed'
    record = {'commit': commit, 'repository_clean': True, 'datasets': {}, 'notebooks': {},
              'paper': 'https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2025.1509165/full',
              'published_prophet_lstm': PUBLISHED}
    for dataset, expected in [('nasa', 'c7aaad88ea28924a259feab54386258cfc846833ce2b682b6901e5d51735539b'),
                              ('fifa', '5f4f1a85aae9b657215f53d09eb3d422ee27357ede7fc1df5bb55323546a80be')]:
        path = original / 'datasets' / (dataset + '.csv')
        sha = digest(path)
        assert sha == expected
        destination = ROOT / 'datasets' / path.name
        destination.write_bytes(path.read_bytes())
        with path.open() as f:
            rows = list(csv.DictReader(f))
        dates = [datetime.fromisoformat(r['minute']) for r in rows]
        counts = [int(r['count']) for r in rows]
        n = len(rows)
        split = n - math.ceil(.3*n)
        n_pairs = n - 1
        pair_split = n_pairs - math.ceil(.3*n_pairs)
        record['datasets'][dataset] = {
            'file': 'baseline-original/datasets/' + path.name,
            'sha256': sha, 'n_rows': n, 'total_requests': sum(counts),
            'first': str(dates[0]), 'last': str(dates[-1]),
            'zero_rows': counts.count(0), 'duplicate_timestamps': n-len(set(dates)),
            'missing_minutes': int((dates[-1]-dates[0]).total_seconds()/60)+1-len(set(dates)),
            'sorted': dates == sorted(dates), 'minimum_count': min(counts), 'maximum_count': max(counts),
            'prophet_train_rows': split, 'test_rows': n-split,
            'last_train_timestamp': str(dates[split-1]), 'first_test_timestamp': str(dates[split]),
            'lstm_train_pairs': pair_split, 'lstm_test_pairs': n_pairs-pair_split,
            'lstm_fit_pairs': int(pair_split*.8), 'lstm_validation_pairs': pair_split-int(pair_split*.8),
        }
        notebook = original / f'Hybrid Model - {"NASA" if dataset=="nasa" else "FIFA"} - Prophet LSTM.ipynb'
        nb = json.loads(notebook.read_text(encoding='utf-8'))
        code = '\n'.join(''.join(c.get('source', [])) for c in nb['cells'] if c['cell_type']=='code')
        assert 'epochs=20' in code and 'look_back = 1' in code
        assert f"final_df_{dataset}['residual_predict'].iloc[0:len(" in code
        selected = {}
        for i,c in enumerate(nb['cells']):
            source = ''.join(c.get('source', []))
            if any(key in source for key in ['pip install','np.random.seed','fit_transform','look_back =','train_test_split','model_two.fit','residual_predict','mean_squared_error','Prophet(','EarlyStopping','def create_dataset']):
                selected[str(i)] = source
        record['notebooks'][dataset] = {'file': notebook.name, 'sha256': digest(notebook),
                                          'selected_source_cells_zero_based': selected}
    (ROOT/'reports'/'source-audit.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k,v in record.items() if k!='notebooks'}, indent=2))


if __name__ == '__main__':
    main()
