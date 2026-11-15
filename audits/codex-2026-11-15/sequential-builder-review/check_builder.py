"""Synthetic builder/aliasing/fault checks; full exact matrices, no physical claims."""
import os,sys,json,gc,weakref
from contextlib import nullcontext,contextmanager
from pathlib import Path
import numpy as np
import scipy.linalg as la
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
from ghost_backend.compressed.construction import Construction
import ghost_backend.linalg.hierarchical as hf
from corrected_builder import install,RECORD
spec=json.loads(sys.argv[1]);install(dict(builder='sequential',packing=spec['packing'],rank_guard=True))
rng=np.random.default_rng(117)
n=1152;u=rng.normal(size=(n,4))+1j*rng.normal(size=(n,4));v=rng.normal(size=(4,n))+1j*rng.normal(size=(4,n))
a=np.eye(n,dtype=complex)+.0001*(u@v);coords=np.arange(n)[:,None].astype(float)
class Operator:
    def __init__(self):
        self.n=n;self.leaf=64;self.order=hf.spatial_order(coords,np.arange(n),self.leaf)
        self.position=np.argsort(self.order);self.entries=self.calls=self.max_entries=0
    def _get(self,rows,cols):
        self.calls+=1;self.entries+=len(rows)*len(cols);self.max_entries=max(self.max_entries,len(rows)*len(cols))
        return a[np.ix_(rows,cols)].copy()
    def range_matmul(self,r0,r1,c0,c1,rhs,adjoint=False):
        block=a[np.ix_(self.order[r0:r1],self.order[c0:c1])]
        return (block.conj().T if adjoint else block)@rhs
    def range_workspace_bytes(self,r0,r1,c0,c1,width,adjoint=False):
        return 32*(r1-r0)*(c1-c0)+32*(r1-r0+c1-c0)*width
    def product_scope(self):return nullcontext()
def make():return HMatrixSystem(Operator(),coords,tolerance=1e-10,budget=512*1024**2,checkpoint=None)
b=rng.normal(size=(n,4))+1j*rng.normal(size=(n,4));b[:,1]=b[:,0];b[:,2]=0
lu=la.lu_factor(a);out=dict(spec=spec,checks=[],faults=[])
f=make()
for trans in (0,1,2):
    x=f.apply(b,solve=True,trans=trans);ref=la.lu_solve(lu,b,trans=trans)
    rel=float(la.norm(x-ref)/la.norm(ref));assert rel<5e-7
    work=b[f.permutation].copy();f.root.solve_into(work,work,trans)
    assert np.array_equal(work,x[f.permutation])
    assert np.array_equal(x[:,0],x[:,1]) and np.all(x[:,2]==0)
    out['checks'].append(dict(trans=trans,relative_error=rel,aliased_identical=True,duplicate_and_zero_rhs=True))
del f
# Failures are injected inside guarded operations; never retained as exceptions.
original_step=Construction.step;original_compress=HMatrixSystem.compress_block
class Cancelled(Exception):pass
for mode in ('cancel','memory','dense_fallback','copy_input'):
    refs=[];triggered=[False]
    @contextmanager
    def step(self,label,additional,*live):
        refs.append(weakref.ref(self.owner))
        if mode in ('cancel','memory') and label=='inverse child product (in place)' and not triggered[0]:
            triggered[0]=True
            if mode=='cancel':raise Cancelled('injected cancellation')
            raise MemoryError('injected live allocation rejection')
        with original_step(self,label,additional,*live):yield
    def compress(self,oracle,rows,cols):
        if mode=='dense_fallback' and len(rows)+len(cols)<=self.DENSE_FALLBACK_LIMIT and not triggered[0]:
            triggered[0]=True;raise hf.HierarchicalRejected('injected compression failure')
        result=original_compress(self,oracle,rows,cols)
        if mode=='copy_input':result[0].flags.writeable=False;triggered[0]=True
        return result
    Construction.step=step;HMatrixSystem.compress_block=compress
    caught=False
    try:
        f=make()
        for trans in (0,1,2):
            x=f.apply(b,solve=True,trans=trans);ref=la.lu_solve(lu,b,trans=trans)
            assert la.norm(x-ref)/la.norm(ref)<5e-7
        if mode=='dense_fallback':assert f.dense_fallbacks>0
        del f
    except (Cancelled,MemoryError):caught=True
    finally:Construction.step=original_step;HMatrixSystem.compress_block=original_compress
    assert triggered[0] and caught==(mode in ('cancel','memory'))
    gc.collect();assert all(r() is None for r in refs)
    out['faults'].append(dict(mode=mode,triggered=True,expected_exception=caught,owner_references_released=True))
out['copy_input_count']=RECORD['u_copies'];assert out['copy_input_count']>0
# Exactly zero off-diagonal ranks exercise the lu=None recursion.
a[:]=np.eye(n,dtype=complex);f=make()
for trans in (0,1,2):assert np.array_equal(f.apply(b,solve=True,trans=trans),b)
out['zero_rank_identity']=True

Path(spec['out']+'.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
