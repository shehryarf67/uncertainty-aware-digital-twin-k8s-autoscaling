# Prophet–LSTM forecasting reproduction

This project executes the NASA-HTTP and WorldCup98 Prophet–LSTM notebooks released by Guruge and Priyadarshana (2025), DOI [10.3389/fcomp.2025.1509165](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2025.1509165/full).

The baseline is the authors' **released implementation**, including its original preprocessing, 20-epoch training cap, prediction alignment and final-row truth fallback. It is not a corrected forecasting evaluation. No Digital Twin, uncertainty calibration, Kubernetes deployment or paid cloud resource is implemented here.

## Files and provenance

- Official repository: https://github.com/PasanBhanu/time-series-forcasting-with-facebook-prophet-lstm-hybrid-model
- Exact revision: `354f0042ae7d5812dc7a44335a56b4992e853483`.
- `baseline-original/`: untouched official Git checkout, including original notebooks, datasets, checkpoint models and licence/citation files.
- `baseline-experiments/<dataset>/<run-id>/`: isolated run copy; `instrumented.ipynb` adds a read-only history capture after fitting and final export cells. All author source cells remain unchanged.
- `datasets/`: byte-identical copies of the author datasets, with hashes in `reports/source-audit.json`.
- `environments/requirements-candidate.txt`: initial explicitly selected versions; not an author lockfile.
- `environments/requirements-working.txt`: complete package freeze from the installed execution environment.
- `environments/hardware.json` and `smoke-test.json`: hardware, versions, devices and executed compatibility check.
- `results/<dataset>/<run-id>/`: executed notebook, full-precision metrics, training history, complete predictions, Prophet predictions, residual prediction arrays, model files and original notebook charts.
- `logs/<dataset>/<run-id>/`: kernel output, cell events, and failure traceback if any.
- `reports/source-audit.json`: direct source-cell evidence, dataset checks and the published hybrid metrics.
- `reports/reproduction-report.html`: generated experiment report and paper comparisons.

Four completed runs (two per dataset) passed independent prediction-score and source-integrity checks. NASA mean RMSE is 8.021634 versus the paper's 7.990; WorldCup98 mean normalized RMSE is 0.003379498 versus 0.003358. These are close numerical results, not exact recovery of the published values. Complete per-run differences and repeat variability are in the report. All four fits stopped after six epochs and restored their best validation weights from epoch one.

Preprocessing source is preserved under `reports/preprocessing-source/` at commit `0e8bc6697f2bf9c147b8fb7a6a757a5107874ee9`. It is reference material, not invoked to replace the authors' provided CSVs. The earlier audit and its evidence are retained under `reports/prior-audit.html` and `reports/prior-audit-evidence.json`.

## Recreate the environment

The executed platform is local Windows 11 x64, Python 3.12.14, TensorFlow 2.17.0 (`tensorflow-intel` on Windows), Keras 3.4.1 and Prophet 1.1.5. Complete actual versions are in the working requirements. Use Python 3.12; original f-strings reuse quote characters inside expressions and require Python 3.12 syntax support.

From the project root, with a working Python 3.12 interpreter:

```powershell
python -m venv environments/forecast-venv
& environments/forecast-venv/Scripts/python.exe -m pip install -r environments/requirements-working.txt
& environments/forecast-venv/Scripts/python.exe -m pip check
& environments/forecast-venv/Scripts/python.exe scripts/smoke_environment.py
```

These orchestration commands are authored for this reproduction, not copied from author instructions. The original installation used `uv pip install --python environments/forecast-venv/Scripts/python.exe -r environments/requirements-candidate.txt`, followed by `pip check`, package freeze and the compatibility check. No requested primary version is silently upgraded. The full freeze contains dependency versions resolved at installation time. A Windows lock includes `tensorflow-intel`; do not claim that this platform-specific freeze is validated on Linux.

The smoke check fits/predicts a tiny Prophet and LSTM model using synthetic data. Its output checks runtime compatibility only and is never included in paper-result comparisons.

## Verify the baseline

```powershell
git -C baseline-original rev-parse HEAD
git -C baseline-original status --short
& environments/forecast-venv/Scripts/python.exe scripts/audit_sources.py
```

The expected revision is given above and original Git status must be empty. Do not modify `baseline-original/`. The source audit also checks exact dataset hashes and copies datasets to the top-level data folder.

NASA CSV SHA-256:
`c7aaad88ea28924a259feab54386258cfc846833ce2b682b6901e5d51735539b`.

FIFA CSV SHA-256:
`5f4f1a85aae9b657215f53d09eb3d422ee27357ede7fc1df5bb55323546a80be`.

## Execute fresh runs

Choose **new run IDs**; the runner refuses to overwrite completed or failed runs. For example, use `rerun-01` below.

```powershell
& environments/forecast-venv/Scripts/python.exe scripts/run_baseline.py --dataset nasa --run-id rerun-01
& environments/forecast-venv/Scripts/python.exe scripts/run_baseline.py --dataset fifa --run-id rerun-01
```

Run sequentially to avoid concurrent CPU contention in timing comparisons. The runner selects the current virtual environment's kernel explicitly and sets CPU intra-op threads to 4, inter-op to 2 and OMP to 4. These are documented execution resource settings, not author hardware settings. It does not add deterministic seeding or change model training settings. Authors' NumPy/TensorFlow seeds remain 42; Python's random generator and the full Keras initialization state are not explicitly seeded by the notebooks.

The runner first copies the original checkout excluding `.git`, creates the missing `images/` directory, then executes every original cell in order. A read-only cell after the original fit cell copies the history before Keras prediction resets `model.history`; a final export block runs after model saving. Before publishing completion it checks that the ordered sequence of original source cells is identical. The kernel environment puts the virtual environment first in PATH so original `!pip install` cells target the selected environment. They request already installed packages without `--upgrade`; package inventories must be checked after execution.

NASA `run-01` completed all author cells but failed in the first version of the added export block with `KeyError: 'loss'`, because prediction had reset the History attribute. The failed notebook/logs and predictions remain preserved. Successful runs capture the existing history immediately after fit. This was an orchestration error, not an author notebook failure or numerical-method correction; the failed-export attempt is excluded from aggregate completed-run results.

Training and test prediction can take several minutes. `results/.../execution-status.json` records the current cell, latest epoch message and completion/failure status. Logs preserve warnings and installation output. A failure does not erase the partly executed notebook. Successful runs retain the complete output notebook and new model checkpoints.

## Generate and verify comparisons

```powershell
& environments/forecast-venv/Scripts/python.exe -m pip freeze | Set-Content -Encoding utf8 environments/requirements-after-runs.txt
& environments/forecast-venv/Scripts/python.exe scripts/summarize_results.py
& environments/forecast-venv/Scripts/python.exe scripts/verify_results.py
& environments/forecast-venv/Scripts/python.exe scripts/package_results.py
```

`summarize_results.py` uses only completed runs with metrics exported from executed notebook state. It creates per-run and aggregate comparison tables and a report. `verify_results.py` independently recomputes scores from exported predictions, verifies sample counts and source-cell identity, and checks repository/data integrity. Report metrics are never filled from theoretical estimates or copied paper values.

The packaging script requires passing verification and saves `prophet-lstm-reproduction.zip` with source, notebooks, evidence and a SHA-256 artifact manifest. It excludes the installed virtual environment and transient kernel/cache files; recreate the environment from the working requirements after extracting. If Git is not on PATH, pass `--git` with its executable path to the audit and verification scripts.

Differences use `reproduced - published`, its absolute magnitude, and `100 * (reproduced - published) / published`. Timing percentages describe this hardware/run protocol only. Summaries include observed means and sample standard deviations; a small repeat count is not a statistical confidence interval.

## Confirmed evaluation limitations retained initially

1. Table 2 prints 50 epochs, but both released main fits use a maximum of 20. Early stopping can end earlier.
2. NASA scales the full residual series, including test data; FIFA scales the full request-count series before splitting.
3. Supervised pairs predict residual `r[i+1]` from `r[i]`, but the final combination writes predictions at row `i`. The final row is filled with its observed residual, making its prediction exact. These behaviors are retained.
4. Test inputs contain observed test residuals. With proper alignment this could be rolling one-step evaluation, not a fully recursive holdout forecast. The released final scoring is misaligned.
5. Released CSVs omit empty minutes. A row step can span a timestamp gap. NASA is not reindexed to zero-filled calendar minutes in the notebooks.
6. The published FIFA comparator MSE/R² pairs are inconsistent with a common normalized target variance; this does not by itself identify the cause.
7. Standalone ARIMA/LSTM/Bi-LSTM comparator scripts and sufficient five-step settings are absent. This task reproduces the two hybrid rows, not all comparator entries.
8. Prediction time is the sum of complete test-batch Prophet and LSTM prediction timings, excluding training and most preprocessing. It is not online autoscaler latency.

Original-vs-reproduced differences can reflect stochastic initialization, early stopping, package/hardware differences and the paper/code disagreement. Without historical run logs, do not assign a specific cause to every numerical difference.

Any later corrections must be implemented separately after this reproduction, with separate experiment labels. No corrected experiment overwrites or changes these baseline outputs.
