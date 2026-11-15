"""Independent checks of Claude's committed arrays, work counts and block solver."""
import json,sys,os
from pathlib import Path
import numpy as np
from scipy.linalg import solve
HERE=Path(__file__).resolve().parent
AUDIT=Path(os.environ['MONOSTATIC_AUDIT'])
sys.path[:0]=[str(HERE/'claude'),str(AUDIT)]
from block_gmres_right import solve as right
z=np.load(HERE/'claude/fields_and_row_checks.npz')
records={p.stem:json.loads(p.read_text()) for p in (HERE/'claude/results').glob('*.json')}
fields=[];counts=[]
for name,r in records.items():
    ref='c32k-compressed-180' if name.startswith('c32k') else 'c8k-compressed-r1'
    assert np.array_equal(z['angles/'+name],z['angles/'+ref])
    f=z[name+'/field'];f0=z[ref+'/field']
    e=float(np.max(abs(f-f0))/np.max(abs(f0)))
    assert e<1e-8
    for key in ('field','residual','row_norm'):assert np.isfinite(z[name+'/'+key]).all()
    blocks=r.get('block_krylov',[])
    assert all(b['max_scaled_relative_residual']<=1e-12 for b in blocks)
    first=[b['check_history'][0] for b in blocks if b.get('check_history')]
    fields.append(dict(case=name,peak_normalized_field_error=e))
    counts.append(dict(case=name,compute_seconds=r['compute_seconds'],peak_gib=r['peak_gib'],applications=sum(b['rhs_equivalent_matrix_applications'] for b in blocks),cycles=sum(b['cycles'] for b in blocks),first_checks=first))
base=np.load(AUDIT/'restored/results/star-8192-180-compressed.npz')
assert np.array_equal(z['c8k-compressed-r1/field'],base['field'])
tests=[]
for seed in (773,902,1102):
    rng=np.random.default_rng(seed);n=150
    a=.01*(rng.normal(size=(n,n))+1j*rng.normal(size=(n,n)))+np.diag(np.linspace(1,4,n))
    original=rng.normal(size=(n,7))+1j*rng.normal(size=(n,7))
    for zero in (False,True):
        b=np.column_stack((original,np.zeros(n))) if zero else original.copy()
        b[:,2]=b[:,1]
        for restart in (3,20):
            x,d=right(lambda v:a@v,lambda v:v/np.diag(a)[:,None],b,restart_blocks=restart)
            reference=solve(a,b);bn=np.linalg.norm(b,axis=0)
            residual=np.linalg.norm(a@x-b,axis=0)
            rel=np.divide(residual,bn,out=np.zeros_like(bn),where=bn!=0)
            assert np.max(rel)<=1e-12 and np.all(x[:,bn==0]==0)
            error=float(np.linalg.norm(x-reference)/np.linalg.norm(reference))
            assert error<1e-11
            tests.append(dict(seed=seed,zero_column=zero,restart=restart,error=error,**d))
    x,d=right(lambda v:a@v,lambda v:v,np.zeros((n,3),complex))
    assert np.all(x==0) and d['matrix_applications']==0
out=dict(fields=fields,counts=counts,small_tests=tests,all_zero_cases=3,compressed_8k_fields_bitwise_identical=True)
(HERE/'review-checks.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(field_cases=len(fields),max_field_error=max(x['peak_normalized_field_error'] for x in fields),small_tests=len(tests),all_zero_cases=3,zero_comparison=[{k:t[k] for k in ('seed','zero_column','restart','steps','rhs_equivalent_matrix_applications')} for t in tests if t['restart']==20]),indent=2))

# Replay the original duplicate/zero test verbatim, preserving its diagnostics.
import contextlib,io
source=(AUDIT/'check_block.py').read_text().replace('from block_gmres import solve as block','from block_gmres_right import solve as block')
captured=io.StringIO()
with contextlib.redirect_stdout(captured):exec(compile(source,'original_duplicate_zero_check','exec'),{})
(HERE/'original-check-replay.json').write_text(captured.getvalue())
