"""Full density/field comparisons; diagnose mechanism without using timing alone."""
import hashlib,json,os
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
AUDIT=Path(os.environ['MONOSTATIC_AUDIT'])
RESULTS=Path(os.environ.get('RESTART_RESULTS',str(HERE/'results')))
OUTPUT=Path(os.environ.get('RESTART_ANALYSIS',str(HERE/'analysis.json')))
def read(path):
    with np.load(path) as z:return {k:np.ascontiguousarray(z[k]) for k in z.files}
def compare(a,b):
    ids=[int(np.flatnonzero(b['angles']==x)[0]) for x in a['angles']]
    x=b['density'][:,ids];f=b['field'][ids]
    d=float(max(np.linalg.norm(a['density']-x,axis=0)/np.linalg.norm(x,axis=0)))
    e=float(np.max(abs(a['field']-f))/np.max(abs(f)))
    assert d<1e-7 and e<1e-8
    return dict(max_density_relative_l2=d,peak_normalized_field_error=e)
def backward(a):
    rhs=a.get('rhs_rows',a['rhs'][a['rows']] if 'rhs' in a else None)
    v=abs(a['residual'])/(a['row_norm'][:,None]*np.max(abs(a['density']),axis=0)+abs(rhs))
    assert np.isfinite(v).all() and v.max()<1e-12
    return float(v.max())
records=[];own={}
for label,spec in json.loads((HERE/'suite.json').read_text())+json.loads((HERE/'suite_extra.json').read_text()):
    timing=json.loads((RESULTS/(label+'.time.json')).read_text());assert timing['returncode']==0
    d=json.loads((RESULTS/(label+'.json')).read_text())
    f=RESULTS/(label+'.npz')
    if not f.exists():f=RESULTS/(label+'-batch0000.npz')
    a=read(f);assert all(np.isfinite(v).all() for v in a.values())
    geometry=spec.get('geometry','star');pol=spec.get('pol','TE')
    ref='star-8192-180-dense' if geometry=='star' else (f'{geometry}-1024-180-dense-cold' if pol=='TE' else 'slot-1024-180-TM-dense')
    b=read(AUDIT/'restored/results'/(ref+'.npz'))
    cmp=compare(a,b)
    ids=[int(np.flatnonzero(b['angles']==x)[0]) for x in a['angles']]
    rhs=float(max(np.linalg.norm(a['rhs']-b['rhs'][:,ids],axis=0)/np.linalg.norm(b['rhs'][:,ids],axis=0)))
    assert rhs<5e-15
    blocks=d.get('block_krylov',[]);true=max((x['max_scaled_relative_residual'] for x in blocks),default=None)
    assert true is None or true<=1e-12
    records.append(dict(label=label,method=spec['method'],reference=ref,**cmp,rhs_error=rhs,exact_row_backward_error=backward(a),max_true_relative_residual=true,compute_seconds=d['compute_seconds'],solve_seconds=d['solve_seconds'],peak_gib=d['peak_gib'],applications=sum(x['rhs_equivalent_matrix_applications'] for x in blocks),preconditioner_applications=sum(x['preconditioner_rhs_applications'] for x in blocks),cycles=sum(x['cycles'] for x in blocks),failed_checks=sum(x['failed_true_checks'] for x in blocks)))
    if label in ('star-8192-180-v3','star-8192-180-z'):own[label]=a
index=json.loads((HERE/'claude/array_index.json').read_text());claude=[]
for file,key in [('d8k-right-v3-a-density.npz','8k-fmm-right-v3 (d8k-right-v3-a)'),('d32k-24-right-v3-restart20-density.npz','32k-24-fmm-right-v3-restart20')]:
    a=read(HERE/'claude/densities'/file);meta=index[key]
    for k,v in a.items():
        if k in meta and isinstance(meta[k],dict) and 'sha256_c_order' in meta[k]:assert hashlib.sha256(v.tobytes()).hexdigest()==meta[k]['sha256_c_order'],(file,k)
    r=dict(file=file,exact_row_backward_error=backward(a))
    if file.startswith('d8k'):
        ref=read(AUDIT/'restored/results/star-8192-180-dense.npz');r.update(compare(a,ref))
        assert hashlib.sha256(ref['rhs'].tobytes()).hexdigest()==meta['rhs']['sha256_c_order']
        r['fresh_v3_comparison']=compare(own['star-8192-180-v3'],a)
        r['fresh_stored_z_comparison']=compare(own['star-8192-180-z'],a)
    claude.append(r)
diag=json.loads((RESULTS/'star-8192-8-diagnostic.json').read_text())['block_krylov'][0]
census=json.loads((RESULTS/'star-8192-8-diagnostic.inverse-arrays.json').read_text())
types={k:dict(arrays=sum(x['dtype']==k for x in census),bytes=sum(x['bytes'] for x in census if x['dtype']==k)) for k in sorted({x['dtype'] for x in census})}
out=dict(fresh_cases=records,claude_published_array_checks=claude,paired_solution_difference=compare(own['star-8192-180-z'],own['star-8192-180-v3']),diagnostic=diag['diagnostics'],diagnostic_check_history=diag['check_history'],inverse_array_types=types)
OUTPUT.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
