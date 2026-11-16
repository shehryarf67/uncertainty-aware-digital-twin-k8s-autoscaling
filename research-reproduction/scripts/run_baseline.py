"""Local orchestration authored for reproduction; not an author experiment script.

Runs every original notebook cell unchanged, with read-only artifact instrumentation.
No corrections to the authors' numeric methodology are made.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "nasa": "Hybrid Model - NASA - Prophet LSTM.ipynb",
    "fifa": "Hybrid Model - FIFA - Prophet LSTM.ipynb",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_cell(dataset, result_dir, run_id):
    # This code runs only after all author cells; it cannot alter trained results.
    return f'''
# Reproduction instrumentation: export existing notebook state without retraining.
import json as _json
from pathlib import Path as _Path
import platform as _platform
import importlib.metadata as _metadata
_out = _Path({str(result_dir)!r})
_out.mkdir(parents=True, exist_ok=True)
_df = final_df_{dataset}.copy()
_df['partition'] = np.where(np.arange(len(_df)) < len(train_df_{dataset}), 'train', 'test')
_df['row_index'] = np.arange(len(_df))
_df.to_csv(_out / 'predictions.csv', index=False, float_format='%.17g')
_test = final_df_{dataset}_analysis
_history = _reproduction_training_history
_metrics = {{
    'dataset': {dataset!r}, 'run_id': {run_id!r},
    'method': 'authors_released_alignment_and_preprocessing',
    'MSE': float(mean_squared_error(_test['y'], _test['y_predicted'])),
    'RMSE': float(np.sqrt(mean_squared_error(_test['y'], _test['y_predicted']))),
    'MAE': float(mean_absolute_error(_test['y'], _test['y_predicted'])),
    'R2': float(r2_score(_test['y'], _test['y_predicted'])),
    'TPT_ms': float(model_one_time + model_two_time),
    'prophet_prediction_ms': float(model_one_time),
    'lstm_prediction_ms': float(model_two_time),
    'epochs_completed': len(_history['loss']),
    'best_validation_epoch': int(np.argmin(_history['val_loss']) + 1),
    'history': {{k: [float(v) for v in values] for k, values in _history.items()}},
    'n_rows': len(_df), 'n_train_prophet': len(train_df_{dataset}),
    'n_test_scored': len(_test), 'n_train_lstm': len(X_train_{dataset}),
    'n_test_lstm': len(X_test_{dataset}), 'look_back': look_back,
    'growth': model_one.growth,
    'scaler': {{'min': scaler.data_min_.tolist(), 'max': scaler.data_max_.tolist()}},
    'versions': {{p: _metadata.version(p) for p in ['tensorflow','keras','prophet','numpy','pandas','scikit-learn','keras-tuner','cmdstanpy']}},
    'python': _platform.python_version(),
    'tensorflow_devices': [str(x) for x in tf.config.list_physical_devices()],
    'author_numpy_seed': 42, 'author_tensorflow_seed': 42,
    'python_random_seed': 'not explicitly set by author notebook',
    'final_row_truth_fallback': bool(np.isclose(_df['y'].iloc[-1], _df['y_predicted'].iloc[-1])),
}}
(_out / 'metrics.json').write_text(_json.dumps(_metrics, indent=2), encoding='utf-8')
pd.DataFrame(_metrics['history']).assign(epoch=lambda x: np.arange(1, len(x)+1)).to_csv(_out / 'training-history.csv', index=False)
forecast_test_df_{dataset}.to_csv(_out / 'prophet-test-predictions.csv', index=False, float_format='%.17g')
np.savez_compressed(_out / 'residual-predictions.npz', train={dataset}_train_predict, test={dataset}_test_predict, targets=y_test_{dataset})
print('REPRODUCTION_EXPORT', _json.dumps({{k: _metrics[k] for k in ['MSE','RMSE','MAE','R2','TPT_ms','epochs_completed']}}))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=FILES, required=True)
    parser.add_argument("--run-id", default="run-01")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if not args.run_id.replace('-', '').isalnum():
        parser.error("run-id must contain letters, digits or hyphens")
    # Fixed CPU resource setting, documented and held constant across repeats.
    os.environ["TF_NUM_INTRAOP_THREADS"] = str(args.threads)
    os.environ["TF_NUM_INTEROP_THREADS"] = "2"
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    kernel_root = ROOT / "environments" / "jupyter"
    kernel_dir = kernel_root / "kernels" / "guruge-baseline"
    kernel_dir.mkdir(parents=True, exist_ok=True)
    (kernel_dir / "kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Guruge baseline", "language": "python"
    }), encoding="utf-8")
    os.environ["JUPYTER_PATH"] = str(kernel_root) + os.pathsep + os.environ.get("JUPYTER_PATH", "")

    import nbformat
    from nbclient import NotebookClient

    work = ROOT / "baseline-experiments" / args.dataset / args.run_id
    result_dir = ROOT / "results" / args.dataset / args.run_id
    log_dir = ROOT / "logs" / args.dataset / args.run_id
    for path in [work, result_dir, log_dir]:
        if path.exists() and any(path.iterdir()):
            raise FileExistsError(f"Refusing to overwrite existing run: {path}")
        path.mkdir(parents=True, exist_ok=True)
    original = ROOT / "baseline-original"
    shutil.copytree(original, work, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
    (work / "images").mkdir(exist_ok=True)
    nb = nbformat.read(original / FILES[args.dataset], as_version=4)
    original_sources = [cell.source for cell in nb.cells]
    capture = nbformat.v4.new_code_cell(
        '# Reproduction instrumentation: preserve the fit history before predict resets it.\n'
        '_reproduction_training_history = {k: list(v) for k, v in model_two.history.history.items()}')
    capture.metadata['reproduction_added'] = True
    nb.cells.insert(47, capture)
    footer = nbformat.v4.new_markdown_cell(
        "## Reproduction artifact export\nAdded instrumentation below exports existing state. "
        "All author cells are unchanged; no evaluation corrections are applied.")
    footer.metadata['reproduction_added'] = True
    nb.cells.append(footer)
    exporter = nbformat.v4.new_code_cell(export_cell(args.dataset, result_dir, args.run_id))
    exporter.metadata['reproduction_added'] = True
    nb.cells.append(exporter)
    nbformat.write(nb, work / "instrumented.ipynb")
    started = time.time()
    state = {
        "status": "running", "dataset": args.dataset, "run_id": args.run_id,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "original_notebook_sha256": sha(original / FILES[args.dataset]),
        "source_cells_unchanged": True,
        "changes": ["created images directory", "read-only fit-history capture after author cell 46", "appended export cells", f"CPU intra-op threads={args.threads}, inter-op=2"],
    }
    status_file = result_dir / "execution-status.json"
    stream_path = log_dir / "kernel-stream.log"
    event_path = log_dir / "events.jsonl"
    executed_path = result_dir / "executed.ipynb"

    def save_state():
        state["elapsed_seconds"] = time.time() - started
        status_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def cell_start(cell, cell_index, **kwargs):
        state["current_cell"] = cell_index
        state["current_source"] = cell.source[:200]
        save_state()
        with event_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({"event": "cell_start", "cell": cell_index, "elapsed": time.time()-started}) + '\n')
        if cell.cell_type == 'code':
            print(f"{args.dataset}/{args.run_id}: cell {cell_index}, {cell.source.splitlines()[0][:100]}", flush=True)

    def cell_done(cell, cell_index, **kwargs):
        nbformat.write(nb, executed_path)
        with event_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({"event": "cell_complete", "cell": cell_index, "elapsed": time.time()-started}) + '\n')

    class LoggedClient(NotebookClient):
        def process_message(self, msg, cell, cell_index):
            content = msg.get('content', {})
            if msg.get('msg_type') == 'stream':
                text = content.get('text', '')
                with stream_path.open('a', encoding='utf-8') as f:
                    f.write(text)
                if 'Epoch ' in text:
                    state['latest_epoch_message'] = text[-500:]
                    save_state()
            elif msg.get('msg_type') == 'error':
                with stream_path.open('a', encoding='utf-8') as f:
                    f.write('\n' + '\n'.join(content.get('traceback', [])))
            return super().process_message(msg, cell, cell_index)

    save_state()
    client = LoggedClient(nb, timeout=None, kernel_name="guruge-baseline",
                          resources={"metadata": {"path": str(work)}},
                          on_cell_start=cell_start, on_cell_executed=cell_done,
                          record_timing=True)
    try:
        client.execute()
        assert [c.source for c in nb.cells if not c.metadata.get('reproduction_added', False)] == original_sources
        state['status'] = 'completed'
        for folder in ['images', 'models']:
            shutil.copytree(work / folder, result_dir / folder, dirs_exist_ok=True)
        # The notebook's batch inference times are already captured before export.
        print(f"COMPLETED {args.dataset}/{args.run_id}: {(result_dir/'metrics.json').read_text(encoding='utf-8')}", flush=True)
    except BaseException as exc:
        state['status'] = 'failed'
        state['error'] = f'{type(exc).__name__}: {exc}'
        (log_dir / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        nbformat.write(nb, executed_path)
        save_state()


if __name__ == '__main__':
    main()
