"""Test whether far-quadrature grading accounts for the tile-policy dependence."""
import os,sys,json,hashlib
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import mesh_for,SimpleNamespace,NativeOracle,CPUState,_STATE,cpu_allocation_scope,execution_scope,exact_rows
R=Path(__file__).resolve().parent;D=R/'results';z=np.load(R/'prior/star-control.npz')
if (D/'grading.json').exists():raise RuntimeError('Refusing overwrite')
mesh=mesh_for(4096,'star');k=80.;eps=3-.08j
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
matrices={};records=[];arrays={}
for threads in (1,4):
 with threadpool_limits(limits=1,user_api='blas'),_STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(threads),execution_scope({'assembly_threads':threads,'blas_threads':1,'far_grading':False}):
    e,_=exact_rows(NativeOracle(mesh,[info],'TE',k,'dielectric'),z['rows'],8192)
    residual=e@z['density']-z['rhs'][z['rows']];norm=np.sum(abs(e),axis=1)
 matrices[threads]=e;arrays['residual'+str(threads)]=residual;arrays['row_norm'+str(threads)]=norm
 records.append(dict(threads=threads,far_grading=False,exact_sha256=hashlib.sha256(e.tobytes()).hexdigest(),residual_sha256=hashlib.sha256(residual.tobytes()).hexdigest()))
changed=np.flatnonzero(matrices[1].ravel()!=matrices[4].ravel());a=matrices[1].ravel()[changed];b=matrices[4].ravel()[changed]
arrays.update(changed_flat_indices=changed,reference_values=a,values=b)
out=dict(cases=records,different_entries=len(changed),max_abs_difference=float(np.max(abs(b-a))) if len(changed) else 0.)
np.savez_compressed(D/'grading-evidence.npz',**arrays);(D/'grading.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
