"""Why does the saved four-thread star residual differ? Recompute exact rows and the product
exact @ density from the published control, under a chosen thread setting.
argv: control.npz, residuals npz, allocation threads, out json. BLAS threads come from the environment."""
import os,sys,json,hashlib
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,CPUState,_STATE,cpu_allocation_scope,execution_scope,exact_rows)
def h(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
z=np.load(sys.argv[1]);saved=np.load(sys.argv[2]);T=int(sys.argv[3]);n=4096;k=80.;eps=3-.08j
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(T),execution_scope({'assembly_threads':T,'blas_threads':1}):
    mesh=mesh_for(n,'star');info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');exact,_=exact_rows(oracle,z['rows'],2*n)
    inside=exact@z['density']-z['rhs'][z['rows']]
outside=exact@z['density']-z['rhs'][z['rows']]
out=dict(allocation_threads=T,env_openblas=os.environ.get('OPENBLAS_NUM_THREADS'),exact_sha256=h(exact),row_norm_matches=bool(np.array_equal(np.sum(abs(exact),axis=1),z['row_norm'])),
    inside_scope=dict(equals_saved_t1=bool(np.array_equal(inside,saved['residual_t1'])),equals_saved_t4=bool(np.array_equal(inside,saved['residual_t4']))),
    outside_scope=dict(equals_saved_t1=bool(np.array_equal(outside,saved['residual_t1'])),equals_saved_t4=bool(np.array_equal(outside,saved['residual_t4']))))
try:
    from threadpoolctl import threadpool_info;out['blas_pools']=[(p.get('internal_api'),p.get('num_threads')) for p in threadpool_info()]
except Exception as e:out['blas_pools']='threadpoolctl unavailable'
print(json.dumps(out));json.dump(out,open(sys.argv[4],'w'),indent=1)
