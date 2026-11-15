"""Saved-array comparisons and recorded gate/call inspection; no new equations."""
import json,os
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;R=Path(os.environ.get('RESULTS_DIR',P/'results'))
specs=dict(json.loads((P/'suite.json').read_text())+json.loads((P/'suite_reference.json').read_text()))
def arrays(label):
    with np.load(R/(label+'-solve0000.npz')) as z:d={k:z[k] for k in z.files}
    with np.load(R/(label+'-fields.npz')) as z:d['field']=z['field']
    return d
summary=[];comparisons=[]
for label,spec in specs.items():
    d=json.loads((R/(label+'.json')).read_text());t=json.loads((R/(label+'.time.json')).read_text())
    assert t['returncode']==0 and d['error'] is None and d['metadata']['quality_gate']['passed'],(label,d['error'])
    assert len(d['captures'])==1 and d['captures'][0]['shape'][1]==180
    h=d['hooks'];checks=h['live_correction_checks'];calls=h['refinement_calls'];conversions=h.get('conversions',[])
    row=dict(case=label,unknowns=d['captures'][0]['shape'][0],peak_gib=d['peak_gib'],wall_seconds=d['wall_seconds'],
        condition=d['metadata']['condition_est_max'],builds=h['builds'],
        accounted_high_water=h['accounting']['high_water_with_check_bytes'],
        uncharged_correction_checks=sum(not x['explicitly_charged'] for x in checks),
        largest_uncharged_correction=max([x['bytes'] for x in checks if not x['explicitly_charged']]+[0]),
        double_fallback_arrays=sum(not x['accepted'] for x in conversions),
        refinement_calls=calls)
    if spec['hook']=='corrected_builder':assert row['uncharged_correction_checks']==0
    if spec['method']=='compressed':
        f=d['factors'][-1]
        row.update(inverse_bytes=f['preconditioners'][-1]['bytes'],operator_bytes=f['compressed']['retained_bytes'],
            initial_tolerance=f['initial_preconditioner_tolerance'],refinement_total=f['refinement_steps'],
            max_refinements=f['max_refinements'],gmres_columns=f['gmres_columns'],
            condition_refinements=sum(x['steps'] for x in calls if x['phase']=='condition_probe'),
            field_refinements=sum(x['steps'] for x in calls if x['phase']=='field_solve'))
        assert sum(x['steps'] for x in calls)==row['refinement_total']
        reference='partialTM-dense-thread4' if spec['material']=='partial' else 'multilayerTM-dense-fresh'
        a,b=arrays(label),arrays(reference)
        for key in a:assert a[key].shape==b[key].shape and np.isfinite(a[key]).all() and np.isfinite(b[key]).all()
        density=float(np.max(np.linalg.norm(a['density']-b['density'],axis=0)/np.linalg.norm(b['density'],axis=0)))
        field=float(np.max(abs(a['field']-b['field']))/np.max(abs(b['field'])))
        rhs=float(np.linalg.norm(a['rhs']-b['rhs'])/np.linalg.norm(b['rhs']))
        assert density<1e-7 and field<1e-8 and rhs<5e-15,(label,density,field,rhs)
        comparisons.append(dict(case=label,reference=reference,density_relative=density,field_peak_normalized=field,rhs_relative=rhs))
    summary.append(row)
matched=[]
for label in ('corrected-cap640','rank-guard-cap640'):
    a,b=arrays(label),arrays('original-cap640')
    equal={key:bool(np.array_equal(a[key],b[key])) for key in a}
    matched.append(dict(case=label,reference='original-cap640',equal=equal))
    # Memory-accounting-only correction must preserve all numerical arrays.
    if label=='corrected-cap640':assert all(equal.values())
out=dict(evidence='Array replay of this round fresh solves, with recorded gate/counter observations.',summary=summary,comparisons=comparisons,matched=matched)
Path(os.environ.get('ANALYSIS_OUT',P/'analysis.json')).write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
