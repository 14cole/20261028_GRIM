"""Reassemble 128 different exact coefficient rows after the capped solves."""
import os,sys,json,time
from pathlib import Path
import numpy as np
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
from monostatic import mesh_for,NativeOracle,exact_rows
from types import SimpleNamespace
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
ROOT=Path(__file__).resolve().parent
n=16384;nd=2*n;k=320.;eps=complex(3.,-.08)
mesh=mesh_for(n,'star')
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
with np.load(ROOT/'results/reference-uncapped-batch0000.npz') as z:old=z['rows']
choices=np.setdiff1d(np.arange(nd),old)
rows=np.sort(np.random.default_rng(2026111602).choice(choices,128,replace=False))
t=time.perf_counter()
with cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    exact,query=exact_rows(oracle,rows,nd)
    norms=np.sum(abs(exact),axis=1);cases=[]
    for label in ('cap2900-production','cap2900-sequential','reference-uncapped'):
        p=ROOT/'results'/(label+'-batch0000.npz')
        if not p.exists():continue
        with np.load(p) as z:x=z['density'];b=z['rhs'];angles=z['angles']
        residual=exact@x-b[rows]
        backward=np.max(abs(residual)/(norms[:,None]*np.max(abs(x),axis=0)+abs(b[rows])),axis=0)
        assert np.isfinite(backward).all() and len(backward)==180 and np.max(backward)<1e-12
        np.savez_compressed(ROOT/'results'/(label+'-independent-rows.npz'),rows=rows,row_norm=norms,residual=residual,backward_error=backward,angles=angles)
        cases.append(dict(label=label,max_backward_error=float(np.max(backward)),angles=len(angles)))
        del x,b,residual
d=dict(seed=2026111602,rows=rows.tolist(),disjoint_from_prior_rows=True,prior_row_count=len(old),
       query=query,cases=cases,seconds=time.perf_counter()-t,scope='Fresh exact coefficients, shared native formulation; sampled equations, not mesh certification.')
(ROOT/'fresh-exact-rows.json').write_text(json.dumps(d,indent=2));print(json.dumps(d,indent=2))
