NOVEMBER CONTROLLER REVISION AND TWO-COLUMN ARTICLE

This work preserves the original forecasting reproduction and the October
contribution. All new measurements, code and protocols are in this directory.
The strict objective remains >=99% HTTP-200 responses within 500 ms.

EVIDENCE DESIGN
1. Development: twenty fixed-capacity blocks, 3,675 measured requests. The current
   host's fixed-six capacity missed the objective at peak conditions. A common
   sixteen-replica maximum is therefore used in the revised comparison. This
   observation is not a proof that all six-replica designs are impossible.
2. Primary study: 75 comparisons = five policies x five repetitions x three
   workloads. 120,275 scheduled measured requests. The previous batch shape is
   retained; new abrupt and uninterrupted shapes broaden the evaluation.
3. Reserve-matched follow-up: 18 comparisons = two policies x three fresh paired
   repetitions x three workloads. 28,866 scheduled measured requests. Native HPA
   here has the same minimum eight and maximum sixteen as the guarded policy.
   This separate exploratory cohort was specified after early primary outcomes
   to test minimum-capacity confounding; no controller parameters were changed.
4. Independent response validation: eighteen unseen combinations of replica
   count, rate and work cost; 2,160 requests. Realized CPU cost is an input, so
   this tests conditional response mapping rather than ex-ante CPU forecasting.
5. Simulation sensitivity: 1,000 rollouts = 25 paired seeds x five regimes x
   eight policies, using a separate Poisson/lognormal queueing plant. These are
   simulated results and are always identified separately from Kubernetes data.

The frozen primary source/configuration was fixed before the 75-comparison
study. The follow-up and response-validation protocols record their own freeze
times and source hashes. Every attempt remains available. SLO failure never
triggers a rerun. Timing/count-invalid attempts can be repeated once.

CONTROLLER CHANGES
controller_v2.py contains the implemented repair. A development-profile capacity
envelope drives sizing, with conservative demand correction, a four-observation
rolling maximum of CPU-P90, startup-aware planning, pressure response, a desired
reserve of eight initialized ready, and one-pod-at-a-time guarded scale-down.
The response curve provides support/tail diagnostics. It is not an end-to-end
SLO certificate, and the maximum-score workload rule has no inherited exact
99% conformal guarantee with forty calibration scores. The no-reserve live
ablation removes only the eight-replica floor. All adaptive primary policies
start with eight ready replicas; fixed sixteen starts provisioned at sixteen.

REAL DATA AND PAPER RULES
Actual measurements and statistics computed from them appear in black in the
paper. During the active study, red [pending] entries identify unfinished
analyses; invented numerical results are never inserted. The final article is
generated only after complete audited evidence exists. The final root Overleaf
source is main_article.tex, with embedded references, vector
plots and tables. Older sources are in archive folders. Main text is two-column;
wide data tables/figures can span both columns as normal research layouts do.

FILES
frozen-protocol.json          Primary settings and immutable input/source hashes.
simulation-protocol.json      Paired plant and isolated ablation specification.
validation-protocol.json      Independent response validation specification.
reserve-followup/frozen-protocol.json  Separate matched-reserve protocol.
development-capacity-*/       Actual development requests and block statistics.
results/live/                Primary requests, replica samples and observations.
reserve-followup/results/    Separate reserve-matched live traces and analysis.
results/twin-validation/     Independent conditional-response evidence.
results/simulation/          All rollout scores and first-seed trajectories.
environment.json             Actual runtime, quota, version and image digest.
controller-verification.json Causal ordering, limits and actuation checks.
paper/                       TeX, final PDF, source export and verification.

ENVIRONMENT
Ubuntu WSL2, existing K3s 1.33.6+k3s1/containerd 2.1.5, Python 3.12.3,
numpy 1.26.4, pandas 2.2.2, scikit-learn 1.5.1 and httpx 0.27.2.
The unchanged service is already deployed in twin-research using the earlier
contribution/deployment.yaml. Its recorded image digest is in environment.json.
Each pod still requests 250m CPU/96Mi and is limited to 500m/192Mi. The new
maximum changes replica capacity, not these per-pod limits or the SLO.
The local kubeconfig is private and is deliberately absent from the handoff.

EXECUTION
From this directory in the existing Ubuntu research environment:

  sudo systemctl start guruge-k3s guruge-research-proxy
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    /opt/guruge-reproduction/twin-venv/bin/python experiments.py
  bash postprocess.sh

The postprocessor waits for all 75 comparisons, then runs the reserve-matched
cohort, independent validation, plant, audits and article builder in sequence.
CPU-heavy simulation is kept out of live measurement periods. The API proxy
must remain loopback-only at 127.0.0.1:8001. The runner discovers the node's
InternalIP and uses the existing NodePort 30081.

ANALYSIS REPLAY
With saved outputs available, run in the research Python environment:

  python analyze_followup.py
  python verify_simulation.py
  python analyze.py
  python build_paper.py

These recompute statistics rather than producing new Kubernetes observations.
The real trial runner skips completed valid comparisons. To perform a new full
run without overwriting evidence, copy this directory to a fresh sibling under
research-reproduction, move the copy's primary and reserve-followup results
directories into archive subfolders, and run there. Keep frozen profiles and
code identical to replay the fitted policy. Recalibrating on another machine
requires a new recorded protocol and hashes; adapting infrastructure paths or
installing a fresh cluster elsewhere is an unverified portability step.

INTERPRETATION
All request outcomes enter each final SLO denominator, including errors/timeouts.
Controller feedback uses only completed responses and pending ages at the
observation boundary. Desired and ready replicas are sampled independently at
one-second intervals. The cost audit bounds its terminal partial sample because
the exact terminal clock is not separately archived. No operational HPA runtime
is inferred from a shadow model calculation. Setup/warm-up allocation and
full-day idle reserves are outside reported trial pod-minutes.
Intervals resample the paired repetitions; individual requests are dependent.
Five primary repeats and three follow-up repeats do not certify universal
reliability. The artifact retains poor and negative outcomes as well as successes.

SIMULATION REPAIR: The first simulation attempt failed when writing NumPy scalar values to JSON. The retry adds only scalar conversion during JSON serialization; simulation and controller logic were unchanged. Verification reconstructs and hashes the original script, checks paired inputs, and reruns two selected cells. Failed output is retained in results/simulation-failed-attempt01.
