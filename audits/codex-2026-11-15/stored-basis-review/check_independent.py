"""Independent fixed-matrix tests of finite-precision preconditioner composition."""
import os,sys,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'claude'),os.environ['MONOSTATIC_AUDIT']]
import block_gmres_right as v3,block_gmres_right_z as stored
records=[]
for seed in (514,717,919):
    rng=np.random.default_rng(seed);n=96
    noise=lambda: (rng.normal(size=(n,n))+1j*rng.normal(size=(n,n)))/np.sqrt(n)
    a=np.eye(n)+.2*noise();p=np.linalg.inv(a+.06*noise())
    b=rng.normal(size=(n,6))+1j*rng.normal(size=(n,6));b[:,2]=b[:,1];b[:,4]=0
    reference=np.linalg.solve(a,b);bn=np.linalg.norm(b,axis=0)
    for dtype in (np.complex128,np.complex64):
        pp=p.astype(dtype)
        def pre(x):return (pp@x.astype(dtype)).astype(np.complex128)
        for name,module in (('v3',v3),('stored_z',stored)):
            x,d=module.solve(lambda x:a@x,pre,b,restart_blocks=20)
            r=np.linalg.norm(b-a@x,axis=0)
            rel=np.divide(r,bn,out=np.zeros_like(r),where=bn!=0)
            error=float(np.linalg.norm(x-reference)/np.linalg.norm(reference))
            assert max(rel)<=1e-12 and error<1e-11 and np.all(x[:,4]==0)
            records.append(dict(seed=seed,preconditioner_arithmetic=np.dtype(dtype).name,solver=name,independent_true_residual=float(max(rel)),density_error=error,**d))
for module in (v3,stored):
    x,d=module.solve(lambda x:x,lambda x:x,np.zeros((16,4)))
    assert not x.any() and d['matrix_applications']==0
(HERE/'independent-checks.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps([dict(seed=x['seed'],dtype=x['preconditioner_arithmetic'],solver=x['solver'],cycles=x['cycles'],failed=x['failed_true_checks'],residual=x['independent_true_residual']) for x in records],indent=2))
