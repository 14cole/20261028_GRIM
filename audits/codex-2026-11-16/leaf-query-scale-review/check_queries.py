"""Independent bit/error parity and actual low-rank HMatrix query allocation."""
import os,sys,json,tracemalloc,warnings
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix import BlockRow,HMatrixOperator
original=BlockRow.values
from query_hook import install
install();candidate=BlockRow.values
def corrected(self,rows=None,columns=None):
    if (isinstance(rows,np.ndarray) and isinstance(columns,np.ndarray)
            and (rows.size==0 or columns.size==0)):
        return original(self,rows,columns)
    return candidate(self,rows,columns)
def br(u,v=None,ranges=None):
    return BlockRow(0,0,u.shape[0],ranges or [(0,u.shape[1] if v is None else v.shape[1])],u,v)
def outcome(fn,b,r,c):
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always')
        try:
            a=fn(b,r,c)
            return dict(shape=a.shape,dtype=a.dtype.str,bytes=a.tobytes().hex(),warnings=[str(w.message) for w in ws])
        except Exception as e:return dict(error=type(e).__name__,warnings=[str(w.message) for w in ws])
cases=[]
for r,c in [(np.array([4]),np.array([],dtype=int)),(np.array([-5]),np.array([],dtype=int)),
            (np.array([],dtype=int),np.array([5])),(np.array([0]),np.array([],dtype=int)),
            (np.array([],dtype=int),np.array([0]))]:
    b=br(np.arange(20.).reshape(4,5).astype(complex))
    d=dict(rows=r.tolist(),cols=c.tolist(),original=outcome(original,b,r,c),candidate=outcome(candidate,b,r,c),corrected=outcome(corrected,b,r,c))
    assert d['corrected']==d['original'];cases.append(d)
# Test payload bits, including signed zeros, infinities and two NaN payloads.
bits=np.array([0,0x8000000000000000,0x7ff0000000000000,0xfff0000000000000,0x7ff8000000000001,0x7ff8000000000042],dtype=np.uint64)
a=np.tile(bits,16).view(np.complex128).reshape(6,8)
bit_cases=0
for u in [a,np.asfortranarray(a),np.repeat(np.repeat(a,2,0),2,1)[::2,::2]]:
    for r in [np.arange(6),np.array([5,1,1,0]),np.array([],dtype=int)]:
        for c in [np.arange(8),np.array([7,2,0,2]),np.array([],dtype=int)]:
            assert outcome(original,br(u),r,c)==outcome(corrected,br(u),r,c)
            bit_cases+=1
BlockRow.values=corrected
def allowance(m,n,rank):
    # Scope: complex128 retained operator, serial query, existing indexed path.
    return 64*m*n+16*rank*(m+n)+128*(m+n)+2**20
def op_for(rows):
    op=object.__new__(HMatrixOperator)
    # Separate levels permit additive contributions to the same rows.
    op.levels=[(np.array([b.start]),np.array([b.stop]),[[b]]) for b in rows]
    return op
alloc=[]
for m,n,rank,height,width in [(149,149,32,256,512),(149,149,600,1024,2048),
        (149,149,2000,4096,8192),(256,256,159,512,1024),(256,256,384,768,2048),
        (37,211,128,512,1024),(1024,1024,700,2048,4096)]:
    # Ones permit an exact analytical check without a full dense product.
    u=np.ones((height,rank),complex);v=np.ones((rank,width),complex)
    block=br(u,v);op=op_for([block]);ids=np.arange(m)[::-1];cols=np.arange(n)[::-1]
    assert rank*(height+width)<height*width  # storable compressed representation
    tracemalloc.start();tracemalloc.reset_peak()
    result=op._get_positions(ids,cols);current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    assert np.all(result==rank)
    proposed=allowance(m,n,rank);assert peak<proposed,(m,n,rank,peak,proposed)
    alloc.append(dict(rows=m,columns=n,rank=rank,stored_height=height,stored_width=width,
        peak_bytes=peak,result_bytes=result.nbytes,old_proposal_bytes=64*m*n+2**20,
        rank_aware_bytes=proposed,exceeds_old_proposal=peak>64*m*n+2**20))
    del result,op,block,u,v
# Multiple levels and disjoint partner ranges, repeats, reordering.
u=np.ones((384,50),complex);v=np.ones((50,512),complex)
op=op_for([br(u,v,[(0,256),(512,768)]),br(u*2,v,[(0,256),(512,768)])])
r=np.array([300,1,1,200]);c=np.array([700,20,300,20])
result=op._get_positions(r,c);assert np.array_equal(result,np.tile([150,150,0,150],(4,1)))
d=dict(empty_index_cases=cases,original_candidate_error_mismatches=sum(x['original']!=x['candidate'] for x in cases),
      corrected_error_mismatches=0,payload_bit_cases=bit_cases,allocation_cases=alloc,multilevel_ranges_repeats_pass=True,
      scope='Python/NumPy tracemalloc, not a native allocation bound; full retained-operator queries')
Path(__file__).with_name('query-check.json').write_text(json.dumps(d,indent=2));print(json.dumps(d,indent=2))
