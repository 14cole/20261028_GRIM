"""What is live when the dense LU copy is made? (N=5120 PEC circle, both polarizations)"""
import sys, os, time, tracemalloc
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
import psutil
from ghost_backend.twod import solver as S
me=psutil.Process()
tracemalloc.start(6)
orig=S._SCIPY_LINALG.lu_factor
class Proxy:
    def __getattr__(self,k): return getattr(S_orig,k)
S_orig=S._SCIPY_LINALG
def lu_factor(a,*args,**kw):
    snap=tracemalloc.take_snapshot()
    print('--- lu_factor called: matrix GiB',round(a.nbytes/2**30,3),'RSS GiB',round(me.memory_info().rss/2**30,3),'traced GiB',round(tracemalloc.get_traced_memory()[0]/2**30,3),flush=True)
    for st in snap.statistics('traceback')[:6]:
        if st.size<30e6: break
        print('   %.3f GiB x%d'%(st.size/2**30,st.count)); 
        for line in st.traceback.format()[-8:]: print('      ',line.strip()[:150])
    r=orig(a,*args,**kw)
    print('--- after lu_factor RSS GiB',round(me.memory_info().rss/2**30,3),flush=True)
    return r
proxy=Proxy(); proxy.lu_factor=lu_factor
S._SCIPY_LINALG=proxy
a=float(sys.argv[1]); f=float(sys.argv[2])
g=circle_geo(a,256,props='2 0 0 0 0')
r=S.solve_monostatic_rcs_2d(g,[f],list(np.linspace(0,180,181)),geometry_units='meters',solver_method='auto',execution_options=dict(factorization='dense',mesh_strategy='global',assembly_threads='auto',blas_threads=1))
print('unknowns',r['metadata'].get('dense_largest_system'),'peak traced GiB',round(tracemalloc.get_traced_memory()[1]/2**30,3))
