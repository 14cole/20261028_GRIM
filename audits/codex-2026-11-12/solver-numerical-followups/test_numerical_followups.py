"""Independent coefficient, transpose, storage, and refinement contracts.
Requires NumPy, SciPy, and threadpoolctl (the existing thread-limit regression dependency).
Run: PYTHONPATH=tools/GHOST python test_numerical_followups.py
"""
import unittest,tempfile,pickle
import numpy as np
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope
from ghost_backend.compressed.operator import StreamedOperator
from ghost_backend.compressed.factor import CompressedFactor
from ghost_backend.compressed.scaling import compression_scales
from ghost_backend.compressed.tile_processes import _compressor
from ghost_backend.compressed.polarization_cache import SpooledOperator
from ghost_backend.linalg.dense import DenseFactor

class Oracle:
    kind='dielectric';nn=32;n=64;calls=entries=dropped_routes=max_entries=0
    def __init__(self,k=1e5):
        self.k0=k
        rows,cols,_=compression_scales(self)
        rng=np.random.default_rng(42)
        u=rng.normal(size=(self.n,4))+1j*rng.normal(size=(self.n,4))
        self.eq=20*np.eye(self.n)+u@u.conj().T
        self.a=self.eq/rows[:,None]/cols[None,:]
        self.xy=rng.normal(size=(self.n,2))
    def get_with_error(self,rows,cols):
        self.calls+=1;self.entries+=len(rows)*len(cols);self.max_entries=max(self.max_entries,len(rows)*len(cols))
        block=self.a[np.ix_(rows,cols)].copy();return block,np.zeros(block.shape)
    def get(self,rows,cols):return self.get_with_error(rows,cols)[0]

class Numerical(unittest.TestCase):
    def setUp(self):
        self.cpu=cpu_allocation_scope(1);self.cpu.__enter__()
        self.scope=execution_scope(dict(factorization='compressed',blas_threads=1,assembly_threads=1));self.scope.__enter__()
    def tearDown(self):self.scope.__exit__(None,None,None);self.cpu.__exit__(None,None,None)
    def test_tile_bounds_and_transposes(self):
        for k in [1e-4,1.,1e5]:
            oracle=Oracle(k);op=StreamedOperator(oracle,oracle.xy,tile=16,budget=2**24)
            actual=op.get(np.arange(op.n),np.arange(op.n));difference=abs(actual-oracle.a)
            np.testing.assert_array_less(difference.sum(axis=1),op.row_error+1e-12*np.max(abs(oracle.a)))
            r,c,_=compression_scales(oracle);scaled=difference*r[:,None]*c[None,:]
            np.testing.assert_array_less(scaled.sum(axis=1),op.scaled_row_error+1e-12*np.max(abs(oracle.eq)))
            factor=CompressedFactor(op,diagnostics={},storage_budget_bytes=2**25)
            rng=np.random.default_rng(9)
            for trans in [0,1,2]:
                columns=c if trans==0 else r
                truth=(rng.normal(size=(op.n,3))+1j*rng.normal(size=(op.n,3)))*columns[:,None]
                matrix=oracle.a if trans==0 else oracle.a.T if trans==1 else oracle.a.conj().T
                b=matrix@truth;x=factor.inverse(b,trans)
                self.assertLess(np.max(abs(x-truth)/columns[:,None])/np.max(abs(truth)/columns[:,None]),1e-9)
    def test_worker_compressor_and_spool(self):
        o=Oracle();op=StreamedOperator(o,o.xy,tile=16,budget=2**24,assemble=False)
        shell=pickle.loads(pickle.dumps(_compressor(op)))
        with tempfile.TemporaryDirectory() as directory:
            spool=SpooledOperator(o,o.xy,tile=16,budget=2**24,assemble=False,directory=directory)
            for j,cols in enumerate(op.groups):
                for i,rows in enumerate(op.groups):
                    value=shell.compress_tile(i,j,*o.get_with_error(rows,cols));op.store_tile(value);spool.store_tile(value)
            op.finalize(o);spool.finalize(o);spool.load()
            x=np.arange(o.n,dtype=complex)
            for key in op.tiles:
                for before,after in zip(op.tiles[key],spool.tiles[key]):
                    if before is not None:np.testing.assert_array_equal(before,after)
            # Disk decoding changes BLAS array layout, not coefficient bits.
            np.testing.assert_allclose(op@x,spool@x,rtol=2e-14,atol=1e-14)
            np.testing.assert_array_equal(op.scaled_row_error,spool.scaled_row_error)
            self.assertEqual(op.bytes,spool.bytes)
    def test_uniform_tile_units_preserve_payload(self):
        first=Oracle();first.kind='robin';first.pec_nodes=np.ones(first.n,bool);first.a=first.eq/first.k0**2
        second=Oracle();second.kind='unknown';second.a=first.a.copy()
        a=StreamedOperator(first,first.xy,tile=16,budget=2**24)
        b=StreamedOperator(second,second.xy,tile=16,budget=2**24)
        self.assertGreater(a.compressed,0)
        for key in a.tiles:
            for left,right in zip(a.tiles[key],b.tiles[key]):
                if left is not None:np.testing.assert_array_equal(left,right)
    def test_stronger_initial_keeps_compact_retry(self):
        from unittest.mock import patch
        f=CompressedFactor.__new__(CompressedFactor);f.event={};f.initial_preconditioner_tolerance=1e-10
        attempts=[]
        def build(tolerance):
            attempts.append(tolerance)
            if len(attempts)==1:raise MemoryError('injected retained-storage exhaustion')
        f._build=build
        with patch('ghost_backend.compressed.preconditioner_hints.try_build',return_value=False),patch('ghost_backend.execution.memory_budget.admit_phase'):
            f._fresh_build()
        self.assertEqual(attempts,[1e-10,1e-6])
        self.assertIn('injected retained-storage',f.event['compact_preconditioner'])
    def test_capacity_and_cancellation(self):
        o=Oracle()
        with self.assertRaises(MemoryError):StreamedOperator(o,o.xy,budget=1)
        def cancel():raise InterruptedError('cancel')
        with self.assertRaises(InterruptedError):StreamedOperator(o,o.xy,checkpoint=cancel)
    def test_thin_units_and_endpoints(self):
        from types import SimpleNamespace
        o=SimpleNamespace(kind='thin',n=8,nn=4,k0=10.,B=.02,endpoints=np.array([0,3]))
        r,c,_=compression_scales(o)
        np.testing.assert_array_equal(r,[1,1,1,1,1,10,10,1]);np.testing.assert_array_equal(c,[10,10,10,10,1,1,1,1])
    def test_dense_transpose_and_condition_gate(self):
        with execution_scope(dict(factorization='dense',blas_threads=1)):
            o=Oracle(1e6);f=DenseFactor(o.a.copy(),diagnostics={})
            rng=np.random.default_rng(53)
            for trans in [0,1,2]:
                matrix=o.a if trans==0 else o.a.T if trans==1 else o.a.conj().T
                truth=rng.normal(size=(o.n,2))+1j*rng.normal(size=(o.n,2))
                x=f._solve_lu(matrix@truth,trans=trans)
                self.assertLess(np.max(abs(matrix@x-matrix@truth))/np.max(abs(matrix@truth)),1e-12)
            # Equilibration must not disguise nearly dependent equations.
            bad=np.ones((2,2),complex);bad[1,1]+=1e-9
            diag={};DenseFactor(bad,diagnostics=diag)
            self.assertGreater(diag['condition_est'],1e6)
    def test_dense_disk_original_and_transposes(self):
        with execution_scope(dict(factorization='dense',blas_threads=1,dense_residual_storage='disk')):
            o=Oracle(1e5);a=np.array(o.a,order='F',copy=True);original=a.copy()
            f=DenseFactor(a,diagnostics={},owned_matrix=True)
            try:
                self.assertEqual(f.event['residual_storage'],'disk')
                for trans in [0,1,2]:
                    matrix=original if trans==0 else original.T if trans==1 else original.conj().T
                    b=np.ones((o.n,2),complex)
                    x=f._solve_lu(b,trans)
                    self.assertLess(np.max(abs(matrix@x-b)),1e-8)
                f.restore_original();np.testing.assert_array_equal(a,original)
            finally:f.close()
    def test_dense_scaled_and_zero_rhs(self):
        with execution_scope(dict(factorization='dense',blas_threads=1)):
            o=Oracle(1e6);r,c,_=compression_scales(o)
            rng=np.random.default_rng(77);truth=(rng.normal(size=(o.n,3))+1j*rng.normal(size=(o.n,3)))*c[:,None];truth[:,0]=0
            f=DenseFactor(o.a,diagnostics={});x=f.solve(o.a@truth)
            self.assertLess(np.max(abs(x-truth)/c[:,None])/np.max(abs(truth)/c[:,None]),1e-9)
            np.testing.assert_array_equal(x[:,0],0.)
            self.assertLess(f.event['max_equilibrated_backward_error'],1e-12)

if __name__=='__main__':unittest.main(verbosity=2)
