"""Validate complete workflow catalog, vector comparisons and pinned source."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;root=Path(sys.argv[1])
catalog=json.loads((P/'catalog.json').read_text())+json.loads((P/'followup_catalog.json').read_text())
expected={s['case'] for s in catalog};assert len(expected)==len(catalog)
actual={f.stem for f in (P/'results').glob('*.json') if f.name.count('.')==1}
assert actual==expected,(sorted(expected-actual),sorted(actual-expected))
source=json.loads((P/'SOURCE_IDENTITY.json').read_text());summary=json.loads((P/'SUMMARY.json').read_text());errors=[];compared=0;worst=0;comparison_flags=[]
for row in summary['cases']:
 r=json.loads((P/'results'/(row['case']+'.json')).read_text())
 assert r.get('source_sha256')==source['production_python_sha256'],row['case']
 if row['error']:
  errors.append(dict(case=row['case'],error=row['error']));continue
 assert row['quality_gate_passed'] and row['termination'] is None,row['case']
 assert 'vs_dense_relative_max_norm' in row,row['case']
 if row['vs_dense_relative_max_norm']>=1e-8:comparison_flags.append(dict(case=row['case'],relative_max_norm=row['vs_dense_relative_max_norm']))
 worst=max(worst,row['vs_dense_relative_max_norm']);compared+=1
verified=0
for e in json.loads((P/'BASE_TREE.json').read_text())['tree']:
 if e['type']!='blob':continue
 b=(root/e['path']).read_bytes();sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
 assert sha==e['sha'],e['path'];verified+=1
controls={}
for f in P.glob('*CONTROLS.json'):controls[f.name]=json.loads(f.read_text())
factors=json.loads((P/'FACTOR_SUMMARY.json').read_text())['cases']
result=dict(workflow_catalog_cases=len(expected),successful_workflows=compared,refusals=errors,worst_field_relative_max_norm_vs_dense=worst,workflow_comparison_check=1e-8,workflow_comparison_flags=comparison_flags,comparison_check_is_study_only=True,source_blobs_reverified=verified,all_original_repository_files_unchanged=True,factor_cases=len(factors),factor_failures=[dict(source=r['source'],variant=r['variant'],error=r['error']) for r in factors if r.get('error')],max_factor_backward_error=max(r['max_backward_error'] for r in factors if not r.get('error')),analytic=json.loads((P/'ANALYTIC_CHECKS.json').read_text()),controls=controls)
(P/'VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['controls','analytic']},indent=2))
