"""Reviewer controls for the two-BLAS-pool hypothesis. Pools are set and read back with GHOST's bundled controller.
argv: n, numpy_threads, scipy_threads, out.json"""
import os,sys,time,json
from pathlib import Path
import numpy as np,scipy.linalg as la
from scipy.linalg.blas import zgemm
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.execution.thread_control import _threadpoolctl as tpc
n,tn,ts=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]);w=16
ctrl=tpc.ThreadpoolController();libs={('numpy' if 'numpy.libs' in l.filepath else 'scipy'):l for l in ctrl.lib_controllers if l.internal_api=='openblas'}
assert set(libs)=={'numpy','scipy'},[l.filepath for l in ctrl.lib_controllers]
libs['numpy'].set_num_threads(tn);libs['scipy'].set_num_threads(ts)
def pools():return {k:int(l.num_threads) for k,l in libs.items()}
r=np.random.default_rng(3);a=np.asfortranarray(r.standard_normal((n,n))+1j*r.standard_normal((n,n))+n*np.eye(n));lu=la.lu_factor(a);ainv=np.asfortranarray(la.inv(a))
B=[np.asfortranarray(r.standard_normal((n,w))+1j*r.standard_normal((n,w))) for _ in range(10)]
solvers={'scipy_lu':lambda b:la.lu_solve(lu,b,check_finite=False),'scipy_gemm_inverse':lambda b:zgemm(1.,ainv,b),'numpy_gemm_inverse':lambda b:np.matmul(ainv,b,out=np.empty(b.shape,complex,order='F'))}
def p_numpy_old(x,b):return a@x-b
def p_numpy_F(x,b):
    res=np.empty(x.shape,np.complex128,order='F');np.matmul(a,x,out=res);res-=b;return res
def p_scipy(x,b):
    res=zgemm(1.,a,x);res-=b;return res
products={'numpy_old':p_numpy_old,'numpy_F':p_numpy_F,'scipy_zgemm':p_scipy}
def sweep(solve,prod):
    ts_=[];tp=[];t0=time.perf_counter()
    for b in B:
        t=time.perf_counter();x=solve(b);ts_.append(time.perf_counter()-t)
        t=time.perf_counter();res=prod(x,b);tp.append(time.perf_counter()-t)
        t=time.perf_counter();c=solve(res);ts_.append(time.perf_counter()-t)
        t=time.perf_counter();res=prod(x,b);tp.append(time.perf_counter()-t)
    return time.perf_counter()-t0,float(np.sum(ts_)),float(np.sum(tp))
combos=[(s,p) for s in solvers for p in products];out={}
for s,p in combos:sweep(solvers[s],products[p])
R={c:[] for c in combos}
for rep in range(6):
    for c in (combos if rep%2==0 else combos[::-1]):R[c].append(sweep(solvers[c[0]],products[c[1]]))
before=pools()
for (s,p),v in R.items():
    v=np.array(v);out[f'{s}|{p}']=dict(total=float(np.median(v[:,0])),solve_sum=float(np.median(v[:,1])),product_sum=float(np.median(v[:,2])))
res=dict(n=n,requested=dict(numpy=tn,scipy=ts),pools_read_back=before,libraries={k:dict(version=l.version,architecture=getattr(l,'architecture',None),filepath=os.path.basename(l.filepath)) for k,l in libs.items()},results=out)
json.dump(res,open(sys.argv[4],'w'),indent=1)
print('numpy/scipy threads',before)
for s in solvers:print('  solve via %-20s'%s,{p:'%.2f (solve %.2f + product %.2f)'%(out[f'{s}|{p}']['total'],out[f'{s}|{p}']['solve_sum'],out[f'{s}|{p}']['product_sum']) for p in products})
