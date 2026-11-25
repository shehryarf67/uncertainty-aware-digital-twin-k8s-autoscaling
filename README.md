# Digital-Twin-Guided Kubernetes Autoscaling: Research Artifact

This repository contains the Prophet–LSTM baseline reproduction and the later measured autoscaling study. The article is `research-reproduction/revision-20261114/paper/main.tex` (self-contained, two-column LaTeX). Numerical results come from saved real Kubernetes requests or explicitly identified simulations.

The measured system is a single-node K3s cluster on Ubuntu WSL2 with a CPU-bound test service; the real workload is generated traffic. The study does not claim a production-cloud deployment. Five primary repetitions per workload and three exploratory follow-up repetitions do not certify future SLO compliance. In the reserve-matched follow-up, native HPA matched the guarded controller's observed compliance using fewer desired pod-minutes. Do not interpret the main HPA comparison alone as evidence of a predictive-logic advantage.

## Evidence

- `research-reproduction/revision-20261114/results/live/`: 75 valid primary comparisons plus a retained timing-invalid attempt, with per-request data and replica/decision observations.
- `research-reproduction/revision-20261114/reserve-followup/`: 18 reserve-matched live comparisons, protocol and analysis.
- `research-reproduction/revision-20261114/results/twin-validation/`: 18 independent response blocks.
- `research-reproduction/revision-20261114/results/simulation/`: 1,000 queueing-plant rollouts, not live Kubernetes runs.
- `research-reproduction/baseline-original/`, `baseline-experiments/`, `corrected-evaluation/`, `results/`, and `contribution/`: baseline and earlier work. The original author project and dataset provenance are documented in `research-reproduction/README-forecasting-baseline.md`.

The original Prophet–LSTM project is https://github.com/PasanBhanu/time-series-forcasting-with-facebook-prophet-lstm-hybrid-model, revision `354f0042ae7d5812dc7a44335a56b4992e853483`; the baseline reproduces released code behavior, while the corrected evaluation is separately labelled. Source datasets and derived traces have their original provenance and access conditions; see the baseline README before redistribution or reuse.

## Replay the audits

Use Python 3.12 and the versions in `research-reproduction/contribution/requirements-linux-working.txt`, plus the environment inventory in `research-reproduction/revision-20261114/environment.json`. Work from `research-reproduction/revision-20261114`:

```sh
python analyze_followup.py
python verify_simulation.py
python analyze.py
```

These commands recompute the reported statistics from preserved outputs; they do not rerun the live experiments. The simulation serializer was repaired after its first attempt, and the verification records this serialization-only change. The original failed attempt remains preserved. Run `simulate.py` only in a fresh copy or after moving its existing output aside: it intentionally refuses to overwrite `results/simulation/`.

To generate fresh Kubernetes observations, follow `revision-20261114/README.txt`, provision an isolated cluster, and adapt the documented local proxy and infrastructure paths. Those steps were measured on the stated WSL/K3s environment; portability to other clusters is not established. Use a fresh results directory to preserve existing runs. Reproduction may differ with hardware and scheduling.

The LaTeX file can be compiled using a TeX distribution with `pgfplots`, `tikz`, `booktabs`, `xurl`, and standard LaTeX packages. Earlier notebooks and models retain the upstream source provenance and any associated license restrictions; no new blanket license is asserted for upstream materials.

The historical draft generator build_paper.py is retained for provenance and writes an earlier article draft; do not run it over the current main.tex. Run it in a disposable copy if needed. The upstream baseline is a source snapshot; embedded Git metadata is intentionally omitted.


The earlier KEDA/HPA integration code, manifests, and measured request traces are in research-reproduction/kubernetes-autoscaling/. Build outputs and environment secrets are excluded; see source-provenance.json for the original scaler and application repositories.


Latest manuscript: [PDF](research-reproduction/revision-20261114/paper/research-article.pdf) and [single TeX source](research-reproduction/revision-20261114/paper/main.tex), synchronized with Overleaf on 25 November 2026. The Guo citation uses the final 2020 volume, issue and pages.

The 25 November prose revision is now the current manuscript (10 pages). See [revision notes](research-reproduction/revision-20261114/paper/REVISION-20261125.md) and [evidence audit](research-reproduction/revision-20261114/paper/revision-audit-20261125.json). Numerical table cells, equations, plot coordinates and bibliography were preserved; no experimental code or measurements changed. No AI detection score is claimed.
