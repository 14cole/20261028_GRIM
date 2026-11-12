"""Focused resource/scale/ID/thread contracts. Run with PYTHONPATH=tools/GHOST."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from ghost_backend.execution.options import execution_scope, factor_blas_threads
from ghost_backend.execution.dense_memory import forecast, GIB
from ghost_backend.execution.selection import request_selection_scope
from ghost_backend.twod.assembly.compact import CompactOperator
from ghost_backend.compressed.scaling import compression_scales

class Planning(unittest.TestCase):
    def plan(self, capacity=2, storage='auto', automatic=True, execution=False, submission=False,
             scratch=True, d=4000, batch=256, assembly=1., solve=1.6):
        with execution_scope(dict(factorization='automatic' if automatic else 'dense', dense_residual_storage=storage)), \
             patch('ghost_backend.twod.solver._solve_memory_limit_gb', return_value=capacity), \
             patch('ghost_backend.execution.dense_memory.scratch_available', return_value=(scratch, None if scratch else 'test unavailable')):
            return forecast(d, batch, batch, assembly*GIB, solve*GIB, 0, True,
                            submission=submission, execution=execution)
    def test_margin_prices_disk(self):
        ordinary=self.plan(automatic=False); lean=self.plan()
        self.assertEqual(ordinary['residual_storage'],'memory')
        self.assertLess(ordinary['peak_bytes'],2*GIB)
        self.assertGreater(ordinary['peak_bytes'],1.6*GIB)
        self.assertEqual(lean['residual_storage'],'disk')
        self.assertLess(lean['peak_bytes'],1.6*GIB)
        self.assertFalse(lean['allow_optional_partner'])
    def test_live_capacity_below_original_reservation(self):
        with patch('ghost_backend.execution.memory_budget.current',return_value=SimpleNamespace(stable=lambda:8.)):
            plan=self.plan(capacity=2.)
        self.assertEqual(plan['capacity_bytes'],2*GIB)
        self.assertEqual(plan['residual_storage'],'disk')

    def test_explicit_memory_and_no_scratch(self):
        for plan in (self.plan(storage='memory'),self.plan(scratch=False),self.plan(submission=True)):
            self.assertEqual(plan['residual_storage'],'memory')
    def test_carry_recheck_and_unrelated_mesh(self):
        lean=self.plan(); selection={'meshes':[{'unknowns':4000,'backend_memory_plans':{'dense':lean}}]}
        with request_selection_scope(selection):
            self.assertEqual(self.plan(capacity=8,execution=True)['residual_storage'],'disk')
            self.assertTrue(self.plan(capacity=8,execution=True)['selected_plan_carried'])
            self.assertEqual(self.plan(capacity=8,execution=True,d=4001)['residual_storage'],'memory')
            self.assertEqual(self.plan(capacity=8,execution=True,storage='memory')['residual_storage'],'memory')
            with self.assertRaisesRegex(MemoryError,'no longer available'):
                self.plan(capacity=8,execution=True,scratch=False)
    def test_batch_carried(self):
        plan=self.plan(capacity=1.4, batch=2048, solve=2.1)
        self.assertLess(plan['angle_batch_size'],2048)
        with request_selection_scope({'meshes':[{'unknowns':4000,'backend_memory_plans':{'dense':plan}}]}):
            actual=self.plan(capacity=8,batch=2048,solve=2.1,execution=True)
        self.assertEqual(actual['angle_batch_size'],plan['angle_batch_size'])

    def test_nested_selected_plan_survives(self):
        from ghost_backend.execution.options import configured_execution
        from ghost_backend.execution.selection import current_request_selection
        @configured_execution
        def nested(solver_method='experimental_cpu'):
            return {'seen':current_request_selection()}
        selection={'meshes':[{'unknowns':4000,'backend_memory_plans':{'dense':self.plan()}}]}
        with request_selection_scope(selection):
            result=nested(execution_options={'factorization':'dense'})
        self.assertEqual(result['seen'],selection)

    def test_partner_does_not_spend_margin(self):
        from ghost_backend.execution.dense_memory import pair
        plan=self.plan(capacity=2.4,solve=1.6)
        self.assertEqual(plan['residual_storage'],'memory')
        with patch('ghost_backend.execution.dense_memory.current',return_value=plan):
            self.assertFalse(pair(4000,True))
        self.assertEqual(plan['partner_matrix_bytes'],0)

class Contracts(unittest.TestCase):
    def test_tree_telemetry_is_throttled_not_parent_rss(self):
        from ghost_backend.execution.metrics import SolveMetrics
        from unittest.mock import Mock
        metrics=SolveMetrics();process=Mock()
        process.memory_info.return_value=SimpleNamespace(rss=1234)
        metrics._process=process
        with patch.object(metrics,'_sample_process_tree') as tree:
            for now in (0.,.1,.3,.9,1.1):
                with patch('ghost_backend.execution.metrics.time.monotonic',return_value=now):
                    metrics.sample_memory()
            self.assertEqual(tree.call_count,2)
            with patch('ghost_backend.execution.metrics.time.monotonic',return_value=1.2):
                metrics.sample_memory(force_tree=True)
            self.assertEqual(tree.call_count,3)
        self.assertEqual(process.memory_info.call_count,6)
        self.assertEqual(metrics.peak_rss,1234)

    def test_ids(self):
        for ids in ([],[0],[0,1,3],[3,0,1],np.array([1,3],dtype=np.uint64)):
            out=CompactOperator._ids(ids,4);np.testing.assert_array_equal(out,ids)
        for ids in ([0,0],[3,0,3],[-1],[4],[1.5],[[1,2]],np.array([2**64-1],dtype=np.uint64)):
            with self.assertRaises(ValueError):CompactOperator._ids(ids,4)
        a=np.arange(5);b=CompactOperator._ids(a,5);b[0]=4;self.assertEqual(a[0],0)
    def test_dielectric_units(self):
        # Compare the same dimensionless block system represented in metres
        # and centimetres; dimensional powers are independent of implementation.
        base=np.arange(1,17).reshape(4,4).astype(float)
        normalized=[]
        for k in (1.,10000.):
            raw=base.copy();raw[:2,:2]/=k;raw[:2,2:]/=k*k;raw[2:,2:]/=k
            rows,cols,_=compression_scales(SimpleNamespace(kind='dielectric',k0=k,n=4,nn=2))
            normalized.append(rows[:,None]*raw*cols[None,:])
        np.testing.assert_allclose(*normalized,rtol=1e-15)
    def test_thread_cap_and_restoration(self):
        from threadpoolctl import threadpool_limits,threadpool_info
        class Factor:
            small_product_blas_threads=1
            @factor_blas_threads
            def run(self,fail=False):
                counts=[p['num_threads'] for p in threadpool_info() if p['user_api']=='blas']
                if fail:raise RuntimeError('cancel simulation')
                return counts
        with threadpool_limits(limits=3,user_api='blas'),execution_scope({'blas_threads':4}):
            before=[p['num_threads'] for p in threadpool_info() if p['user_api']=='blas']
            self.assertTrue(all(n==1 for n in Factor().run()))
            with self.assertRaises(RuntimeError):Factor().run(True)
            self.assertEqual(before,[p['num_threads'] for p in threadpool_info() if p['user_api']=='blas'])
if __name__=='__main__':unittest.main(verbosity=2)
