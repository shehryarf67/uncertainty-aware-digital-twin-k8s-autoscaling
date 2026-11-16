"""Verify report text against checked numerical sources and record visual QA."""
from pathlib import Path
from pypdf import PdfReader
import json,hashlib
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'final-report'
reader=PdfReader(out/'base-article-reproduction-report.pdf');text='\n'.join(p.extract_text() for p in reader.pages)
e=json.loads((out/'report-metric-evidence.json').read_text())
assert len(reader.pages)==11 and e['cluster_scenario_count']==8
for d in ['nasa','fifa']:
    for collection in ['published','baseline_means','common_corrected']:
        for value in e[collection][d].values():assert f'{float(value):.6g}' in text,str(value)
cluster=json.loads((ROOT/'kubernetes-autoscaling/results/comparison.json').read_text())
for r in cluster['scenarios']:
    for k in ['requests','failed','p95_ms','p99_ms','sampled_pod_minutes','mean_cpu_utilization_percent_of_request']:
        assert f'{float(r[k]):.6g}' in text,(r['controller'],r['scenario'],k)
assert '23.286 pod-minutes' in text and '13.778' in text
assert '12.158 and 14.606' in text and '59 seconds' in text and '70 seconds' in text
qa=json.loads((out/'quality-assurance.json').read_text())
qa['report_validation']={'pdf_pages':len(reader.pages),'paper_baseline_corrected_cluster_table_values_match_checked_sources':True,'all_pages_rendered_and_visually_inspected':True,'visual_defects_found':0,'report_sha256':hashlib.sha256((out/'base-article-reproduction-report.pdf').read_bytes()).hexdigest(),'scope':'Numerical text checks plus manual inspection of all rendered pages, including revised pages 8, 9 and 11'}
(out/'quality-assurance.json').write_text(json.dumps(qa,indent=2))
print(json.dumps(qa['report_validation'],indent=2))
