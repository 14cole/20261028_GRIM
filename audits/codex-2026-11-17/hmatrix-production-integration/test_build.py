"""Actual integrated builder versus dense linear algebra and failure invariants."""
import os,sys,unittest
from pathlib import Path
from contextlib import contextmanager
import numpy as np
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
from ghost_backend.compressed.inverse import Oracle,CompressedSystem
from ghost_backend.compressed.construction import Construction,array_bytes
from ghost_backend.compressed.hmatrix_build import _solve_in_place
from ghost_backend.linalg.hierarchical import HierarchicalRejected

class Guard(Construction):
    def __init__(self,owner):super().__init__(owner);self.records=[]
    @contextmanager
    def step(self,label,additional,*live):
        self.records.append((label,additional,array_bytes(live)))
        with super().step(label,additional,*live):yield

class Builder(HMatrixSystem):
    DENSE_FALLBACK_LIMIT=4
    def __init__(self,a,budget=10**8,reject=0):
        self.a=a;self.n=len(a);self.leaf=2;self.bytes=0;self.budget=budget;self.ranks=[];self.leaves=0
        self.dense_fallbacks=0;self.largest_dense_fallback=0;self.reject=reject;self.calls=[];self.checkpoint=lambda:None
        self.construction=Guard(self)
        with self.construction.track():self.root=self.build(Oracle(a),np.arange(len(a)))
    def compress_block(self,oracle,rows,cols):
        self.calls.append((tuple(rows),tuple(cols)))
        if len(rows)+len(cols)==self.reject:raise HierarchicalRejected('controlled rejection')
        a=oracle.get(rows,cols);u,s,v=np.linalg.svd(a,full_matrices=False);rank=np.count_nonzero(s>1e-13)
        return (u[:,:rank]*s[:rank]).astype(complex),v[:rank].astype(complex),0.

def matrix(n,zero=False):
    rng=np.random.default_rng(81);a=np.diag(np.linspace(8,10,n)).astype(complex)
    if not zero:a+=(rng.standard_normal((n,n))+1j*rng.standard_normal((n,n)))*.025
    return a
def payload(node):
    count=0 if node.lu is None else node.lu[0].nbytes+8*len(node.lu[0])
    if not node.leaf:
        count+=sum(getattr(node,k).nbytes for k in ('e1','e2','v12','v21'))+payload(node.left)+payload(node.right)
        assert not hasattr(node,'u12') and not hasattr(node,'u21')
    return count

class Tests(unittest.TestCase):
    def verify(self,a):
        f=Builder(a);rng=np.random.default_rng(7);b=rng.standard_normal((len(a),3))+1j*rng.standard_normal((len(a),3))
        for t,m in [(0,a),(1,a.T),(2,a.conj().T)]:
            x=f.root.solve(b,t);np.testing.assert_allclose(m@x,b,rtol=1e-12,atol=1e-12)
            alias=b.copy();f.root.solve_into(alias,alias,t);np.testing.assert_allclose(alias,x,rtol=1e-13,atol=1e-13)
        self.assertEqual(f.bytes,payload(f.root));return f
    def test_normal_transpose_adjoint_and_accounting(self):self.verify(matrix(16))
    def test_zero_rank_children(self):self.verify(matrix(16,True))
    def test_unequal_ranks(self):
        a=matrix(8,True);a[:4,4:]=.01;a[4:,:4]=np.diag([.01,.02,0,0]);f=self.verify(a)
        self.assertNotEqual(f.root.e1.shape[1],f.root.e2.shape[1])
    def test_small_dense_fallback(self):
        a=matrix(8);f=Builder(a,reject=4);self.assertEqual(f.dense_fallbacks,2)
        np.testing.assert_allclose(a@f.root.solve(np.eye(8)),np.eye(8),atol=1e-12)
        self.assertEqual(f.bytes,payload(f.root))
    def test_large_rejection_propagates(self):
        with self.assertRaises(HierarchicalRejected):Builder(matrix(8),reject=8)
    def test_retained_cap_rejection(self):
        with self.assertRaises(MemoryError):Builder(matrix(8),budget=1)
    def test_diagonal_workspace_and_live_correction(self):
        f=Builder(matrix(8));leaves=[r for r in f.construction.records if r[0]=='leaf coefficients']
        self.assertTrue(leaves);self.assertTrue(all(r[1]==4*2**2*16+2**20 for r in leaves))
        children=[r for r in f.construction.records if r[0]=='inverse child product (in place)']
        self.assertTrue(any(r[2]>0 for r in children))
    def test_copy_path_charges_dtype_growth(self):
        f=Builder(matrix(2));a=np.ones((2,2),dtype=np.complex64);f.bytes=a.nbytes
        class Child:
            def solve_into(self,b,result):result[:]=b/2
        with f.construction.track():v=_solve_in_place(f,Child(),a)
        self.assertEqual(v.dtype,np.complex128);self.assertEqual(f.bytes,v.nbytes);np.testing.assert_array_equal(v,.5)
    def test_base_builder_is_not_overridden(self):
        self.assertIsNot(HMatrixSystem.build,CompressedSystem.build)
        self.assertEqual(CompressedSystem.build.__module__,'ghost_backend.compressed.inverse')
if __name__=='__main__':unittest.main(verbosity=2)
