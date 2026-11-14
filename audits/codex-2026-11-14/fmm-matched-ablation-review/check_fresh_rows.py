"""Evaluate new exact Galerkin rows on the three published 65k solutions."""
import json,os,sys,time
from pathlib import Path
import numpy as np
checkout=Path(os.environ['GRIM_ROOT']);audit=checkout/'audits/codex-2026-11-13/fmm-scale-validation'
# GRIM_AUDIT supports a local source-equivalent audit folder without a full checkout.
if 'GRIM_AUDIT' in os.environ:audit=Path(os.environ['GRIM_AUDIT'])
sys.path[:0]=[str(checkout/'tools/GHOST'),str(audit),str(audit/'fmm')]
from ghost_backend.compressed.coefficients import NativeOracle
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from fmm_galerkin import circle_mesh
from exact_validation import validate_rows
from types import SimpleNamespace
root=Path('source/audits/claude-2026-11-14');new=root/'fmm-scale-response-review/results';old=root/'fmm-scale-validation-review/results'
names=['cap-only-65536','combined-65536','mixed-65536'];data=[]
for name in names:
 with np.load(new/(name+'.npz')) as a:data.append({key:a[key].copy() for key in a.files})
with np.load(old/'fmm-65536.npz') as d:excluded=np.union1d(d['rows'],data[2]['rows'])
nd=data[0]['density'].shape[0];assert nd==65536
for d in data[1:]:
 for k in ['rhs','angles','observation']:assert np.array_equal(d[k],data[0][k]),k
rows=np.sort(np.random.default_rng(2026111403).choice(np.setdiff1d(np.arange(nd),excluded),64,replace=False))
assert not np.intersect1d(rows,excluded).size
x=np.column_stack([d['density'] for d in data]);rhs=np.column_stack([d['rhs'] for d in data])
spec=json.loads((new/'mixed-65536.json').read_text());assert spec['n']==nd//2 and spec['k']==640
k=spec['k'];eps=complex(*spec.get('eps',[3.,-.08]));pol=spec.get('pol','TE')
mesh=circle_mesh(nd//2,star=spec.get('star',True),inward=True)
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
state=CPUState(kernel_only=True);state.reuse_operators=False;started=time.perf_counter()
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 oracle=NativeOracle(mesh,[info],pol,k,'dielectric')
 errors,residual,norms,metadata=validate_rows(oracle,rows,nd,x,rhs)
assert np.all(np.isfinite(errors)) and max(errors)<1e-12
np.savez_compressed('results/fresh-exact-rows.npz',rows=rows,excluded_rows=excluded,residual=residual,row_norm=norms)
result=dict(unknowns=nd,rows_checked=64,seed=2026111403,excluded_saved_row_count=len(excluded),queries=metadata,errors={name:errors[2*i:2*i+2].tolist() for i,name in enumerate(names)},seconds=time.perf_counter()-started,validation='New direct Galerkin coefficient rows, not FMM matvecs; sampled validation, not mesh/condition certification')
Path('results/fresh-exact-rows.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
