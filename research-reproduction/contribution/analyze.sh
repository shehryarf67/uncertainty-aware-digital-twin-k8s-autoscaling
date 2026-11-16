#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY=/opt/guruge-reproduction/twin-venv/bin/python
# The final pre-specified live policy must finish before CPU-heavy simulation.
while [ ! -f results/live-01/303-point/summary.json ]; do sleep 5; done
"$PY" simulate.py > logs/simulation.log 2>&1
"$PY" summarize.py > logs/analysis.log 2>&1
"$PY" verify_evidence.py > logs/verification.log 2>&1
"$PY" build_paper.py > logs/paper.log 2>&1
