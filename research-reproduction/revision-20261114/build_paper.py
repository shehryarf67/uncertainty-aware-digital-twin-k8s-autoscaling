"""Build the self-contained two-column article from completed audited evidence."""
from pathlib import Path
from collections import defaultdict
import csv,json,statistics,zipfile,re
import numpy as np
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'paper'
def read(path):return json.loads(path.read_text())
def f(x,n=2):return f'{float(x):.{n}f}'
def interval(x):return '['+f(x[0])+', '+f(x[1])+']'
def table(headers,rows,caption,label,wide=False,align=None):
    env='table*' if wide else 'table'
    pre=[r'\begin{'+env+r'}[t]\centering\small\setlength{\tabcolsep}{3pt}',r'\caption{'+caption+r'}\label{'+label+'}']
    pre.append(r'\savebox{\databox}{%')
    pre += [r'\begin{tabular}{'+(align or 'l'+'r'*(len(headers)-1))+r'}\toprule',' & '.join(headers)+r'\\\midrule']
    pre += [' & '.join(map(str,r))+r'\\' for r in rows]
    pre += [r'\bottomrule\end{tabular}']
    pre.append('}')
    width=r'\textwidth' if wide else r'\columnwidth'
    pre.append(r'\ifdim\wd\databox>'+width+r'\relax\resizebox{'+width+r'}{!}{\usebox{\databox}}\else\usebox{\databox}\fi')
    pre.append(r'\end{'+env+'}')
    return '\n'.join(pre)

def trajectory():
    lines=[r'\begin{figure*}[t]\centering\begin{tikzpicture}\begin{axis}[width=.97\textwidth,height=5cm,xlabel={Elapsed seconds},ylabel={Replicas},xmin=0,xmax=131,ymin=0,ymax=17,ytick={0,4,8,12,16},legend style={at={(.5,1.04)},anchor=south,legend columns=4,font=\footnotesize},tick label style={font=\footnotesize},label style={font=\small}]']
    for mode,key,color,style,label in [('guarded','desired','black','thick','Guarded desired'),('guarded','ready','black','dashed','Guarded ready'),('legacy','desired','black','densely dotted','Original dual'),('cpu_hpa','desired','black','dashdotted','CPU HPA')]:
        samples=read(ROOT/f'results/live/legacy_batch-404-{mode}-attempt01/replicas.json')
        points=' '.join('('+f(x['time'],3)+','+str(x[key])+')' for x in samples if key in x)
        lines += [r'\addplot[const plot,no marks,'+color+','+style+r'] coordinates {'+points+'};',r'\addlegendentry{'+label+'}']
    lines.append(r'\end{axis}\end{tikzpicture}\caption{Independent one-second replica observations from the predeclared first seed and previously used batch pattern. Desired capacity and ready capacity differ during actuation. All five repetitions enter the results; this trajectory is not selected for best SLO performance.}\label{fig:trajectory}\end{figure*}')
    return '\n'.join(lines)

def main():
    s=read(ROOT/'results/summary.json');assert s['status']=='completed' and s['final_live_runs']==75 and s['source_hashes_verified']
    sim_status=read(ROOT/'results/simulation/status.json');assert sim_status['status']=='completed' and sim_status['trials']==1000
    follow=read(ROOT/'reserve-followup/results/summary.json');assert follow['status']=='completed' and follow['trials']==18
    validation=read(ROOT/'results/twin-validation/summary.json');assert validation['status']=='completed' and validation['conditions']==18
    old=read(ROOT.parent/'contribution/results/summary.json')
    cal=read(ROOT.parent/'contribution/results/forecast-calibration-01/summary.json')['datasets']
    protocol=read(ROOT/'frozen-protocol.json')
    overall={x['controller']:x for x in s['overall']};g=overall['guarded'];v1=overall['legacy'];fixed=overall['static'];abl=overall['no_reserve']
    live={(x['scenario'],x['controller']):x for x in s['aggregate']}
    development=[]
    for name in protocol['development_only']:development+=read(ROOT/name/'summary.json')
    from controller_v2 import GuardedController
    safe=GuardedController(development).safe_work
    sim=list(csv.DictReader((ROOT/'results/simulation/scores.csv').open()))
    assert len(sim)==1000
    sim_groups=defaultdict(list)
    for x in sim:sim_groups[x['regime'],x['controller']].append(x)
    def sm(regime,mode,key):return statistics.mean(float(x[key]) for x in sim_groups[regime,mode])
    before=(ROOT/'paper/archive_20261114/main_article_before_20261114.tex').read_text(encoding='utf8')
    bibliography=before[before.index(r'\begin{thebibliography}'):before.index(r'\end{thebibliography}')]
    bibliography=bibliography.replace(r'{thebibliography}{11}',r'{thebibliography}{13}').replace('accessed 28 October 2026','accessed 14 November 2026')
    body=[r'''\documentclass[10pt,twocolumn,a4paper]{article}
\usepackage[margin=18mm,columnsep=6mm]{geometry}
\usepackage{amsmath,amssymb,booktabs,microtype,graphicx,tikz,pgfplots}
\usepackage[hidelinks]{hyperref}
\usepackage{xurl,placeins}
\pgfplotsset{compat=1.18}
\setlength{\emergencystretch}{1em}
\newsavebox{\databox}
\renewcommand{\dbltopfraction}{0.95}
\renewcommand{\dblfloatpagefraction}{0.85}
\renewcommand{\textfraction}{0.05}
\title{Digital-Twin-Guided Predictive Autoscaling:\\Capacity Calibration, Ready Reserves and Repeated Kubernetes Evaluation}
\author{Shehryar Faisal}
\date{November 2026}
\begin{document}
\twocolumn[\begin{@twocolumnfalse}\maketitle
\begin{abstract}
Predictive autoscaling can fail when forecast uncertainty, service capacity and replica readiness are treated separately. We preserve a published Prophet--LSTM reproduction and investigate why an initial latency-Twin controller met a strict request objective inconsistently. A revised controller replaces an absolute latency-error correction with a measured capacity envelope, a conservative demand bound, recent CPU-cost information, ready capacity reserves and guarded scale-down. Development measurements showed that fixed six-replica capacity failed at peak conditions on the current host, motivating a shared sixteen-replica maximum for the expanded comparison. We execute 75 primary Kubernetes trials across five policies, five repetitions and three workloads, plus eighteen reserve-matched follow-up trials, eighteen independent response-validation blocks and 1,000 independent-plant rollouts.''']
    body.append('The primary cohort measures '+str(s['valid_requests'])+' requests. The revised controller meets the 99'+r'\% HTTP-success-within-500-ms objective in '+str(g['slo_met_runs'])+' of 15 trials, compared with '+str(v1['slo_met_runs'])+' for the original dual policy and '+str(overall['cpu_hpa']['slo_met_runs'])+' for CPU HPA. Mean trial violation rates are '+f(g['mean_trial_violation_percent'])+r'\%, '+f(v1['mean_trial_violation_percent'])+r'\% and '+f(overall['cpu_hpa']['mean_trial_violation_percent'])+r'\%, respectively. The revised controller uses '+f(g['mean_pod_minutes'])+' mean desired pod-minutes versus '+f(fixed['mean_pod_minutes'])+' for fixed sixteen-replica capacity. Reserve-matched HPA complies in FOLLOW_HPA of nine follow-up cells, qualifying attribution of the primary gain. These finite results characterize a reliability--allocation tradeoff on one local service; they do not certify a general SLO guarantee.'+r'\end{abstract}\vspace{4mm}\end{@twocolumnfalse}]')
    body.append(r'''
\section{Introduction}
Kubernetes autoscaling observes demand and resource use, then requests capacity that becomes useful only after replicas are ready. CPU-based Horizontal Pod Autoscaling (HPA) and KEDA provide established execution mechanisms \cite{k8s,keda}. A forecast alone does not determine the resources needed for a latency objective. Request cost, CPU throttling, routing and readiness affect the demand-to-performance relationship.

Our research began with the Prophet--LSTM approach of Guruge and Priyadarshana \cite{guruge}. We first reproduced the released calculations and implemented a separate causal evaluation. An initial uncertainty-aware service-response Twin then exposed two practical failures: sudden demand reached the application before scale-up completed, and large absolute latency residuals made every surrogate replica choice infeasible. Simply adding a larger latency margin did not establish request-level compliance.

This article studies an implemented repair rather than claiming a new general class of autoscaling. We calibrate a service-capacity envelope from development measurements, retain ready capacity, react conservatively to observed pressure, and restrict scale-down while the observed violation fraction is high. We compare this controller with the original dual policy under a common expanded capacity limit, a reserve ablation, native CPU HPA and a fixed-capacity reference. Previous results remain available as a diagnostic pilot, not a resource-matched estimate of the revision's effect.

We ask: (RQ1) what does a faithful forecasting reproduction establish after causal evaluation; (RQ2) how consistently does the revision meet the measured SLO, and at what allocation cost; and (RQ3) which roles do reserve capacity, pressure response and planning horizon play under bursts, drift and observation or startup delay? The evidence combines saved historical forecasts, repeated real Kubernetes execution and a separate queueing plant. Each has a distinct scope.

\section{Related Work}
Prophet models trend and seasonal structure \cite{prophet}; LSTM provides gated recurrent memory \cite{lstm}. The reference hybrid assigns trend and seasonality to Prophet and forecasts residuals with an LSTM \cite{guruge}. Our neural reproduction concerns this baseline, while the live controller uses a lightweight short-horizon predictor so that policy differences are not confused with retraining a larger forecaster.

Adaptive conformal inference updates calibration levels using observed misses \cite{aci,online}. The initial pilot used clipped rolling ACI-style corrections. The revision uses a conservative finite-window upper-error statistic; it does not inherit the original algorithms' guarantees. In particular, workload-bound coverage and request-level latency compliance have different outcomes and denominators.

BACC version 2 combines forecast calibration, measured service-risk profiling and budget feedback, including latency and CPU objectives \cite{bacc}. It substantially overlaps the broad proposal. Our evaluated choice is a measured capacity envelope with ready reserves and conservative actuation guards; it is not a priority claim over calibrated or latency-aware autoscaling. KARMA uses a cluster-trace Twin for simulation-based multi-agent training and cluster transfer \cite{karma}. SLO-Scaler describes Bayesian workload/tail-latency prediction and dependency-aware decisions \cite{sloscaler}; InferScale combines predictive and readiness-sensitive SLO control \cite{inferscale}. We do not reproduce these full systems or rank our measurements against their published results. The contribution is an auditable empirical study of concrete failure repairs and their costs.

\section{Baseline Validation}
Let $y_t$ be workload, $p_t$ a Prophet estimate and $r_t=y_t-p_t$ its residual. A causal one-minute hybrid predicts
\begin{equation}\widehat y_{t\mid t-1}=p_t+f_\theta(r_{t-1}).\end{equation}
The scored observation is excluded from its input. Earlier observed test counts may enter later forecasts: this is rolling one-step evaluation. The official supplied NASA-HTTP and WorldCup98 files contain 81,396 and 125,300 observed minute rows, with chronological 70/30 partitions of 56,977/24,419 and 87,710/37,590. They omit 7,884 and ten calendar minutes. Gap filtering leaves 24,390 NASA and 37,590 WorldCup eligible targets; missing traffic is not asserted to be zero.

The main released notebooks use linear Prophet growth for NASA and flat growth for WorldCup, changepoint prior 5.1, seasonality prior 30, daily/weekly Fourier orders 50/20 and no yearly seasonality. Two 50-unit LSTM layers and a linear output use look-back one, Adam/MSE, batch 16, a 20-epoch cap, validation fraction 0.2 and patience-five early stopping with restored best weights. The article prints 50 epochs. Four faithful fits, two per dataset, stop after six epochs and restore epoch-one weights. The CPU environment uses Python 3.12.14, TensorFlow 2.17, Keras 3.4.1 and Prophet 1.1.5 on an Intel i7-1255U.

The released combination places a next-row residual prediction on the current row and fills its final missing prediction with observed truth. NASA residual scaling and WorldCup count scaling include test data. Faithful runs retain these behaviours. A separate implementation fixes alignment and the truth fallback, fits transforms on the early neural fitting prefix, filters gaps and fixes random states to 42. Prophet fits the full outer training period; neural validation is conditional on that fitted Prophet, while outer-test observations remain outside fitting. The changes are joint corrections, not a one-factor ablation.
''')
    body.append(table(['Trace','Published','Faithful','Causal'],[['NASA','7.990','8.02163','14.2902'],['WorldCup','0.003358','0.00337950','0.00388174']],r'Forecast RMSE. Faithful means use full released tests; causal NASA excludes 29 gap targets. WorldCup is displayed on the common author scale after causal fitting.','tab:baseline'))
    body.append(r'''
On common NASA targets, faithful mean RMSE is 8.01251. WorldCup causal raw-count RMSE is 890.5685, compared with persistence at 762.7463; NASA persistence is 16.3871. The higher causal errors change the interpretation of the released scores without identifying one isolated cause. Original models, predictions and inputs are preserved.

\section{Initial Controller Diagnosis}
An earlier integration check connected the authors' Java 21/Spring Boot 3.4.2 application and forecasting scaler to KEDA 2.18, Prometheus 2.55.1 and local K3s. Scaler logic was preserved while compatible gRPC bindings were regenerated. Stable, increasing, spike and decreasing scenarios produced 6,870 measured requests per controller in scheduling-validated runs. Forecast KEDA and CPU HPA had zero HTTP failures and zero observations above 500 ms. Forecast scaling held three replicas; HPA moved from one to three. Sampled allocation was 23.286 versus 13.778 pod-minutes. These short integration sequences established actuation without exposing a useful overload boundary.

The subsequent CPU-service pilot fitted a monotone effective-P99 response Twin, $g(x)$, to $x=\lambda c/n$, where $\lambda$ is offered rate, $c$ median CPU milliseconds and $n$ ready replicas. Eighteen fit and twelve calibration blocks initialized a frozen curve and a separate latency residual margin. The policy combined this with a demand residual margin, planning over two cycles and enumerating one to six replicas. Each cycle offered five seconds of traffic and reserved three seconds for drainage.

Across fifteen pilot trials, the dual policy averaged 10.40\% request violations and satisfied the strict SLO in only one of three repetitions. Point-Twin control averaged 39.67\%. Twelve of 48 dual decisions carried a latency correction above the 500-ms target itself, making every positive-latency candidate fail its surrogate constraint. Maximum-replica fallback was therefore not evidence of feasible constraint satisfaction. Conditional mapping residuals also mixed queueing under the realized state with the counterfactual effect of adding capacity. These observations motivated the revision.

\section{Controller Revision}
\subsection{Objective and Capacity Evidence}
A request complies only if HTTP status is 200 and measured client latency $\ell_i\leq500$ ms. The request objective is
\begin{equation}v=\frac{1}{N}\sum_i\mathbf1\{\mathrm{status}_i\ne200\lor\ell_i>500\mathrm{\ ms}\}\leq0.01.\label{eq:slo}\end{equation}
Timeouts and fast rejections count as violations. This objective differs from workload prediction coverage. Allocation is desired-replica pod-minutes, including pending capacity, rather than monetary billing or CPU energy.

We retain the same instrumented PBKDF2 CPU service. A pod requests 250m CPU/96Mi and is limited to 500m/192Mi. A single processing semaphore serializes work per pod; queue waits beyond two seconds return HTTP 429 and clients time out after three seconds. Readiness includes a five-second startup delay and two-second probe cadence. Kubernetes CPU limits can impose throttling \cite{resources}. The author application and original baseline files are unchanged.

Before final testing, development capacity measurements cross four offered-load/work conditions with 4, 6, 8, 12 and 16 fixed replicas. Conditions are 5, 25 and 45 requests/s with unit work, and 30 requests/s with 1.8-fold work. The 4--12-replica blocks use five seconds of offered traffic and three seconds of drainage; sixteen-replica blocks extend offered traffic to fifteen seconds. These twenty blocks contain 3,675 measured requests. At the current host conditions, fixed six replicas failed the target at peak traffic and higher work cost; sixteen had no observed violations in the longer checks. This is empirical capacity evidence, not a proof that every six-replica strategy is impossible. The expanded comparison consequently gives every adaptive policy the same sixteen-replica ceiling.

For development block $j$, define $x_j=\lambda_jc_j/n_j$. A monotone response curve is fitted to measured effective P99. For model diagnostics, a failure receives an effective penalty of at least 2,000 ms so that fast errors do not resemble good service. Actual SLO metrics and client quantiles always use measured latency and status. Sizing uses an operating envelope extracted from the same development profile:
\begin{align}
\mathcal A&=\{j:v_j\leq0.01,\ P99_j\leq400\mathrm{\ ms}\},\\
C&=\min\{200,\ 0.8\max_{j\in\mathcal A}x_j\}.\label{eq:capacity}
\end{align}
The 20\% headroom and 400-ms screening target are engineering choices fixed before evaluation. $C$ is CPU milliseconds per second per ready replica; it is not a confidence-certified capacity estimate. The frozen response curve supplies support and tail diagnostics, while this empirical envelope directly drives replica sizing.

\subsection{Demand and Cost Corrections}
The controller observes completed outcomes, issued-request counts and current replica state. Initial rate history uses two measured five-RPS warm-up cycles. Initial CPU cost uses their successful-response P90. A rolling maximum of the most recent four available response CPU-P90 estimates provides $\bar c_t$, allowing immediate upward adjustment and slower decay after a service-cost shift. Failed or incomplete responses do not reveal future CPU work.

For horizon $h_t$, the point demand forecast is the maximum of the last three observed rates and the current rate extrapolated using the latest nonnegative rate increase. Forecast errors compare an issued point with the maximum of the next $h_t$ observed rates. An error enters calibration only after its full horizon matures. The last forty signed errors provide a nonnegative nominal-99\% upper correction $q_t$, with finite ranks capped at the largest observed score. With at most forty scores, this maximum-score rule does not provide exact distribution-free 99\% finite-sample coverage. We evaluate it empirically and make no inherited conformal guarantee.

\subsection{Readiness, Pressure and Scale-Down}
Observed desired-to-ready transitions update a startup estimate using equal weight on its previous value and the latest observed transition lag, floored at eight seconds. The horizon is
\begin{equation}h_t=\max\{2,\min(6,\lceil\widehat d_t/8\rceil+1)\}.\end{equation}
The nominal startup estimate is eight seconds. At each completed observation, the provisional replica requirement is
\begin{equation}n_t^{\rm req}=\left\lceil\frac{(\widehat\lambda_t+q_t)\bar c_t}{C\beta_t}\right\rceil+2,\label{eq:sizing}\end{equation}
clipped to the common maximum, with an eight-replica desired reserve initialized with all eight ready. The two additional replicas and reserve are explicit resource costs. The reserve ablation removes only the eight-replica floor; it begins with the same eight ready replicas and retains the other logic.

The factor $\beta_t\in[0.5,1]$ tightens by a factor 0.85 when observed violations exceed 0.5\% or effective P99 exceeds 450 ms. After eight clean observations it recovers by 0.025 per cycle, up to one. Violations above 1\%, effective P99 above 500 ms, or an active three-cycle pressure hold request the maximum. Scale-down requires three lower recommendations, three clean observations, no ready deficit and cumulative observed violations at most 0.5\%. At most one replica is removed per decision. This is a conservative burn guard rather than a general budget-pacing optimizer.

Unsupported or over-limit demand is logged. Neither a maximum-capacity request nor a diagnostic ``feasible'' flag proves Equation~\ref{eq:slo}. The revision avoids applying an irreducible absolute latency residual to every counterfactual replica count, but still relies on approximate balancing, finite profiling and service instrumentation.

\begin{figure}[t]\centering
\resizebox{\columnwidth}{!}{\begin{tikzpicture}[font=\footnotesize]
\node[draw,align=center] (o) at (0,0) {Observed requests\\and replica state};
\node[draw,align=center] (p) at (3.4,0) {Demand bound\\and CPU-cost history};
\node[draw,align=center] (t) at (3.4,-1.4) {Capacity envelope\\and pressure guards};
\node[draw,align=center] (a) at (0,-1.4) {Reserve and readiness\\aware replica execution};
\draw[->] (o)--(p);\draw[->] (p)--(t);\draw[->] (t)--(a);\draw[->] (a)--(o);
\end{tikzpicture}}
\caption{Implemented revision. Decisions use only observed telemetry; future traffic and work schedules remain confined to the load generator.}\label{fig:architecture}\end{figure}

\section{Experimental Design}
\subsection{Repeated Kubernetes Evaluation}
The cluster remains K3s v1.33.6+k3s1/containerd 2.1.5 under Ubuntu WSL2 on the local Intel CPU host. A loopback-only API proxy serves the external controller. Source, development inputs and controller settings are hashed before final comparisons. Existing forecasting and pilot artifacts remain preserved.

Five policies are tested: guarded revision, original dual policy, reserve ablation, native CPU HPA and fixed sixteen replicas. The original dual algorithm and its earlier fitted profile are retained; its replica maximum is raised to sixteen for this comparison. All adaptive policies start with eight ready replicas. The fixed reference is provisioned with sixteen before measurement, so it is a capacity/cost reference with an explicit initial-capacity advantage. Two common low-rate warm-up cycles and setup allocation are excluded. Results concern the measured trial interval, not full deployment lifetime billing.

Native HPA uses a 70\% CPU-request target, replica bounds one to sixteen, zero scale-up stabilization and a 24-second scale-down stabilization window. It is installed after warm-up to preserve the common initial adaptive capacity. HPA retains native reconciliation and sensing timing \cite{k8s}; external policies decide every eight seconds. This is an operational comparison, not a timing-matched implementation of the same algorithm.

An exploratory follow-up addresses minimum-replica confounding directly. It compares the unchanged guarded controller with native HPA whose minimum is also eight and maximum sixteen. Three fresh seeds, 909, 1010 and 1111, give eighteen additional trials across the same three workloads, with randomized within-seed policy and scenario ordering. This follow-up was specified after early primary outcomes had been inspected; its paired results are reported separately rather than being portrayed as part of the original frozen 75-comparison plan. No controller parameters are refitted.

Seeds 404, 505, 606, 707 and 808 define five repetitions. Scenario and policy orders are shuffled deterministically per seed. The three sixteen-cycle workloads are fixed before final testing (Table~\ref{tab:workloads}). The previous batch shape is deliberately reused and is not claimed to be an unseen workload. Two new shapes introduce abrupt changes or uninterrupted traffic. The controller never receives their future rates or work multipliers.
''')
    workload_rows=[]
    short={'legacy_batch':'Previous batch','abrupt_batch':'Abrupt batch','continuous':'Continuous'}
    for name,cfg in protocol['scenarios'].items():workload_rows.append([short[name],cfg['active_seconds'],sum(cfg['rates'])*cfg['active_seconds'],', '.join(map(str,cfg['rates']))])
    body.append(table(['Workload','Active s/cycle','Requests/trial','Rate sequence (requests/s)'],workload_rows,r'Each cycle spans eight seconds. Batch workloads offer traffic for five seconds and pause for three; continuous traffic uses all eight. Work multipliers rise to 1.8 in cycles 13--16 of the previous batch, to 1.6 in cycles 11--13 of abrupt batch, and to 1.6 in cycles 11--16 of continuous traffic. Other cycles use unit work.','tab:workloads',wide=True,align='lrrl'))
    body.append(r'''
The generator uses absolute send deadlines, jittered request slots and no connection reuse. Traffic production runs independently of telemetry and control, preventing controller API time from creating artificial drain pauses in continuous trials. Requests retain send/finish times, HTTP status, latency, CPU and queue information where observed, and dispatch delay. Every scheduled request enters final scoring, including late completions and timeouts. Control feedback at a boundary uses completed outcomes before that boundary and outstanding-response ages, with no future response payloads.

An independent sampler records desired and ready replicas approximately once per second. Desired pod-minutes integrate these observations with the measured terminal partial interval. The audit independently bounds the terminal contribution because its exact terminal clock is not separately archived. Dispatch delay must remain below 500 ms, sampler gaps below three seconds, decision lateness below one second, and request counts must match the schedule. A timing-invalid attempt may be repeated once; all attempts remain available. SLO failures are valid outcomes and never trigger replacement.

\subsection{Historical Bounds and Independent Plant}
Saved causal forecasts are evaluated without retraining weights. The first 20\% of previously eligible outer-test targets form a new calibration prefix: 4,878 NASA and 7,518 WorldCup observations. Remaining rolling evaluations contain 19,512 and 30,072 targets. Static calibration uses the prefix's upper-error quantile; adaptive calibration starts from its last forty errors and updates after each outcome. These trace-bound results concern demand events, not request-latency certification.

Independent response validation uses eighteen new combinations: fixed replica counts 6, 10 and 14; rates 12, 24 and 36 requests/s; and work multipliers 1.1 and 1.5. Each has five seconds of offered load and three seconds of drainage, producing 2,160 additional measured requests. Neither the response curve nor operating envelope is refitted. CPU input for this check is realized within the block, so it validates the conditional response mapping, not ex-ante CPU forecasting or a full-cluster counterfactual guarantee.

The new simulator generates labels using Poisson arrivals and independent lognormal CPU work, never using the fitted response Twin. Log-scale standard deviation is 0.3 and mean CPU work derives from unit-work development measurements. A central dispatcher assigns requests to the earliest free ready server supplying 0.5 CPU core. Queue admission and three-second client timeout are modeled; successful completed responses alone expose their CPU work. Removed-server outcomes remain scored.

Twenty-five paired seeds, five regimes and eight policies give 1,000 rollouts of 64 eight-second cycles. Regimes cover smooth demand, bursts, a 1.8-fold service-cost shift, startup delay increased from eight to 24 seconds, and one-cycle observation delay. In the delay case, demand, response and CPU feedback are delayed while replica state remains current. Policies include the guarded revision, reserve ablation, original dual policy, CPU-reactive proxy, fixed eight and fixed sixteen replicas, and isolated emergency-response and horizon ablations. The latter change only the named assignment in the frozen controller method. The proxy is not native HPA. Shared arrival/service input hashes verify pairing across policies.

\subsection{Analysis and Claim Scope}
We report per-workload compliance counts, mean trial violation rates, mean per-trial P99 and allocation. Paired seed differences compare the revision with each live comparator. Descriptive percentile bootstrap intervals use 10,000 resamples of the five paired repetitions \cite{bootstrap}. Requests within a run are temporally dependent and are not treated as independent statistical replications. With five repetitions, interval precision is limited; an all-zero empirical outcome can yield a degenerate bootstrap interval without proving zero risk. Simulation intervals characterize the selected plant and seeds rather than a population of real clusters.

\section{Results}
\subsection{Preserved Forecasting Evidence}
''')
    body.append(table(['Trace','Point','Static','Adaptive'],[[{'nasa':'NASA','fifa':'WorldCup'}[x['dataset']],f(100*x['point_coverage']),f(100*x['split_coverage']),f(100*x['adaptive_coverage'])] for x in cal],r'Held-out historical demand upper-bound coverage (\%), nominal 90\%. This analysis uses a new calibration prefix of saved test predictions and does not change predictor weights.','tab:historical'))
    body.append(r'''The adaptive historical bounds approach their nominal workload coverage. WorldCup static bounds are more conservative. This does not reduce point forecast RMSE or imply that the later control loops achieve their request SLO.
\subsection{Development Capacity Checks}''')
    dev_rows=[]
    for n in [4,6,8,12,16]:
        rs=[x for x in development if x['replicas']==n];a=next(x for x in rs if x['rps']==45);b=next(x for x in rs if x['units']==1.8)
        dev_rows.append([n,f(100*a['slo_violation_fraction']),f(a['p99_ms']),f(100*b['slo_violation_fraction']),f(b['p99_ms'])])
    body.append(table(['Replicas',r'45 RPS bad \%','P99 ms',r'30 RPS, 1.8 work bad \%','P99 ms'],dev_rows,r'Development measurements preceding final tests. These are single blocks per condition; sixteen-replica offered-load blocks last fifteen seconds, other blocks five. Sampling variability and host conditions limit the inferred capacity boundary.','tab:capacity',wide=True))
    body.append('The selected operating threshold is '+f(safe)+' CPU-ms/s per ready replica. The capacity measurements justify evaluating a larger shared ceiling, while the matched reruns, rather than a direct comparison with the old six-replica pilot, assess policy differences under that ceiling.')
    body.append(table(['Conditional response check','Observed'],[['Effective-P99 MAE (ms)',f(validation['effective_p99_mae_ms'])],['Median absolute error (ms)',f(validation['median_absolute_error_ms'])],['SLO-compliant fixed-load blocks',str(validation['conditions_meeting_slo'])+'/18'],['False-safe envelope cases',str(validation['false_safe_conditions'])+'/'+str(validation['envelope_safe_conditions'])]],r'Independent response mapping at eighteen new load/work/replica combinations, using realized CPU input. Screening an operating point as safe is not a guarantee for future traffic.','tab:fidelity',align='lr'))
    body.append('The independent validation measures '+str(validation['requests'])+' requests. It evaluates interpolation to new rate/work combinations and replica counts; its conditional CPU input and one short block per condition limit ex-ante and counterfactual interpretations.')
    body.append(r'\subsection{Repeated Live SLO Outcomes}')
    live_rows=[]
    for scenario in protocol['scenarios']:
        for mode in protocol['controllers']:
            x=live[scenario,mode]
            live_rows.append([short[scenario],x['label'],str(x['slo_met_runs'])+'/5',f(x['mean_violation_percent']),interval(x['bootstrap95_violation_percent']),f(x['p99_ms']),f(x['pod_minutes'])])
    body.append(table(['Workload','Policy','Met',r'Bad \%',r'95\% interval','P99 ms','Pod-min'],live_rows,r'Means across five real Kubernetes repetitions. P99 is the mean of per-run client P99 values. SLO runs satisfy at least 99\% HTTP-200 responses within 500 ms. Intervals resample runs; zero empirical violations do not certify zero future risk.','tab:live',wide=True,align='lllrrrr'))
    body.append('All '+str(s['final_live_runs'])+' selected comparisons contain '+str(s['valid_requests'])+' scored requests. '+str(s['invalid_attempts'])+' additional timing-invalid attempts are retained. Across the fifteen workload--seed cells, guarded control complies in '+str(g['slo_met_runs'])+', the original dual policy in '+str(v1['slo_met_runs'])+', CPU HPA in '+str(overall['cpu_hpa']['slo_met_runs'])+', the reserve ablation in '+str(abl['slo_met_runs'])+', and fixed sixteen in '+str(fixed['slo_met_runs'])+'. Means across trials give '+f(g['mean_trial_violation_percent'])+r'\% violations for the revision versus '+f(v1['mean_trial_violation_percent'])+r'\% for original dual control. Different workloads offer different numbers of requests; compliance counts and the per-workload table therefore remain primary, rather than substituting a pooled percentage for each trial objective.')
    body.append(trajectory())
    body.append(r'\subsection{Allocation and Paired Comparisons}')
    pair_rows=[]
    for x in s['paired_comparisons']:
        if x['comparison'] not in ['guarded minus legacy','guarded minus cpu_hpa','guarded minus static']:continue
        mode=x['comparison'].split(' minus ')[1]
        pair_rows.append([short[x['scenario']],{'legacy':'Original dual','cpu_hpa':'CPU HPA','static':'Fixed sixteen'}[mode],f(x['violation_pp']),interval(x['violation95']),f(x['relative_pod_minutes_percent'])])
    body.append(table(['Workload','Reference','Bad-rate difference pp',r'Paired 95\% interval',r'Allocation change \%'],pair_rows,r'Guarded minus reference comparisons over matched workload seeds. Negative violation differences favour guarded control; negative allocation changes mean fewer desired pod-minutes. References share the sixteen-replica ceiling; fixed capacity starts at sixteen.','tab:paired',wide=True,align='llrrr'))
    body.append('Mean desired allocation is '+f(g['mean_pod_minutes'])+' pod-minutes for guarded control, '+f(v1['mean_pod_minutes'])+' for the original dual policy and '+f(fixed['mean_pod_minutes'])+' for fixed sixteen. The guarded-versus-fixed difference is '+f(100*(g['mean_pod_minutes']/fixed['mean_pod_minutes']-1))+r'\%. More replicas can buy reliability; the comparison does not justify claiming simultaneous universal cost and latency improvement. Setup, warm-up and full-day idle capacity are outside these trial costs.')
    body.append(r'\subsection{Reserve-Matched Native HPA}')
    follow_rows=[]
    for x in follow['results']:
        follow_rows.append([short[x['scenario']],str(x['guarded_met'])+'/3',str(x['hpa_reserve_met'])+'/3',f(x['guarded_bad_percent']),f(x['hpa_reserve_bad_percent']),f(x['guarded_pod_minutes']),f(x['hpa_reserve_pod_minutes'])])
    body.append(table(['Workload','Guarded met','HPA-eight met',r'Guarded bad \%',r'HPA-eight bad \%','Guarded pod-min','HPA-eight pod-min'],follow_rows,r'Separate exploratory cohort with both adaptive policies initialized at eight and constrained to the same minimum eight and maximum sixteen. Three fresh paired repeats per workload; the frozen primary cohort is unchanged.','tab:reserve_hpa',wide=True,align='lrrrrrr'))
    fm=sum(x['guarded_met'] for x in follow['results']);hm=sum(x['hpa_reserve_met'] for x in follow['results'])
    gc=statistics.mean(x['guarded_pod_minutes'] for x in follow['results']);hc=statistics.mean(x['hpa_reserve_pod_minutes'] for x in follow['results'])
    body.append('The reserve-matched follow-up contains '+str(follow['requests'])+' requests. Guarded control complies in '+str(fm)+' of nine cells and minimum-eight HPA in '+str(hm)+'. Mean allocation is '+f(gc)+' versus '+f(hc)+' pod-minutes. This comparison tests whether the primary gain over minimum-one HPA extends beyond warm capacity; it is a separate exploratory cohort rather than a retroactively randomized part of the original study.')
    if hm>=fm and hc<gc:
        body.append('The simpler reserve-matched HPA matches or exceeds the guarded policy in empirical compliance and uses fewer replicas. The evidence therefore does not support attributing a reliability advantage to the added forecasting/Twin logic over this stronger reference. Warm capacity is an important explanation for the primary comparison.')
    body.append(r'\subsection{Ablation and Stress Sensitivity}')
    ablation_rows=[]
    for scenario in protocol['scenarios']:
        x=next(x for x in s['paired_comparisons'] if x['scenario']==scenario and x['comparison']=='guarded minus no_reserve')
        ablation_rows.append([short[scenario],f(x['violation_pp']),interval(x['violation95']),f(x['relative_pod_minutes_percent'])])
    body.append(table(['Workload',r'$\Delta$ bad pp',r'95\% interval',r'$\Delta$ cost \%'],ablation_rows,r'Live reserve ablation: guarded minus otherwise identical policy without the eight-replica floor. Both begin with eight ready replicas.','tab:ablation'))
    if abl['slo_met_runs']>=g['slo_met_runs'] and abl['mean_trial_violation_percent']<=g['mean_trial_violation_percent'] and abl['mean_pod_minutes']<g['mean_pod_minutes']:
        body.append('The reserve ablation matches or exceeds the guarded policy\'s aggregate empirical reliability while using less allocation. Thus these live tests do not justify the reserve\'s additional cost; its value cannot be assumed merely because headroom is intuitively protective.')
    else:
        body.append('The reserve ablation quantifies a specific resource-protection choice. Its observed effect varies by workload and should not be treated as a universal advantage for a fixed eight-replica floor.')
    sim_rows=[]
    for regime in ['smooth','burst','service_drift','slow_readiness','observation_delay']:
        sim_rows.append([regime.replace('_',' '),f(100*sm(regime,'guarded','violation_fraction')),f(100*sm(regime,'no_reserve','violation_fraction')),f(100*sm(regime,'no_emergency','violation_fraction')),f(100*sm(regime,'no_horizon','violation_fraction')),f(100*sm(regime,'cpu_proxy','violation_fraction')),f(sm(regime,'guarded','mean_desired_replicas'))])
    body.append(table(['Regime','Guarded','No reserve','No emergency',r'$h=1$','CPU proxy',r'Guarded $n$'],sim_rows,r'Independent-plant means across 25 paired seeds per regime. All ablation columns show violation percentages. The central queue omits Kubernetes routing and CFS details, so these values are not live-cluster outcomes. Full eight-policy scores are retained in the artifact.','tab:simulation',wide=False))
    body.append('The simulator contributes '+str(len(sim))+' new rollouts, supplementing the preserved 350-rollout pilot. It isolates stress and component changes under shared generated inputs, but cannot replace the 75 measured Kubernetes comparisons. A reactive proxy or fixed-eight policy may perform well in its balanced central queue even when native HPA or smaller capacity performs poorly in live routing; such differences constrain transfer claims.')
    body.append(r'''

\section{Discussion and Limitations}
\textbf{Capacity and algorithm effects.} The old pilot used at most six replicas and one initial replica. The expanded experiment uses a common maximum of sixteen and eight initial ready replicas for adaptive policies. Direct before/after SLO percentages mix these resource changes with policy changes. The resource-matched original-policy reruns, reserve ablation and fixed-capacity reference provide the relevant comparisons. Development observations of poor fixed-six behaviour support capacity provisioning decisions but do not prove that every possible six-replica design fails.

\textbf{Empirical reliability, not certification.} Forecast bounds, conditional model residuals, surrogate feasibility and request compliance concern different events. Temporal dependence, finite maximum-score ranks, candidate selection and workload shift prevent importing a distribution-free latency theorem. A run with no bad requests remains finite evidence. Five repetitions per workload do not establish production reliability or a rare-event failure probability. Bootstrap intervals describe the selected repetitions and may be degenerate when all measured values agree.

\textbf{Calibration and Twin scope.} The revised operating envelope is frozen from twenty development blocks on one service. CPU cost is supplied by successful response instrumentation; applications without it require another observation path. Per-block P99 is noisy, especially at low rates. The two-hundred CPU-ms/s cap, twenty-percent headroom, two extra replicas, reserve size and pressure thresholds are engineering settings, fixed before tests rather than optimized universally. The response curve's tail/support checks are diagnostics; the empirical capacity envelope drives sizing. The independent conditional response check does not establish ex-ante CPU forecasting accuracy, unobserved counterfactual fidelity or a full cluster Twin. The original-policy comparison also changes the profiling approach as part of the revision, so its entire effect cannot be attributed to one guard.

\textbf{Traffic and system scope.} The live system is an instrumented CPU endpoint on one shared laptop/WSL node, rather than a multi-service benchmark, inference deployment or public-cloud cluster. Native HPA and the external loop have different sensing and reconciliation timing. Two workloads retain drain intervals, while one removes those intervals; conclusions do not extend to arbitrary continuous arrival processes. The synthetic plant uses central dispatch and simplified CPU service, and its conclusions must remain separate from Kubernetes measurements. Desired-replica allocation includes pending capacity but is not billing, energy or achieved CPU efficiency.

\textbf{Claim boundary.} The evidence supports a reproducible account of this controller's measured compliance and resource costs, including failed and negative ablation outcomes. It does not establish unprecedented architecture, superiority to unimplemented contemporary systems, globally minimal replicas or universal SLO guarantees. A broader study should add services, hardware environments, longer observation periods and independently reproduced contemporary controllers.

\section{Conclusion}
''')
    body.append('We preserved a forecasting baseline, diagnosed an inconsistent initial latency-Twin policy and implemented a capacity-calibrated controller with causal demand corrections, CPU-cost history, readiness planning and actuation guards. The expanded real-cluster study contains 75 comparisons and '+str(s['valid_requests'])+' measured requests; the revised policy meets the strict SLO in '+str(g['slo_met_runs'])+' of fifteen workload--seed cells versus '+str(v1['slo_met_runs'])+' for the original dual policy under the same maximum capacity. Mean guarded allocation is '+f(g['mean_pod_minutes'])+' desired pod-minutes versus '+f(fixed['mean_pod_minutes'])+' for fixed sixteen. Component ablations and 1,000 independent-plant rollouts characterize where protection and cost arise. These findings conclude the bounded empirical study while leaving broader reliability, cost optimality and counterfactual-Twin guarantees unestablished.')
    body.append(r'''
\appendix
\section{Reproducibility}
The artifact retains original source, inputs, model/prediction files, earlier results, every new request trace, replica observations and timing records. New code and protocols are in \texttt{revision-20261114/}; the earlier \texttt{contribution/} directory is preserved. The frozen live protocol records seeds, workloads, ordering, capacity and validity thresholds, plus source and development-input hashes. The independent audit recomputes counts, statuses, latency quantiles, schedule validity and paired-input consistency. It bounds the unarchived terminal allocation clock contribution rather than claiming exact independent reconstruction of that last interval.

The live runner executes \texttt{experiments.py}; \texttt{simulate.py} runs the independent plant, \texttt{analyze.py} audits all 75 selected comparisons, and \texttt{build\_paper.py} generates this article from completed evidence. Dependency freezes, manifests and the previous source audit describe the local K3s/WSL environment. No public repository or external publication is claimed.

The final paper uses exactly one root-level source, \texttt{main\_article.tex}. All sections, bibliography entries and vector plot coordinates are embedded. Older TeX drafts reside in archive folders. No additional TeX input, image, bibliography database or external plot-data file is required to compile the two-column manuscript.
''')
    body.append(bibliography)
    body.append(r'''\bibitem{resources} Kubernetes Authors, ``Resource Management for Pods and Containers,'' official documentation, accessed 14 November 2026. \url{https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/}.
\bibitem{bootstrap} B.~Efron, ``Bootstrap Methods: Another Look at the Jackknife,'' \emph{The Annals of Statistics}, 7(1), pp.~1--26, 1979. \url{https://doi.org/10.1214/aos/1176344552}.
\end{thebibliography}
\end{document}''')
    text='\n\n'.join(body)
    text=text.replace('FOLLOW_HPA',str(sum(x['hpa_reserve_met'] for x in follow['results'])))
    assert not re.search(r'\\(?:input|include|includegraphics|bibliography)\s*\{',text)
    assert text.count(r'\bibitem')==13
    OUT.mkdir(exist_ok=True)
    (OUT/'main_article.tex').write_text(text,encoding='utf8',newline='\n')
    print(OUT/'main_article.tex')

if __name__=='__main__':main()
