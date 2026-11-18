"""Reviewer microbenchmark: the two residual expressions timed in the sequence the solver uses
(LU solve, residual, LU solve of the residual, residual), not back to back."""
import os,sys,time,json,numpy as np,scipy.linalg as la
r=np.random.default_rng(3);n=int(sys.argv[1]);w=16;out={}
a=np.asfortranarray(r.standard_normal((n,n))+1j*r.standard_normal((n,n))+n*np.eye(n));lu=la.lu_factor(a)
B=[np.ascontiguousarray(r.standard_normal((n,w))+1j*r.standard_normal((n,w))) for _ in range(12)]
def old(x,b):return a@x-b
def new(x,b):
    res=np.empty(x.shape,np.complex128,order='F');np.matmul(a,x,out=res);res-=b;return res
def sweep(f):
    tp=[];tl=[];t_all=time.perf_counter()
    for b in B:
        t=time.perf_counter();x=la.lu_solve(lu,b,check_finite=False);tl.append(time.perf_counter()-t)
        t=time.perf_counter();res=f(x,b);tp.append(time.perf_counter()-t)
        t=time.perf_counter();c=x+la.lu_solve(lu,-res,check_finite=False);tl.append(time.perf_counter()-t)
        t=time.perf_counter();res=f(c,b);tp.append(time.perf_counter()-t)
    return time.perf_counter()-t_all,float(np.median(tp)),float(np.sum(tp)),float(np.sum(tl))
sweep(old);sweep(new);R={'old':[],'new':[]}
for rep in range(8):
    for name,f in ((('old',old),('new',new)) if rep%2==0 else (('new',new),('old',old))):R[name].append(sweep(f))
for name,v in R.items():
    v=np.array(v);out[name]=dict(total_median=float(np.median(v[:,0])),product_median_ms=float(np.median(v[:,1])*1e3),product_sum_median=float(np.median(v[:,2])),lu_sum_median=float(np.median(v[:,3])))
print(os.environ.get('OPENBLAS_NUM_THREADS'),n,json.dumps(out));json.dump(out,open(sys.argv[2],'w'),indent=1)
