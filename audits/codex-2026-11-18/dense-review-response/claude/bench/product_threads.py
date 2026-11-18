"""Reviewer microbenchmark of the exact old and new residual expressions (product and subtraction), alternating order."""
import os,sys,time,json,numpy as np
r=np.random.default_rng(2);out={}
for n in (4146,4096,8192):
    a=np.asfortranarray(r.standard_normal((n,n))+1j*r.standard_normal((n,n)))
    for w in (16,4,10):
        x=np.asfortranarray(r.standard_normal((n,w))+1j*r.standard_normal((n,w)));b=np.asfortranarray(r.standard_normal((n,w))+1j*r.standard_normal((n,w)))
        def old():return a@x-b
        def new():
            res=np.empty(x.shape,np.complex128,order='F');np.matmul(a,x,out=res);res-=b;return res
        old();new();T={'old':[],'new':[]}
        for rep in range(21):
            for name,f in ((('old',old),('new',new)) if rep%2==0 else (('new',new),('old',old))):
                t=time.perf_counter();f();T[name].append(time.perf_counter()-t)
        out[f'{n}|{w}']={k:dict(median=float(np.median(v)),q25=float(np.quantile(v,.25)),q75=float(np.quantile(v,.75))) for k,v in T.items()}
        print(os.environ.get('OPENBLAS_NUM_THREADS'),n,w,'old %.1f ms new %.1f ms ratio %.2f'%(out[f'{n}|{w}']['old']['median']*1e3,out[f'{n}|{w}']['new']['median']*1e3,out[f'{n}|{w}']['new']['median']/out[f'{n}|{w}']['old']['median']),flush=True)
json.dump(out,open(sys.argv[1],'w'),indent=1)
