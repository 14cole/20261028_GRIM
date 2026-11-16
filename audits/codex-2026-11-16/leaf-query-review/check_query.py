"""Independent BlockRow indexing and allocation checks; no solver timing claims."""
import os,sys,json,tracemalloc,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix import BlockRow
from query_hook import install
original=BlockRow.values;install();direct=BlockRow.values
def measure(fn,row,rr,cc):
    tracemalloc.start();tracemalloc.reset_peak();t=time.perf_counter()
    out=fn(row,rr,cc);elapsed=time.perf_counter()-t
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    return out,dict(tracked_peak_bytes=peak,seconds=elapsed)
records=[];checks=0
for width in (512,4096,32768):
    # Deterministic nonconstant coefficients, with allocation outside tracing.
    u=np.arange(512*width,dtype=np.float64).reshape(512,width).astype(complex)
    u.imag=u.real%17
    row=BlockRow(0,0,512,[(0,width)],u,None)
    for size in (32,149,512):
        rr=np.arange(size,dtype=np.int64);cc=np.arange(size,dtype=np.int64)
        a,old=measure(original,row,rr,cc);b,new=measure(direct,row,rr,cc)
        assert np.array_equal(a,b)
        records.append(dict(partner_width=width,query_size=size,original=old,direct=new))
    del row,u,a,b
rng=np.random.default_rng(91);u=rng.normal(size=(19,23))+1j*rng.normal(size=(19,23))
selectors=[(None,None),(None,slice(2,9)),(slice(1,8),np.array([4,1,4])),
    (np.array([7,1,7,-1]),np.array([3,2,3,-2])),(np.array([],dtype=int),np.arange(7)),
    (np.arange(6),np.array([],dtype=int)),(np.arange(19)%2==0,np.arange(23)%3==0),
    ([4,1,4],[2,8,2])]
for values in (u,np.asfortranarray(u),u[::2]):
    for low_rank in (False,True):
        row=BlockRow(0,0,len(values),[(0,23)],values,np.eye(23,dtype=complex) if low_rank else None)
        for rr,cc in selectors:
            if isinstance(rr,np.ndarray) and rr.dtype==bool and len(rr)!=len(values):continue
            a=original(row,rr,cc);b=direct(row,rr,cc);assert np.array_equal(a,b);checks+=1
out=dict(indexing_checks=checks,measurements=records,note='tracemalloc tracks Python/NumPy allocations, not all native workspace; times are single microcalls, not speed benchmarks.')
Path(__file__).with_name('query-check.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
