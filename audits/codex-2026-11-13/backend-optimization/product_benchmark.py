import os,sys,time,json,resource
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_CANDIDATE_ROOT','/workspace/backend-optimization-study/candidate')+'/tools/GHOST')
from ghost_backend.linalg.products import adjoint_product
spec=json.loads(sys.argv[1]);m,n=spec.get('shape',[256,8192]);width=spec.get('width',2)
rng=np.random.default_rng(932)
a=np.empty((m,n),complex);a.real=rng.normal(size=(m,n));a.imag=rng.normal(size=(m,n));b=rng.normal(size=(m,width))+1j*rng.normal(size=(m,width))
fn=(lambda:a.conj().T@b) if spec['mode']=='baseline' else (lambda:adjoint_product(a,b))
# Input construction high water is below a full extra complex factor copy.
times=[]
for i in range(12):
 t=time.perf_counter();y=fn();times.append(time.perf_counter()-t)
np.savez_compressed(spec['out']+'.npz',product=y)
print(json.dumps(dict(spec,median_seconds=float(np.median(times[2:])),times=times,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)))
