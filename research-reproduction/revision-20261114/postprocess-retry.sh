#!/bin/bash
set -e
cd /mnt/c/Users/sofia/.codex/.chatgpt-projects/g-p-67a332acf1fc8191bddbeac79c7b1526/research-reproduction/revision-20261114
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
/opt/guruge-reproduction/twin-venv/bin/python simulate.py > logs/simulation-retry.log 2>&1
/opt/guruge-reproduction/twin-venv/bin/python verify_simulation.py > logs/simulation-verification.log 2>&1
/opt/guruge-reproduction/twin-venv/bin/python analyze.py > logs/analysis.log 2>&1
/opt/guruge-reproduction/twin-venv/bin/python build_paper.py > logs/paper.log 2>&1