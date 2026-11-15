"""Independently reevaluate new coefficient rows for Claude's 32k/24 solution."""
import json,os,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT']]
from monostatic import mesh_for,dielectric,NativeOracle,SimpleNamespace,CPUState,_STATE,cpu_allocation_scope,execution_scope
from exact_validation import exact_rows
source=HERE/'claude/densities/d32k-24-right-v3-restart20-density.npz'
with np.load(source) as z:a={k:z[k] for k in z.files}
n=16384;k=320;eps=complex(3,-.08);mesh=mesh_for(n,'star')
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
available=np.setdiff1d(np.arange(2*n),a['rows'])
sample=np.sort(np.random.default_rng(2026111517).choice(available,16,replace=False))
state=CPUState(kernel_only=True)
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
    coeff,query=exact_rows(oracle,sample,2*n)
    rhs=dielectric.rhs_many(mesh,k,a['angles'])
residual=coeff@a['density']-rhs[sample]
norms=np.sum(abs(coeff),axis=1)
errors=np.max(abs(residual)/(norms[:,None]*np.max(abs(a['density']),axis=0)+abs(rhs[sample])),axis=0)
assert np.isfinite(errors).all() and max(errors)<1e-12
rhs_error=float(np.max(abs(rhs[a['rows']]-a['rhs_rows']))/np.max(abs(a['rhs_rows'])))
assert rhs_error<5e-15
np.savez_compressed(HERE/'fresh-row-evidence.npz',angles=a['angles'],rows=sample,residual=residual,row_norm=norms,rhs_rows=rhs[sample])
record=dict(source=str(source.name),new_rows=sample.tolist(),no_overlap_with_published_rows=True,unknowns=2*n,angles=len(a['angles']),max_exact_row_backward_error=float(max(errors)),regenerated_published_rhs_rows_relative_error=rhs_error,query=query,scope='new coefficient checks of a supplied solution; not a fresh 32k solve')
(HERE/'fresh-row-check.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
