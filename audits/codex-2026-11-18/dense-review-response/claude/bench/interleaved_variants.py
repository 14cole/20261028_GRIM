"""Reviewer microbenchmark: candidate residual formulations in the solver's sequence (LU solve / residual / LU solve / residual)."""
import os,sys,time,json,numpy as np,scipy.linalg as la
from scipy.linalg.blas import zgemm
r=np.random.default_rng(3);n=int(sys.argv[1]);w=int(sys.argv[3]) if len(sys.argv)>3 else 16
a=np.asfortranarray(r.standard_normal((n,n))+1j*r.standard_normal((n,n))+n*np.eye(n));lu=la.lu_factor(a)
B=[np.ascontiguousarray(r.standard_normal((n,w))+1j*r.standard_normal((n,w))) for _ in range(12)]
def old(x,b):return a@x-b
def new(x,b):
    res=np.empty(x.shape,np.complex128,order='F');np.matmul(a,x,out=res);res-=b;return res
def blas(x,b):
    res=zgemm(1.,a,x);res-=b;return res
def blas_beta(x,b):
    return zgemm(1.,a,x,beta=-1.,c=np.asfortranarray(b),overwrite_c=False)
def transposed(x,b):
    res=(x.T@a.T).T;res=res-b;return res
V=dict(old=old,new=new,blas=blas,blas_beta=blas_beta,transposed=transposed)
def sweep(f):
    tp=[];t_all=time.perf_counter()
    for b in B:
        x=la.lu_solve(lu,b,check_finite=False);t=time.perf_counter();res=f(x,b);tp.append(time.perf_counter()-t)
        c=x+la.lu_solve(lu,-res,check_finite=False);t=time.perf_counter();res=f(c,b);tp.append(time.perf_counter()-t)
    return time.perf_counter()-t_all,float(np.median(tp))
x0=la.lu_solve(lu,B[0]);ref=old(x0,B[0]);same={k:bool(np.array_equal(f(x0,B[0]),ref)) for k,f in V.items()};rel={k:float(np.max(abs(f(x0,B[0])-ref))/np.max(abs(a@x0))) for k,f in V.items()}
for f in V.values():sweep(f)
R={k:[] for k in V};names=list(V)
for rep in range(6):
    for k in (names if rep%2==0 else names[::-1]):R[k].append(sweep(V[k]))
out={k:dict(total_median=float(np.median([t for t,_ in v])),product_median_ms=float(np.median([p for _,p in v])*1e3),bitwise_equal_old=same[k],rel_diff=rel[k]) for k,v in R.items()}
print('threads',os.environ.get('OPENBLAS_NUM_THREADS'),'n',n,'w',w,{k:(round(v['total_median'],2),round(v['product_median_ms'],1),v['bitwise_equal_old']) for k,v in out.items()});json.dump(out,open(sys.argv[2],'w'),indent=1)
