from common import *
from ghost_backend.execution.thread_control import threadpool_limits
import collections
n=int(sys.argv[1]); f=float(sys.argv[2]); a=0.1
sol=BorPecSolver(sphere_pts(a,n), f*1e9)
ka=sol.k*a; m_max=int(np.ceil(ka+4*ka**(1/3)+2))
shapes=collections.Counter(); 
orig=K._project_half_grid
def rec(samples, table, modes, size, method, odd=False):
    shapes[(samples.shape[0], samples.shape[1], len(modes), method, odd)]+=1
    return orig(samples, table, modes, size, method, odd)
K._project_half_grid=rec
with threadpool_limits(1):
    c=time.process_time()
    st=S.StreamingFarBlocks(sol,m_max,efie=True,mfie=True,tile_threads=1)
    print('build cpu (1 BLAS thread; OMP threads counted)',time.process_time()-c)
K._project_half_grid=orig
tot=collections.Counter(); samp=0
for (p,h,m,meth,odd),cnt in shapes.items(): tot[meth]+=cnt*p*h*m; samp+=cnt*p*h
print('calls',sum(shapes.values()),'work pairs*half*modes by method',dict(tot),'total samples',samp)
hs=collections.Counter()
for (p,h,m,meth,odd),cnt in shapes.items(): hs[(h,meth)]+=cnt*p
print('pairs by (half,method):',sorted(hs.items())[:80])
# benchmark the three methods on the recorded shapes (CPU time, 1 thread)
rng=np.random.default_rng(0)
res=collections.Counter()
with threadpool_limits(1):
    for (p,h,m,meth,odd),cnt in sorted(shapes.items()):
        size=2*(h-1); modes=np.arange(m)
        x=(rng.standard_normal((p,h))+1j*rng.standard_normal((p,h)))
        for method in ('complex','real','fft'):
            cos,sin,_,_,_=K._half_grid_tables(size,modes,True,method)
            tab=sin if odd else cos
            reps=max(1,int(2e6/(p*h*m)))
            t=time.thread_time()
            for _ in range(reps): orig(x,tab,modes,size,method,odd)
            dt=(time.thread_time()-t)/reps
            res[method]+=dt*cnt
            res[('chosen' if method==meth else 'x')]+=dt*cnt if method==meth else 0
        best=None
print('projected CPU if always:', {k:round(v,2) for k,v in res.items() if k!='x'})
