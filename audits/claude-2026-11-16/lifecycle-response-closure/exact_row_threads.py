"""Exact coefficient rows of the 8,192-unknown star at several assembly thread counts."""
import os,sys,json,hashlib
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,CPUState,_STATE,cpu_allocation_scope,execution_scope,exact_rows)
z=np.load(sys.argv[1]);n=4096;k=80.;eps=3-.08j;E={}
for T in (1,2,3,4):
    with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(T),execution_scope({'assembly_threads':T,'blas_threads':1}):
        mesh=mesh_for(n,'star');info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
        oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');E[T],info_=exact_rows(oracle,z['rows'],2*n)
        if T in (1,4):E[(T,'again')],_=exact_rows(oracle,z['rows'],2*n)
out={}
for key,e in E.items():
    d=abs(e-E[1]);nz=d>0
    out[str(key)]=dict(sha256=hashlib.sha256(e.tobytes()).hexdigest()[:16],bitwise_equal_t1=bool(np.array_equal(e,E[1])),entries_differing=int(nz.sum()),of=int(e.size),
        max_abs_diff=float(d.max()),max_rel_diff_entrywise=float((d[nz]/abs(E[1][nz])).max()) if nz.any() else 0.,max_abs_entry=float(abs(E[1]).max()),
        rows_affected=int(nz.any(axis=1).sum()),cols_affected=int(nz.any(axis=0).sum()),first_cols=np.flatnonzero(nz.any(axis=0))[:12].tolist(),
        row_abs_sum_bitwise_equal=bool(np.array_equal(abs(e).sum(axis=1),abs(E[1]).sum(axis=1))))
print(json.dumps(out,indent=1));json.dump(out,open(sys.argv[2],'w'),indent=1)
