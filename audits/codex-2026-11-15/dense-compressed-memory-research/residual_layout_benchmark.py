"""Paired persistent C/F coefficient layouts; copies are outside product timing.
This has both layouts resident and is a speed experiment, not a RAM measurement.
"""
import os,sys,json,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import mesh_for,dielectric,SimpleNamespace,CPUState,_STATE,cpu_allocation_scope,execution_scope
n=4096;k=80;eps=3-.08j;mesh=mesh_for(n,'star')
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
state=CPUState(kernel_only=True)
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):f=dielectric.assemble_system(mesh,[info],'TE',k)
t=time.perf_counter();c=np.array(f,order='C',copy=True);copy_seconds=time.perf_counter()-t
assert f.flags.f_contiguous and c.flags.c_contiguous
with np.load(HERE/'results/star-8192-180-dense-full-batch0000.npz') as z:x=z['density']
records=[]
for threads in (1,4):
    with threadpool_limits(threads):
        for width in (16,180):
            xx=x[:,:width];ref=f@xx
            for repeat in range(4):
                modes=('F_full','C_full','C_block64') if repeat%2==0 else ('C_block64','C_full','F_full')
                for mode in modes:
                    t=time.perf_counter()
                    if mode=='F_full':y=f@xx
                    elif mode=='C_full':y=c@xx
                    else:
                        y=np.empty_like(ref)
                        for start in range(0,len(c),64):y[start:start+64]=c[start:start+64]@xx
                    seconds=time.perf_counter()-t
                    error=float(np.linalg.norm(y-ref)/np.linalg.norm(ref));assert error<1e-13
                    records.append(dict(threads=threads,rhs=width,repeat=repeat,mode=mode,seconds=seconds,error=error))
            print('Completed',threads,width,flush=True)
(HERE/'residual-layout-benchmark.json').write_text(json.dumps(dict(matrix_shape=list(f.shape),copy_seconds=copy_seconds,records=records),indent=2))
