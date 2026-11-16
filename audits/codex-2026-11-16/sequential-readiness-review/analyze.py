"""Validate full fresh solutions and recovery invariants; no performance claim."""
import os,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;RESULTS=Path(os.environ.get('RESULTS_DIR',str(ROOT/'results')))
sha=lambda x:hashlib.sha256(x.tobytes()).hexdigest()
def read(label):
    with np.load(RESULTS/(label+'-batch0000.npz')) as z:return {k:z[k] for k in z.files}
def compare(a,b):
    assert a.shape==b.shape and a.dtype==b.dtype
    diff=a-b
    relative=max(float(np.linalg.norm(diff[:,j])/max(np.linalg.norm(b[:,j]),1e-300)) for j in range(a.shape[1])) if a.ndim==2 else float(np.linalg.norm(diff)/max(np.linalg.norm(b),1e-300))
    return dict(bit_identical=a.tobytes()==b.tobytes(),max_column_relative_error=relative,
        peak_normalized_error=float(np.max(abs(diff))/max(np.max(abs(b)),1e-300)))
dense=read('dense');base=read('production-threads1');records=[]
for label,spec in json.loads((ROOT/'suite_readiness.json').read_text()):
    timing=json.loads((RESULTS/(label+'.time.json')).read_text());raw=json.loads((RESULTS/(label+'.json')).read_text())
    assert timing['returncode']==0 and not raw.get('error'),(label,raw.get('error'))
    values=read(label)
    for key in ('density','rhs','field','residual'):assert np.isfinite(values[key]).all()
    assert values['density'].shape==(4096,180)
    cd={k:compare(values[k],dense[k]) for k in ('density','rhs','field')}
    cb={k:compare(values[k],base[k]) for k in ('density','rhs','field')}
    assert cd['rhs']['bit_identical'] and max(cd[k]['max_column_relative_error'] for k in ('density','field'))<1e-8
    den=values['row_norm'][:,None]*np.max(abs(values['density']),axis=0)+abs(values['rhs'][values['rows']])
    backward=np.max(abs(values['residual'])/den,axis=0)
    assert len(backward)==180 and np.max(backward)<1e-12
    assert raw['pending_after_solve']==0 and raw['live_threads_after_solve']==[]
    if spec['method']=='compressed':
        assert all(cb[k]['bit_identical'] for k in ('density','rhs','field'))
        probes=[x for x in raw['inverse_calls'] if x['phase']=='condition_probe']
        assert {x['trans'] for x in probes}=={0,2}
        if spec['threads']==2:assert len(raw['worker_names'])>=2 and raw['worker_statistics']['max_active']>=2
    if spec.get('cancel'):
        c=raw['cancel_cleanup'];assert raw['active_tasks_when_cancel_observed']>=1;assert c['pending_bytes']==0 and c['live_threads']==[] and c['live_failed_inverse_objects']==0 and c['executor_context_reset'] and c['active_after']==0 and raw['recovered_after_cancel']
    records.append(dict(label=label,diagnostics=raw['diagnostics'],versus_dense=cd,versus_compressed_single_thread=cb,
        max_exact_row_backward_error=float(np.max(backward)),worker_names=raw['worker_names'],worker_statistics=raw['worker_statistics'],
        cancel_cleanup=raw.get('cancel_cleanup'),active_tasks_when_cancel_observed=raw.get('active_tasks_when_cancel_observed'),
        hashes={k:dict(shape=list(v.shape),dtype=v.dtype.str,sha256=sha(v)) for k,v in values.items()}))
out=dict(cases=records,all_seven_cases_pass=True,scope='Fresh 4096-unknown star with condition estimation, exact rows, 180 angles; no mesh certification or speed claim.')
Path(os.environ.get('ANALYSIS_OUT',str(ROOT/'analysis.json'))).write_text(json.dumps(out,indent=2));print(json.dumps([{k:x[k] for k in ('label','max_exact_row_backward_error','worker_names','cancel_cleanup','active_tasks_when_cancel_observed')} for x in records],indent=2))
