"""Paired residual products on a physical matrix; no accuracy gate removed."""
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
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):a=dielectric.assemble_system(mesh,[info],'TE',k)
with np.load(HERE/'results/star-8192-180-dense-full-batch0000.npz') as z:x=z['density'];b=z['rhs']
records=[]
for threads in (1,4):
    with threadpool_limits(threads):
        for width in (16,180):
            xx=x[:,:width];ref=a@xx
            for repeat in range(4):
                modes=('full','blocked','blocked_c') if repeat%2==0 else ('blocked_c','blocked','full')
                for mode in modes:
                    started=time.perf_counter()
                    if mode=='full':y=a@xx
                    else:
                        y=np.empty_like(ref)
                        for start in range(0,len(a),256):
                            block=a[start:start+256]
                            if mode=='blocked_c':block=np.ascontiguousarray(block)
                            y[start:start+256]=block@xx
                    elapsed=time.perf_counter()-started
                    error=float(np.linalg.norm(y-ref)/np.linalg.norm(ref));assert error<1e-13
                    records.append(dict(threads=threads,rhs=width,repeat=repeat,mode=mode,seconds=elapsed,relative_product_error=error))
(HERE/'residual-benchmark.json').write_text(json.dumps(dict(matrix_shape=list(a.shape),c_contiguous=a.flags.c_contiguous,f_contiguous=a.flags.f_contiguous,records=records),indent=2))
print(json.dumps(records))

# Local-file cold-read control. This is advisory eviction, not whole-machine RAM pressure.
from ghost_backend.linalg.residual_spool import ResidualSpool
def io_counts():
 return {k:int(v) for k,v in (line.split(':') for line in Path('/proc/self/io').read_text().splitlines())}
t=time.perf_counter();spool=ResidualSpool(a,'/tmp',lambda:None);os.fsync(spool.file.fileno());setup=time.perf_counter()-t
disk=[]
with threadpool_limits(1):
 for width in (16,180):
  ref=a@x[:,:width]
  for policy in ('cached','drop_advice','cached_again'):
   if policy=='drop_advice':os.posix_fadvise(spool.file.fileno(),0,0,os.POSIX_FADV_DONTNEED)
   before=io_counts();t=time.perf_counter();y=spool@x[:,:width];seconds=time.perf_counter()-t;after=io_counts()
   error=float(np.linalg.norm(y-ref)/np.linalg.norm(ref));assert error<1e-13
   disk.append(dict(rhs=width,policy=policy,seconds=seconds,error=error,io={k:after[k]-before[k] for k in before}))
spool.close()
(HERE/'disk-residual-benchmark.json').write_text(json.dumps(dict(spool_bytes=a.nbytes,setup_and_fsync_seconds=setup,records=disk),indent=2))
