"""Validate lifecycle transitions, safety fallbacks and complete native solutions."""
import os,json,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;D=Path(os.environ.get('RESULTS_DIR',str(R/'results')))
def load(case,label):
    with np.load(D/(case+'-'+label+'.npz')) as z:return {k:z[k] for k in z.files}
def compare(x,y):
    assert x.shape==y.shape and x.dtype==y.dtype
    diff=x-y
    rel=float(np.max(np.linalg.norm(diff,axis=0)/np.maximum(np.linalg.norm(y,axis=0),1e-300))) if x.ndim==2 else float(np.linalg.norm(diff)/max(np.linalg.norm(y),1e-300))
    return dict(bit_identical=x.tobytes()==y.tobytes(),relative_error=rel,peak_normalized_error=float(np.max(abs(diff))/max(np.max(abs(y)),1e-300)))
dense={n:load('dense-reference','dense'+str(n)) for n in (16,180)}
records=[];bycase={};solutions=0
for case,spec in json.loads((R/'suite_lifecycle.json').read_text()):
    timing=json.loads((D/(case+'.time.json')).read_text());raw=json.loads((D/(case+'.json')).read_text())
    assert timing['returncode']==0 and not raw.get('error'),(case,raw.get('error'))
    assert raw['pending_after']==0 and not raw['workers_after']
    entries={}
    for entry in raw['solves']:
        a=load(case,entry['label']);n=entry['count'];ref=dense[n]
        assert np.isfinite(a['density']).all() and np.isfinite(a['field']).all()
        errs={k:compare(a[k],ref[k]) for k in ('density','rhs','field')}
        assert errs['rhs']['bit_identical'] and errs['density']['relative_error']<1e-7 and errs['field']['peak_normalized_error']<1e-7
        den=a['row_norm'][:,None]*np.max(abs(a['density']),axis=0)+abs(a['rhs'][a['rows']])
        back=np.max(abs(a['residual'])/den,axis=0);assert np.max(back)<1e-12
        entries[entry['label']]=dict(corrections=entry['corrections'],tolerance=entry['tolerance'],inverse_bytes=entry['inverse_bytes'],
            versus_dense=errs,max_exact_backward_error=float(np.max(back)),hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in a.items()})
        solutions+=1
    if spec['scenario'] in ('lifecycle','cancel','tighten'):
        fixed=spec['variant']=='fixed'
        assert entries['rebuilt_stable']['corrections']==(2 if fixed else 8)
        assert entries['rebuilt_stable']['tolerance']==(1e-10 if fixed else 1e-8)
        restored=load(case,'rebuilt_stable');fresh=load(case,'new_factor_same_operator')
        same={k:compare(restored[k],fresh[k]) for k in ('density','rhs','field')}
        assert all(v['bit_identical'] for v in same.values()) if fixed else not same['density']['bit_identical']
        raw['recovery_vs_fresh_factor']=same
        if spec['scenario']!='tighten':
            initial=load(case,'initial');assert compare(fresh['density'],initial['density'])['bit_identical']
    if spec['scenario']=='hint_failure':
        assert raw['build_tolerances']==[1e-10,1e-8]
        assert all(e['tolerance']==1e-8 and e['corrections']==8 for e in entries.values())
    if spec.get('condition'):
        assert np.isfinite(raw['final_diagnostics']['condition_est'])
    if spec['scenario']=='cancel':
        c=raw['cancel_cleanup'];assert c['factor_is_none'] and c['attempt_still_consumed'] and c['pending_bytes']==0 and c['live_failed_inverses']==0 and not c['workers'] and c['executor_reset']
    bycase[case]=dict(spec=spec,solves=entries,recovery_vs_fresh_factor=raw.get('recovery_vs_fresh_factor'),cancel_cleanup=raw.get('cancel_cleanup'),faults=raw['faults'],build_tolerances=raw['build_tolerances'])
for label in ('fallback1','fallback2'):
    a=load('original-hint_failure',label);b=load('fixed-hint_failure',label)
    assert all(compare(a[k],b[k])['bit_identical'] for k in ('density','rhs','field'))
out=dict(cases=bycase,completed_solutions=solutions,all_cases_pass=True,
    max_density_error_vs_dense=max(s['versus_dense']['density']['relative_error'] for c in bycase.values() for s in c['solves'].values()),
    max_field_error_vs_dense=max(s['versus_dense']['field']['peak_normalized_error'] for c in bycase.values() for s in c['solves'].values()),
    max_exact_backward_error=max(s['max_exact_backward_error'] for c in bycase.values() for s in c['solves'].values()),
    scope='Fresh native slot systems; controlled faults select production branches; shared formulation, not mesh convergence.')
Path(os.environ.get('ANALYSIS_OUT',str(R/'analysis.json'))).write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='cases'},indent=2))
