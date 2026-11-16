RESEARCH CONTRIBUTION — 28 October 2026

This directory adds a separate measured service-response Twin and two online
residual corrections to the preserved Prophet–LSTM reproduction. It is a finite
pilot study. Results do not establish universal SLO guarantees or priority of the
general idea. Read the final manuscript's related work and limitations.

WHAT IS PRESERVED
The sibling baseline-original, baseline-experiments, datasets, results,
corrected-evaluation and kubernetes-autoscaling directories retain the prior
research. The original implementation is not overwritten. The original report
and handoff archives remain available. verification.json checks original hashes.
overleaf-before-20261028.zip is the downloaded pre-edit Overleaf source backup.

NEW IMPLEMENTATION
service.py           Instrumented PBKDF2 CPU service, not the authors' sample app.
controller.py        Frozen isotonic response Twin and separate demand/model
                     residual corrections; limits, delay horizon and hysteresis.
deployment.yaml      New twin-research namespace application deployment/service.
live.py              Measured profiling and repeated real Kubernetes experiments.
simulate.py          Separate discrete-event queueing plant, not Kubernetes.
forecast_calibration.py  Calibration-only evaluation of saved causal forecasts.
frozen-protocol.json  Choices fixed before the live controller comparisons.
summarize.py         Request-based metrics and descriptive paired simulation CIs.
verify_causality.py   Prefix invariance, delayed labels, limits and monotonicity.
verify_evidence.py    Independent metric/bound recomputation and baseline hashes.
build_paper.py        Generates the single self-contained final main TeX file.

OUTPUTS
results/profile-01/              18 fit + 12 calibration service-profile blocks.
results/live-01/                 3 seeds x 5 policies; every request and observation.
results/simulation-01/           10 seeds x 5 regimes x 7 policies.
results/forecast-calibration-01/ Chronological NASA/WorldCup saved-forecast bounds.
results/summary.json             Aggregated evidence used by the manuscript.
verification.json               Independent audit outcome.
paper/main_article_v1a_change_this.tex  Sole final paper source; references,
                               diagrams, plots and tables are embedded.

REPLAY ANALYSIS WITHOUT A CLUSTER
Use Python 3.12 and requirements-linux-working.txt in a separate virtual
environment. numpy, pandas and scikit-learn are required. From this directory:

  python verify_causality.py
  python summarize.py
  python verify_evidence.py
  python build_paper.py

These commands analyze the existing evidence; they do not retrain the baseline.
The complete handoff retains the previous archive's exact-duplicate alias map.
verify_evidence.py resolves those aliases read-only and verifies all 253 original
per-path hashes, including the official source snapshot's Git identity files.
Duplicate experiment folders need not be materialized just to run the audit.
The evidence audit also requires the sibling preserved reproduction files.
To rerun forecast_calibration.py, preserve the existing output directory first.
It reads corrected-evaluation/results/nasa/run-02/predictions.csv and the FIFA
run-01 predictions. It never retrains their fitted predictors. To rerun the
simulator, preserve results/simulation-01 first: its exclusive-create output
directory intentionally refuses to overwrite prior trials.

REAL KUBERNETES REPRODUCTION
Verified here on Ubuntu WSL, K3s v1.33.6+k3s1, containerd 2.1.5, one local node.
Metrics-server is needed for the native CPU HPA; the custom controller uses the
instrumented service. Docker Desktop was unavailable and is not needed here.
The previous reproduction installed K3s at /opt/guruge-reproduction/bin/k3s,
with its private kubeconfig at /opt/guruge-reproduction/kubeconfig.yaml and a
guruge-k3s systemd unit. Those paths are local environment requirements, not
portable defaults. No kubeconfig or credentials belong in a handoff archive.

Commands executed for this contribution, from this directory in Ubuntu:

  sudo systemctl start guruge-k3s
  sudo bash setup.sh
  /opt/guruge-reproduction/twin-venv/bin/python live.py profile
  /opt/guruge-reproduction/twin-venv/bin/python live.py experiments

setup.sh assumes the existing cluster, root privileges, Python venv support,
outbound access to PyPI and the official python:3.12-alpine container image,
and a logs directory. It installs only the new environment and namespace. It
starts an authenticated Kubernetes API proxy bound only to 127.0.0.1:8001.
live.py discovers the host's first IPv4 address and uses NodePort 30081. Verify
that address is the reachable node in another environment. Do not expose the
API proxy to a network. The controller changes only twin-research resources.
runtime-inventory.json records node/environment facts and the resolved image:
python@sha256:5789aa194f757888f41fa3d48e14b6feaa1b57c0af0b56fcb1372d6474d3bff0
The deployment used the version tag shown above. Pinning this recorded digest
on a new machine avoids later tag changes; that adaptation was not needed in
the measured run. Machine identifiers and authentication material are excluded.
One controller runs at a time; trial order is a seeded permutation. Profiling
and experiment directories refuse overwrites. A new reproduction must archive
existing outputs before starting, rather than silently replacing evidence.

After all live measurements, execute:

  /opt/guruge-reproduction/twin-venv/bin/python simulate.py
  /opt/guruge-reproduction/twin-venv/bin/python forecast_calibration.py
  /opt/guruge-reproduction/twin-venv/bin/python summarize.py
  /opt/guruge-reproduction/twin-venv/bin/python verify_evidence.py
  /opt/guruge-reproduction/twin-venv/bin/python build_paper.py

The exact environment and deployment are provided, but a new machine's timing,
CPU frequency, resource contention, routing and readiness will differ. Treat
these as verified local commands requiring the stated prerequisites. Installing
a fresh cluster elsewhere and adapting addresses/paths are inferred setup steps,
not commands verified on another machine. The original baseline reproduction
has its own environment and instructions; do not merge the Python environments.

INTERPRETATION
Live traffic uses five-second offered-load windows and a fixed three-second
drain per cycle. All 1,400 requests per trial are scored; warmup is excluded.
The native HPA reconciles on its own timing, unlike the custom eight-second
batch loop. Desired pod-minutes use cycle-start desired replicas, include drain
and pending capacity, and exclude inter-window API time: they are sampled
allocation, not precise billing or CPU energy. HPA records contain a shadow
model calculation for logging; its calibration/runtime fields are not HPA
algorithm overhead or HPA coverage guarantees.

The simulated plant uses independent lognormal service times and central FIFO
dispatch. Live Kubernetes routes per connection and can be imbalanced. The
simulator is a sensitivity experiment, not a validated production-cluster Twin.
Request-level SLO compliance is 99% HTTP-200 responses within 500 ms. Nominal
90% model/forecast coverage concerns different events and implies no 99% SLO
guarantee. Clipped rolling ACI-style updates have no inherited formal theorem.
Calibration-set model error is not an independent test-fidelity estimate.
All prescribed trials, including poor outcomes, must appear in the analysis.

OVERLEAF
Final main source: main_article_v1a_change_this.tex. It has no external TeX,
image or bibliography dependencies and uses ordinary TeX Live packages.
The old TeX drafts belong only in archive_20261015/. The root must contain
exactly one .tex file. The local source backup preserves the previous project.
