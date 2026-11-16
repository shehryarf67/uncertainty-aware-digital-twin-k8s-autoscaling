"""Show implemented revision and completed development data during the rerun."""
from pathlib import Path
import ast,json,datetime
ROOT=Path(__file__).resolve().parent
target=ROOT/'paper/main_article.tex';text=target.read_text()
if r'\section{Revision Progress}' in text:text=text[:text.index(r'\section{Revision Progress}')]+text[text.index(r'\section{Discussion and Threats to Validity}'):]
tree=ast.parse((ROOT/'build_paper.py').read_text())
literal=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and r'\section{Controller Revision}' in n.value)
method=literal[literal.index(r'\section{Controller Revision}'):literal.index(r'\section{Experimental Design}')]
method=method.replace(r'\section{Controller Revision}',r'\subsection{Implemented Controller Revision}').replace(r'\subsection{',r'\subsubsection{')
method=method.replace(r'\subsubsection{Implemented Controller Revision}',r'\subsection{Implemented Controller Revision}')
method=method.replace('fig:architecture','fig:architecture-revision').replace('eq:slo','eq:slo-revision')
development=[]
for name in ['development-capacity-01','development-capacity-02','development-capacity-03']:development+=json.loads((ROOT/name/'summary.json').read_text())
rows=[]
for n in [4,6,8,12,16]:
    a=next(r for r in development if r['replicas']==n and r['rps']==45);b=next(r for r in development if r['replicas']==n and r['units']==1.8)
    rows.append(f"{n} & {100*a['slo_violation_fraction']:.2f} & {a['p99_ms']:.2f} & {100*b['slo_violation_fraction']:.2f} & {b['p99_ms']:.2f}"+r'\\')
completed=[json.loads(p.read_text()) for p in (ROOT/'results/live').glob('*/summary.json')]
valid=[r for r in completed if r['protocol_valid']]
stamp=datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=5))).strftime('%d %B %Y, %H:%M PKT')
progress=r'''\section{Revision Progress}
This section records the implemented November revision and completed development measurements. Expanded controller comparisons are still running; the earlier sections retain the completed pilot results. All measured numerical entries are black. Red bracketed entries explicitly mark measurements not yet available and are not estimated results.
'''+f'Progress snapshot: {stamp}. '+str(len(valid))+' of the 75 planned primary comparisons have completed with valid timing. A separate eighteen-trial reserve-matched HPA follow-up and eighteen held-out response-validation blocks are specified; their final analyses are pending.\n'+method+r'''
\begin{table*}[t]\centering\small
\caption{Real completed development capacity measurements. These are not final expanded-controller means. The sixteen-replica offered-load blocks lasted fifteen seconds; other blocks lasted five. All values below are measured.}
\begin{tabular}{rrrrr}\toprule
Replicas & 45 RPS bad (\%) & P99 (ms) & 30 RPS, 1.8 work bad (\%) & P99 (ms)\\\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule\end{tabular}\end{table*}
\begin{table}[t]\centering\small
\caption{Expanded-study status. Red brackets mark unfinished analyses.}
\begin{tabular}{lr}\toprule
Quantity & Status\\\midrule
Completed valid primary comparisons & '''+str(len(valid))+r'''/75\\
Final expanded SLO compliance & \textcolor{red}{[pending]}\\
Final paired effect intervals & \textcolor{red}{[pending]}\\
Independent response-validation error & \textcolor{red}{[pending]}\\
\bottomrule\end{tabular}\end{table}
'''
first=[r for r in valid if r['seed']==404]
if len(first)==15:
    labels={'guarded':'Guarded Twin','legacy':'Original dual','no_reserve':'No reserve','cpu_hpa':'CPU HPA','static':'Fixed sixteen'}
    preliminary=[r'\begin{table*}[t]\centering\small',r'\caption{Real preliminary measurements from the first complete repetition (seed 404), selected by the frozen plan rather than performance. These fifteen trials are not the final five-repeat aggregate; all subsequent repetitions remain in progress.}',r'\begin{tabular}{llrrr}\toprule Workload & Policy & Bad (\%) & P99 (ms) & Desired pod-min\\\midrule']
    for scenario in ['legacy_batch','abrupt_batch','continuous']:
        for mode in ['guarded','legacy','no_reserve','cpu_hpa','static']:
            r=next(x for x in first if x['scenario']==scenario and x['controller']==mode)
            preliminary.append(scenario.replace('_',' ')+ ' & '+labels[mode]+f" & {100*r['slo_violation_fraction']:.2f} & {r['p99_ms']:.2f} & {r['desired_pod_minutes']:.2f}"+r'\\')
    preliminary.append(r'\bottomrule\end{tabular}\end{table*}')
    progress+='\n'+'\n'.join(preliminary)+'\n'
anchor=r'\section{Discussion and Threats to Validity}'
assert anchor in text;text=text.replace(anchor,progress+'\n'+anchor,1)
if r'\bibitem{resources}' not in text:
    text=text.replace(r'\end{thebibliography}',r'''\bibitem{resources} Kubernetes Authors, ``Resource Management for Pods and Containers,'' official documentation, accessed 14 November 2026. \url{https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/}.
\end{thebibliography}''')
    text=text.replace(r'\begin{thebibliography}{11}',r'\begin{thebibliography}{12}')
target.write_text(text,encoding='utf8',newline='\n');print('Completed valid primary comparisons:',len(valid))
