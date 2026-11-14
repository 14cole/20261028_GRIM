"""Recheck disjoint exact rows from saved 65k solutions; no FMM matvec used."""
import os,sys,json,time
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST');sys.path.insert(0,'fmm')
from ghost_backend.compressed.coefficients import NativeOracle
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from fmm_galerkin import circle_mesh
from exact_validation import validate_rows
from types import SimpleNamespace
start=time.perf_counter();r=json.loads(Path('results/fmm-65536.json').read_text());data=np.load('results/fmm-65536.npz');n=r['n'];k=r['k'];eps=complex(*r.get('eps',[3.,-.08]))
mesh=circle_mesh(n,star=r.get('star',True),inward=True)
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
eligible=np.setdiff1d(np.arange(2*n),data['rows']);rows=np.sort(np.random.default_rng(139570).choice(eligible,64,replace=False))
state=CPUState(kernel_only=True);state.reuse_operators=False
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 oracle=NativeOracle(mesh,[info],r.get('pol','TE'),k,'dielectric')
 errors,residual,norms,metadata=validate_rows(oracle,rows,2*n,data['density'],data['rhs'])
assert np.all(np.isfinite(errors)) and max(errors)<1e-12
np.savez_compressed('results/extra-65536-rows.npz',rows=rows,residual=residual,row_norm=norms)
Path('results/extra-65536-rows.json').write_text(json.dumps(dict(disjoint_rows=64,seed=139570,errors=errors.tolist(),validation_queries=metadata,seconds=time.perf_counter()-start),indent=2))
