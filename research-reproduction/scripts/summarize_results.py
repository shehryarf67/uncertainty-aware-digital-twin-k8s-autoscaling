"""Create evidence-derived comparisons and a concise HTML experiment report."""
from pathlib import Path
import csv
import html
import json
import statistics

ROOT = Path(__file__).resolve().parents[1]
METRICS = ['MSE', 'RMSE', 'MAE', 'R2', 'TPT_ms']


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def table(headers, rows):
    return '<table><thead><tr>' + ''.join('<th>'+html.escape(str(x))+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'


def main():
    audit = read_json(ROOT/'reports'/'source-audit.json')
    runs = []
    states = []
    for path in sorted((ROOT/'results').glob('*/*/execution-status.json')):
        state = read_json(path)
        states.append(state)
        if state['status'] == 'completed':
            m = read_json(path.parent/'metrics.json')
            m['execution_elapsed_seconds'] = state['elapsed_seconds']
            runs.append(m)
    if not runs:
        raise RuntimeError('No completed executed baseline runs; refusing to generate numerical claims')
    comparison = []
    aggregates = []
    for r in runs:
        target = audit['published_prophet_lstm'][r['dataset']]
        for metric in METRICS:
            published, reproduced = target[metric], r[metric]
            comparison.append({'dataset': r['dataset'], 'run_id': r['run_id'], 'metric': metric,
                               'published': published, 'reproduced': reproduced,
                               'signed_difference': reproduced-published,
                               'absolute_difference': abs(reproduced-published),
                               'percentage_difference': 100*(reproduced-published)/published,
                               'epochs_completed': r['epochs_completed']})
    for dataset in ['nasa','fifa']:
        subset = [r for r in runs if r['dataset']==dataset]
        if not subset:
            continue
        for metric in METRICS:
            values = [r[metric] for r in subset]
            mean = statistics.mean(values)
            original = audit['published_prophet_lstm'][dataset][metric]
            aggregates.append({'dataset': dataset, 'metric': metric, 'n_runs': len(values),
                               'published': original, 'mean': mean,
                               'sample_stddev': statistics.stdev(values) if len(values)>1 else None,
                               'minimum': min(values), 'maximum': max(values),
                               'signed_difference_of_mean': mean-original,
                               'absolute_difference_of_mean': abs(mean-original),
                               'percentage_difference_of_mean': 100*(mean-original)/original})
    for name, rows in [('metric-comparisons.csv',comparison),('aggregate-comparisons.csv',aggregates)]:
        with (ROOT/'reports'/name).open('w',newline='',encoding='utf-8') as f:
            w = csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary = {'completed_runs': runs, 'execution_states': states, 'comparison_rows': comparison,
               'aggregate_rows': aggregates, 'published_source': audit['paper'],
               'interpretation': 'Released-code retraining; retained known evaluation artifacts; not corrected evaluation'}
    (ROOT/'reports'/'results-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

    env = read_json(ROOT/'environments'/'smoke-test.json')
    hardware = read_json(ROOT/'environments'/'hardware.json')
    fmt = lambda x: '—' if x is None else f'{x:.9g}'
    blocks = [
        '<h1>Prophet–LSTM forecasting reproduction</h1>',
        '<p>Guruge and Priyadarshana (2025), DOI <a href="https://doi.org/10.3389/fcomp.2025.1509165">10.3389/fcomp.2025.1509165</a>. Experiments executed locally on 9 October 2026.</p>',
        '<p class="notice"><strong>Outcome:</strong> '+str(len(runs))+' complete training-and-evaluation runs were executed from the released notebooks. The tables below contain measured outputs, not estimates. Execution reproduces the authors\' released code behavior; numerical agreement with the paper must be assessed separately. Known evaluation artifacts remain intact. No Digital Twin or uncertainty-aware controller was implemented.</p>',
        '<h2>Original and reproduced hybrid metrics</h2>',
        '<p>Each run retains the authors\' settings: a 70/30 chronological row split, Prophet seasonality, look-back 1, two LSTM layers of 50 units, Adam/MSE, batch 16, 20-epoch maximum, 20% neural validation and patience 5. NumPy/TensorFlow seeds are 42; other initialization sources are not fully fixed. Positive signed differences mean reproduced values are higher. Differences are computed against the printed paper values: especially for FIFA MSE, coarse publication rounding limits the precision of percentage comparisons.</p>'
    ]
    for dataset in ['nasa','fifa']:
        subset = [r for r in runs if r['dataset']==dataset]
        if not subset:
            continue
        blocks.append('<h3>'+('NASA-HTTP' if dataset=='nasa' else 'WorldCup98, normalized')+'</h3>')
        for r in subset:
            blocks.append('<p><strong>'+r['run_id']+'</strong>: '+str(r['epochs_completed'])+' epochs completed; lowest validation loss at epoch '+str(r['best_validation_epoch'])+'.</p>')
            rows = [c for c in comparison if c['dataset']==dataset and c['run_id']==r['run_id']]
            blocks.append(table(['Metric','Paper','Reproduced','Signed difference','Absolute difference','Difference %'],
                                [[c['metric']]+[fmt(c[k]) for k in ['published','reproduced','signed_difference','absolute_difference','percentage_difference']] for c in rows]))
            blocks.append('<p><a href="../results/'+dataset+'/'+r['run_id']+'/executed.ipynb">Executed notebook</a> · <a href="../results/'+dataset+'/'+r['run_id']+'/predictions.csv">Predictions</a> · <a href="../results/'+dataset+'/'+r['run_id']+'/metrics.json">Full metrics and history</a></p>')
        rows = [c for c in aggregates if c['dataset']==dataset]
        blocks.append(table(['Metric','Repeat count','Mean','Sample standard deviation','Minimum','Maximum'],
                            [[c['metric'],c['n_runs']]+[fmt(c[k]) for k in ['mean','sample_stddev','minimum','maximum']] for c in rows]))
        blocks.append('<p>Two repeats characterize observed variability only; they do not establish confidence intervals or significance.</p>')
        first = subset[0]['run_id']
        blocks.append('<img alt="'+dataset+' author notebook final forecast" src="../results/'+dataset+'/'+first+'/images/'+dataset+'-final-output.jpeg">')
    blocks.extend([
        '<h2>Execution environment and fidelity</h2>',
        '<p>'+html.escape(hardware['operating_system']['Caption'])+' '+html.escape(hardware['operating_system']['Version'])+'; '+html.escape(hardware['processors'][0]['Name'])+'; approximately '+fmt(hardware['operating_system']['TotalVisibleMemorySize']/1024**2)+' GiB visible RAM. TensorFlow used the CPU; the Intel Iris Xe adapter is not a CUDA training GPU. CPU intra-op threads 4, inter-op 2, OMP 4. oneDNN retained its default enabled behavior.</p>',
        '<p>Python '+html.escape(env['python'])+'. '+html.escape(', '.join(k+' '+v for k,v in env['versions'].items()))+'. Actual complete package versions are frozen in <a href="../environments/requirements-working.txt">requirements-working.txt</a>. TensorFlow/Prophet fitting and prediction passed the independent environment smoke check; pip check found no dependency conflicts.</p>',
        '<p>The official checkout is pinned to '+audit['commit']+'. All original numerical notebook cells were executed unchanged. Required preparation created the absent images directory. A read-only instrumentation cell copies fit history immediately after training; final added cells export existing predictions/metrics/history only. The runner creates an explicit virtual-environment Jupyter kernel and sets local CPU thread limits. Original unpinned install cells are retained; before/after package inventories are checked. There is no change from 20 to 50 epochs, no realignment, no training-only transform correction and no added full deterministic seeding.</p>',
        '<h2>Datasets and preprocessing</h2>',
        table(['Property','NASA','WorldCup98'], [[key,audit['datasets']['nasa'][key],audit['datasets']['fifa'][key]] for key in ['n_rows','total_requests','first','last','missing_minutes','zero_rows','duplicate_timestamps','prophet_train_rows','test_rows','lstm_train_pairs','lstm_validation_pairs']]),
        '<p>The provided CSVs are used unchanged, with exact hashes in <a href="source-audit.json">source-audit.json</a>. NASA retains naive -0400 local timestamps; the official WorldCup recreation tool emits UTC, stored as naive datetimes. Missing timestamp rows are not reinserted. The preprocessing notebook aggregates all parsed HTTP requests by observed minute without method/status filtering. No raw trace reconstruction or augmentation is used in these experiments.</p>',
        '<h2>Confirmed methodological findings retained</h2>',
        '<ol><li>Both main notebook fits use 20 epochs maximum, while the paper prints 50. FIFA uses flat growth; NASA uses linear.</li><li>NASA residual scaling and FIFA raw-count scaling use full-series extrema, including test data.</li><li>Residual target r[i+1] is written at output row i. This combines a next-row residual prediction with the current-row Prophet value and scores against current-row observations. The original final row uses the true residual as a fallback.</li><li>Test windows contain observed test residuals. Properly aligned, that could represent rolling one-step testing; the released final metric is not a causally aligned next-minute forecast.</li><li>CSV gaps mean a row step is not always a one-minute step.</li></ol>',
        '<p>Independent checks in <a href="verification.json">verification.json</a> recompute exported scores and establish whether the final-row fallback and original source identity hold. These are implementation findings, not proof that every printed paper result was generated by this exact code.</p>',
        '<h2>Environment problems and unverified explanations</h2>',
        '<p>NASA run-01 completed all original author cells, then failed in our added exporter with KeyError: loss: prediction had reset the model History attribute. Its partial executed notebook, predictions and traceback are preserved. The exporter was repaired to copy fit history immediately after training, without changing any author numerical cell. This failed-export attempt is excluded from completed-run aggregates. pandas emits chained-assignment/deprecation warnings; preserving pandas 2.2.2 retains the released behavior. Optional Plotly import warnings do not block static notebook figures. The initial generic uv interpreter inventory encountered a blocked uv Python launcher; the bundled Python 3.12.14 interpreter and virtual environment work. No application-control setting was changed.</p>',
        '<p>Observed numerical variability is consistent with incomplete random-state control and stochastic training, but the historical author TensorFlow version, full dependency lock, hardware and run logs are missing. The exact contribution of these differences cannot be quantified. Hardware and batch timing protocol differ from the unspecified original setup. Timing is the sum of Prophet and LSTM full-test prediction calls, not training time or an online scaling action.</p>',
        '<h2>Published table limitations and research implications</h2>',
        '<p>This reproduction covers only the Prophet–LSTM rows in Tables 4 and 5. Standalone ARIMA/LSTM/Bi-LSTM scripts and sufficient five-step scoring settings are missing. WorldCup comparator MSE/R² pairs imply a different target variance from the hybrid; Bi-LSTM five-step RMSE and MSE are inconsistent under ordinary rounding. The cause remains unverified. Do not describe the entire table as reproduced.</p>',
        '<p>For subsequent research, first create a separately labelled causal baseline: align targets, fit transformations on training data and eliminate truth fallbacks. Only then compare calibrated uncertainty and SLO-aware Digital Twin decisions. Current point-forecast error results do not establish calibrated uncertainty, latency-SLO compliance or autoscaling cost improvement. No corrected experiment is mixed into these outputs.</p>',
        '<p>Exact rerun commands are in <a href="../README.md">README.md</a>. The source audit retains precise cell excerpts and data hashes. Prior detailed inspection is available in <a href="prior-audit.html">the prior audit</a>. All orchestration/export/verification scripts are authored for reproduction; the baseline model methodology is the authors\' code.</p>'
    ])
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prophet–LSTM executed reproduction report</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1080px;margin:40px auto;padding:0 24px;color:#1c2937;background:#fafbfd}h1{font-size:32px}h2{margin-top:35px;color:#14516b}table{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0}td,th{padding:9px;border:1px solid #cbd6df;text-align:left}th{background:#e6eef3}img{max-width:100%;height:auto}.notice{background:#fff0d0;padding:16px}a{color:#065d91}@media print{body{font-size:10pt;background:white}table{font-size:8pt}tr{break-inside:avoid}h2,h3{break-after:avoid}}</style>'''+''.join(blocks)+'</html>'
    (ROOT/'reports'/'reproduction-report.html').write_text(document,encoding='utf-8')
    print(json.dumps(aggregates,indent=2))


if __name__ == '__main__':
    main()
