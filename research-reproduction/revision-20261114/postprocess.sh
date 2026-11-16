#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
PY=/opt/guruge-reproduction/twin-venv/bin/python
# Preserve live measurement conditions: run the heavy plant only after all trials.
while [ ! -f results/live-status.json ]; do sleep 15; done
"$PY" reserve_followup.py > logs/reserve-followup.log 2>&1
"$PY" analyze_followup.py > logs/reserve-analysis.log 2>&1
"$PY" validate_twin.py > logs/twin-validation.log 2>&1
"$PY" simulate.py > logs/simulation.log 2>&1
"$PY" verify_simulation.py > logs/simulation-verification.log 2>&1
"$PY" analyze.py > logs/analysis.log 2>&1
"$PY" build_paper.py > logs/paper.log 2>&1
