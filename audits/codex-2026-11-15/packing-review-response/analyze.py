"""Replay complete saved solutions from the fresh serial suite; no new solves."""
import json,os
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
RESULTS=Path(os.environ.get('RESULTS_DIR',HERE/'results'))
records=[];comparisons=[]
def arrays(label):
    with np.load(RESULTS/(label+'-solve0000.npz')) as z:
        d={k:z[k] for k in z.files}
    with np.load(RESULTS/(label+'-fields.npz')) as z:d['field']=z['field']
    return d
for label,spec in json.loads((HERE/'suite.json').read_text()):
    d=json.loads((RESULTS/(label+'.json')).read_text())
    timing=json.loads((RESULTS/(label+'.time.json')).read_text())
    expected=('Unsafe research packing' if spec['packing']=='construction' else
        'retained-storage cap' if spec.get('storage_mib')==640 or
        (spec.get('storage_mib')==675 and spec['packing']=='none') else
        'condition' if label=='multilayerTE-bounded' else None)
    if expected:
        assert timing['returncode']!=0 and expected.lower() in d['error'].lower(),(label,d['error'])
    else:
        assert timing['returncode']==0 and d['error'] is None,(label,d['error'])
        assert d['metadata']['quality_gate']['passed']
        assert len(d['captures'])==1 and d['captures'][0]['shape'][1]==180
    conversions=d['hooks'].get('conversions',[])
    row=dict(case=label,error=d['error'],returncode=timing['returncode'],
        peak_gib=d['peak_gib'],wall_seconds=d['wall_seconds'],
        condition=d.get('metadata',{}).get('condition_est_max'),
        storage_rejections=d['hooks'].get('storage_rejections',[]),
        lost_components=sum(c['lost_components'] for c in conversions),
        max_lost_component=max([c['max_lost_component'] for c in conversions]+[0]),
        retained_double_arrays=sum(not c['accepted'] for c in conversions),
        max_conversion_relative_error=max([c['relative_max_component_error'] for c in conversions]+[0]))
    for f in d['factors']:
        if f.get('preconditioners'):
            row.update(unknowns=f['unknowns'],inverse_bytes=f['preconditioners'][-1]['bytes'],
                operator_bytes=f['compressed']['retained_bytes'],refinement_steps=f['refinement_steps'],
                max_backward_error=f['max_backward_error'],max_sampled_backward_error=f.get('max_sampled_backward_error'))
    records.append(row)
    if expected or spec['method']=='dense':continue
    ref=('partialTE' if spec['material']=='partial' else 'multilayerTM')+'-dense-none'
    a,b=arrays(label),arrays(ref)
    for key in a:
        assert a[key].shape==b[key].shape and np.isfinite(a[key]).all() and np.isfinite(b[key]).all()
    density=float(np.max(np.linalg.norm(a['density']-b['density'],axis=0)/np.linalg.norm(b['density'],axis=0)))
    field=float(np.max(abs(a['field']-b['field']))/np.max(abs(b['field'])))
    rhs=float(np.linalg.norm(a['rhs']-b['rhs'])/np.linalg.norm(b['rhs']))
    assert density<1e-7 and field<1e-8 and rhs<5e-15,(label,density,field,rhs)
    comparisons.append(dict(case=label,reference=ref,max_per_angle_density_relative_error=density,
        peak_normalized_field_error=field,rhs_relative_error=rhs))
out=dict(evidence='Saved-array comparisons of fresh solves; gate/rejection records inspected; no new equation evaluations.',
    records=records,comparisons=comparisons)
Path(os.environ.get('ANALYSIS_OUT',HERE/'analysis.json')).write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
