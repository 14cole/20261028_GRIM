"""Saved-array replay and recorded-counter analysis, not a fresh solver run."""
import json,os,statistics
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;R=Path(os.environ.get('RESULTS_DIR',P/'results'))
specs={}
for name in ('suite_timing','suite_audit','suite_reference','suite_capacity'):specs.update(json.loads((P/(name+'.json')).read_text()))
def arrays(label):
    with np.load(R/(label+'-solve0000.npz')) as z:d={k:z[k] for k in z.files}
    with np.load(R/(label+'-fields.npz')) as z:d['field']=z['field']
    return d
reference=arrays('dense-fresh');rows=[];comparisons=[]
for label,spec in specs.items():
    d=json.loads((R/(label+'.json')).read_text());t=json.loads((R/(label+'.time.json')).read_text())
    rejected=label=='cap650-production'
    if rejected:assert t['returncode']==2 and 'retained-storage cap' in d['error'],d['error']
    else:assert t['returncode']==0 and d['error'] is None and d['metadata']['quality_gate']['passed'],(label,d['error'])
    h=d['hooks'];calls=h['inverse_calls']
    row=dict(case=label,error=d['error'],wall_seconds=d['wall_seconds'],peak_gib=d['peak_gib'],builds=h['builds'],
        condition_corrections=sum(x['corrections'] for x in calls if x['phase']=='condition_probe'),
        field_corrections=sum(x['corrections'] for x in calls if x['phase']=='field_solve'),
        field_seconds=sum(x['seconds'] for x in calls if x['phase']=='field_solve'),audit=h['audit'])
    if not rejected and spec['method']=='compressed':
        f=d['factors'][-1];row['inverse_bytes']=f['preconditioners'][-1]['bytes'];row['operator_bytes']=f['compressed']['retained_bytes']
        a=arrays(label)
        for key in a:assert a[key].shape==reference[key].shape and np.isfinite(a[key]).all()
        density=float(np.max(np.linalg.norm(a['density']-reference['density'],axis=0)/np.linalg.norm(reference['density'],axis=0)))
        field=float(np.max(abs(a['field']-reference['field']))/np.max(abs(reference['field'])))
        rhs=float(np.linalg.norm(a['rhs']-reference['rhs'])/np.linalg.norm(reference['rhs']))
        assert density<1e-7 and field<1e-8 and rhs<5e-15
        comparisons.append(dict(case=label,reference='dense-fresh',density_relative=density,field_peak_normalized=field,rhs_relative=rhs))
    rows.append(row)
matched=[]
for label in ('audit-direct','audit-sequential-direct','audit-direct-priced'):
    a,b=arrays(label),arrays('audit-original');equal={key:bool(a[key].dtype==b[key].dtype and a[key].shape==b[key].shape and a[key].tobytes()==b[key].tobytes()) for key in a};assert all(equal.values())
    matched.append(dict(case=label,reference='audit-original',equal=equal))
production=[x['wall_seconds'] for x in rows if x['case'].startswith('cap690-production')]
sequential=[x['wall_seconds'] for x in rows if x['case'].startswith('cap690-sequential')]
timing=dict(production_seconds=production,sequential_seconds=sequential,
    median_reduction_fraction=1-statistics.median(sequential)/statistics.median(production),
    both_sequential_faster_than_both_production=max(sequential)<min(production))
out=dict(evidence='Saved arrays and recorded diagnostics from fresh runs; analysis does not reevaluate equations.',rows=rows,comparisons=comparisons,matched=matched,timing=timing)
Path(os.environ.get('ANALYSIS_OUT',P/'analysis.json')).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
