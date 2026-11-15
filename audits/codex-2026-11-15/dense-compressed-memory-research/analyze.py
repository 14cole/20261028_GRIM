"""Replay all preserved arrays; does not run a new solve or a fresh equation check."""
import os,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
RESULTS=Path(os.environ.get('RESULTS_DIR',HERE/'results'))
def read(label):return json.loads((RESULTS/(label+'.json')).read_text())
def arrays(label,kind):
    files=sorted(RESULTS.glob(label+'-'+kind+'*.npz'))
    assert files,(label,kind)
    if kind=='fields':
        with np.load(files[0]) as z:return {'field':z['field']}
    items=[]
    for f in files:
        with np.load(f) as z:items.append({k:z[k] for k in z.files})
    keys=('density','rhs') if kind=='solve' else ('density','rhs','field','angles')
    return {k:np.concatenate([a[k] for a in items],axis=1 if k in ('rhs','density') else 0) for k in keys}
def compare(label,ref,kind):
    a,b=arrays(label,kind),arrays(ref,kind)
    out={'case':label,'reference':ref,'evidence':'saved-array replay'}
    if 'angles' in a:assert np.array_equal(a['angles'],b['angles'])
    for k in a:
        assert a[k].shape==b[k].shape,(label,ref,k)
        assert np.isfinite(a[k]).all() and np.isfinite(b[k]).all()
    if 'density' in a:
        den=np.linalg.norm(b['density'],axis=0)
        err=np.linalg.norm(a['density']-b['density'],axis=0)/np.maximum(den,np.finfo(float).tiny)
        out['max_per_angle_density_relative_error']=float(np.max(err));assert out['max_per_angle_density_relative_error']<1e-7,out
        out['rhs_relative_error']=float(np.linalg.norm(a['rhs']-b['rhs'])/np.linalg.norm(b['rhs']))
        assert out['rhs_relative_error']<5e-15,out
    if 'field' in a:
        out['peak_normalized_field_error']=float(np.max(np.abs(a['field']-b['field']))/np.max(np.abs(b['field'])))
        assert out['peak_normalized_field_error']<1e-8,out
    return out

specs=[]
for suite in ('suite1','suite_adjoint','suite_geometry','suite_scale','suite_sweeps','suite_geometry_capture','suite_layout','suite_lifecycle','suite_output','suite_output_repeats'):
    specs+=json.loads((HERE/(suite+'.json')).read_text())
summary=[];comparisons=[];failures=[]
for label,spec in specs:
    timing=json.loads((RESULTS/(label+'.time.json')).read_text())
    if timing['returncode']:
        failures.append({'case':label,**timing});continue
    d=read(label)
    row={'case':label,'method':spec.get('method'),'packing':spec.get('packing'),'process_wall_seconds':timing['wall_seconds']}
    if 'stages' in d:
        row.update({k:d[k] for k in ('compute_seconds','solve_seconds','peak_gib','retained_factor_bytes')})
        row.update(unknowns=2*spec['n'],factor_peak_gib=d['stages']['factor']['peak_gib'],factor_seconds=d['stages']['factor']['seconds'],assembly_seconds=d['stages']['assembly']['seconds'],refinement_steps=d['event'].get('refinement_steps',0),factorizations=d['event']['factorizations'])
        row['sweep_compression']=d['event'].get('sweep_compression',{})
        row['fresh_exact_row_error_max']=max(b['max_exact_row_backward_error'] for b in d['batches'])
        assert row['fresh_exact_row_error_max']<1e-12,row
        if spec['n']==4096:ref='star-8192-180-dense-full'
        elif spec['n']==2048:ref='star-4096-360-dense-full-batch256'
        else:ref=f"star-{2*spec['n']}-180-compressed-none"
        if label!=ref:comparisons.append(compare(label,ref,'batch'))
    elif 'metadata' in d:
        m=d['metadata'];assert d['error'] is None and m['quality_gate']['passed']
        row.update(peak_gib=d['peak_gib'],wall_seconds=d['wall_seconds'],panels=m['panel_count'],unknowns=max([x.get('unknowns',0) for x in d['factors']]+[m.get('dense_largest_system',0)]),condition_est=m['condition_est_max'],quality_gate=m['quality_gate'],capture_count=len(d['captures']))
        name=label.removeprefix('capture-').removeprefix('layout-').removeprefix('output-')
        base=name.split('-dense-')[0].split('-compressed-')[0]
        ref=('capture-' if label.startswith(('capture-','layout-','output-')) else '')+base+'-dense-none'
        if label!=ref:
            comparisons.append(compare(label,ref,'fields'))
            if label.startswith(('capture-','layout-','output-')):comparisons.append(compare(label,ref,'solve'))
    elif 'checks' in d:
        row['checks']=d['checks']
        assert all(x['density_error']<1e-7 and x['exact_backward_error']<1e-12 for x in d['checks'])
    else:raise ValueError(label)
    summary.append(row)
out=dict(evidence='Saved-array replay of fresh solves, plus inspection of recorded fresh-check outcomes; no new equation evaluations in this script.',cases=len(specs),completed=len(summary),failures=failures,summary=summary,comparisons=comparisons)
target=Path(os.environ.get('ANALYSIS_OUT',HERE/'analysis.json'));target.write_text(json.dumps(out,indent=2))
print(json.dumps({'cases':len(specs),'completed':len(summary),'failures':failures,'comparisons':len(comparisons),'max_density_error':max(x.get('max_per_angle_density_relative_error',0) for x in comparisons),'max_field_error':max(x.get('peak_normalized_field_error',0) for x in comparisons)}))
