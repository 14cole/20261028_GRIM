"""Randomized product timing and traced allocations; no physical-solve speed claim."""
import numpy as np,time,json,sys,tracemalloc
from threadpoolctl import threadpool_limits,threadpool_info
n=int(sys.argv[1]);rng=np.random.default_rng(1811);records=[]
a=np.asfortranarray(rng.normal(size=(n,n))+1j*rng.normal(size=(n,n)))
for threads in (1,4):
 with threadpool_limits(threads):
  for width in (1,16,180,360):
   x=np.asfortranarray(rng.normal(size=(n,width))+1j*rng.normal(size=(n,width)));b=np.zeros_like(x)
   def base():return a@x-b
   def proposed():
    out=np.empty(x.shape,complex,order='F');np.matmul(a,x,out=out);out-=b;return out
   times={k:[] for k in ('base','proposed')};reference=base()
   for rep in range(10):
    for key in rng.permutation(['base','proposed']):
     t=time.perf_counter();result={'base':base,'proposed':proposed}[key]();times[key].append(time.perf_counter()-t)
     assert np.linalg.norm(result-reference)/np.linalg.norm(reference)<1e-13
   peaks={}
   for key,fn in [('base',base),('proposed',proposed)]:
    tracemalloc.start();result=fn();peaks[key]=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
   records.append(dict(threads=threads,width=width,times=times,traced_peak=peaks))
json.dump(dict(n=n,records=records,blas=threadpool_info()),open(sys.argv[2],'w'),indent=2)
print('PASS products',len(records))
