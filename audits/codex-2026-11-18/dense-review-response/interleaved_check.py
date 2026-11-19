"""Independent randomized solver-order benchmark with both BLAS pools observed."""
import os,sys,time,json,pathlib,resource
import numpy as np,scipy.linalg as la
from scipy.linalg.blas import zgemm
sys.path.insert(0,str(pathlib.Path(os.environ.get('BASE_GRIM_ROOT','/workspace/production-consolidation/candidate'))/'tools/GHOST'))
try:from ghost_backend.execution.thread_control import threadpool_info,ThreadpoolController
except ImportError:from threadpoolctl import threadpool_info,ThreadpoolController
spec=json.loads(sys.argv[1]);rng=np.random.default_rng(2026111819);n=spec.get('n',3072);w=spec.get('width',16)
controller=ThreadpoolController()
scopes=[]
for component,threads in [('numpy',spec['np_threads']),('scipy',spec['sp_threads'])]:
 pools=[p for p in threadpool_info() if '/'+component+'.libs/' in p['filepath']]
 assert len(pools)==1,(component,pools)
 scope=controller.select(filepath=pools[0]['filepath']).limit(limits=threads);scopes.append(scope)
pools=threadpool_info();assert all(p['num_threads']==spec['np_threads' if '/numpy.libs/' in p['filepath'] else 'sp_threads'] for p in pools)
a=np.asfortranarray(rng.normal(size=(n,n))+1j*rng.normal(size=(n,n)));a.flat[::n+1]+=n
lu=la.lu_factor(a);rhs=[rng.normal(size=(n,w))+1j*rng.normal(size=(n,w)) for _ in range(3)]
def baseline(x,b):return a@x-b
def numpy_f(x,b):
 r=np.empty(x.shape,complex,order='F');np.matmul(a,x,out=r);r-=b;return r
def direct(x,b):r=zgemm(1.,a,x);r-=b;return r
functions=dict(baseline=baseline,numpy_f=numpy_f,direct=direct)
def sweep(fn):
 products=[];solves=[];cpu=time.process_time();t0=time.perf_counter();last=[]
 for b in rhs:
  t=time.perf_counter();x=la.lu_solve(lu,b,check_finite=False);solves.append(time.perf_counter()-t)
  t=time.perf_counter();res=fn(x,b);products.append(time.perf_counter()-t)
  t=time.perf_counter();x+=la.lu_solve(lu,-res,check_finite=False);solves.append(time.perf_counter()-t)
  t=time.perf_counter();res=fn(x,b);products.append(time.perf_counter()-t)
  last.append(x)
 elapsed=time.perf_counter()-t0
 return dict(wall_seconds=elapsed,cpu_seconds=time.process_time()-cpu,products=products,solves=solves),last
for fn in functions.values():sweep(fn)
records=[];reference=None;errors={};arrays={}
for rep in range(5):
 for name in rng.permutation(list(functions)):
  measurement,answers=sweep(functions[name]);records.append(dict(variant=name,rep=rep,**measurement))
  if reference is None:reference=answers
  # Axis-free linalg.norm uses BLAS and wakes the NumPy pool between sweeps.
  # Elementwise reductions validate all answers without that extra pool call.
  err=max(float(np.sqrt(np.sum(abs(x-y)**2)/np.sum(abs(y)**2))) for x,y in zip(answers,reference));assert err<1e-12
  errors[name]=max(errors.get(name,0.),err)
  if rep==0:arrays[name]=answers[0][:,:min(w,4)]
out=pathlib.Path(spec['out']);out.parent.mkdir(parents=True,exist_ok=True)
out.with_suffix('.json').write_text(json.dumps(dict(spec=spec,pools=pools,records=records,errors=errors,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20),indent=2))
np.savez_compressed(out.with_suffix('.npz'),**arrays)
print(json.dumps({k:float(np.median([r['wall_seconds'] for r in records if r['variant']==k])) for k in functions}),flush=True)
for scope in scopes:scope.restore_original_limits()
