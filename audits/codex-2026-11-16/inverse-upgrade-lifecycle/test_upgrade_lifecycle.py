"""Focused state/admission regressions complement the native physical suite."""
import os,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack
sys.path.insert(0,str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST'))
from ghost_backend.compressed.factor import CompressedFactor
from ghost_backend.linalg.hierarchical import HierarchicalRejected
MIB=2**20
class Factor(CompressedFactor):
    def __init__(self):
        self.factor=SimpleNamespace(bytes=MIB);self.tolerance=1e-8
        self.budget=100*MIB;self.event={};self.builds=[];self.failures=[];self._upgrade_attempted=True
    def _build(self,tolerance):
        self.factor=None;self.builds.append(tolerance)
        if self.failures:raise self.failures.pop(0)
        self.factor=SimpleNamespace(bytes=MIB);self.tolerance=tolerance
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.admit=self.stack.enter_context(patch('ghost_backend.execution.memory_budget.admit_phase'))
        self.hint=self.stack.enter_context(patch('ghost_backend.compressed.preconditioner_hints.try_build',return_value=False))
        self.stack.enter_context(patch('ghost_backend.twod.solver._process_rss_bytes',return_value=0))
        self.stack.enter_context(patch('ghost_backend.twod.solver._solve_memory_limit_gb',return_value=1.))
        self.stack.enter_context(patch('ghost_backend.compressed.worker_pool.retained_bytes',return_value=0))
    def test_once_per_successful_fresh_build(self):
        f=Factor();f._fresh_build();self.assertTrue(f._upgrade_preconditioner())
        self.assertFalse(f._upgrade_preconditioner());self.assertEqual(f.builds,[1e-8,1e-10])
        f._fresh_build();self.assertTrue(f._upgrade_preconditioner());self.assertFalse(f._upgrade_preconditioner())
        self.assertEqual(f.builds,[1e-8,1e-10,1e-8,1e-10])
    def test_denied_upgrade_not_retried_each_solve(self):
        f=Factor();f._fresh_build();f.budget=2*MIB
        self.assertFalse(f._upgrade_preconditioner());f.budget=100*MIB
        self.assertFalse(f._upgrade_preconditioner());self.assertEqual(f.builds,[1e-8])
        f._fresh_build();self.assertTrue(f._upgrade_preconditioner())
    def test_hint_fallback_suppression_is_generation_scoped(self):
        f=Factor();f._fresh_build(allow_upgrade=False)
        for _ in range(3):self.assertFalse(f._upgrade_preconditioner())
        self.assertEqual(f.builds,[1e-8]);f._fresh_build();self.assertTrue(f._upgrade_preconditioner())
    def test_hint_early_return_uses_requested_policy(self):
        self.hint.side_effect=lambda f:(f._build(1e-10) or True)
        f=Factor();f._fresh_build();self.assertFalse(f._upgrade_attempted)
        f._fresh_build(allow_upgrade=False);self.assertTrue(f._upgrade_attempted)
    def test_failed_admission_preserves_previous_attempt_state(self):
        f=Factor();old=f.factor;self.admit.side_effect=MemoryError('admission')
        with self.assertRaises(MemoryError):f._fresh_build()
        self.assertTrue(f._upgrade_attempted);self.assertIs(f.factor,old);self.assertEqual(f.builds,[])
    def test_failed_compact_retry_does_not_rearm(self):
        f=Factor();f.failures=[MemoryError('ordinary'),MemoryError('compact')]
        with self.assertRaises(MemoryError):f._fresh_build()
        self.assertTrue(f._upgrade_attempted);self.assertEqual(f.builds,[1e-8,1e-6])
    def test_cancelled_fresh_build_does_not_rearm(self):
        f=Factor();f.failures=[InterruptedError('cancel')]
        with self.assertRaises(InterruptedError):f._fresh_build()
        self.assertTrue(f._upgrade_attempted);f._fresh_build();self.assertFalse(f._upgrade_attempted)
    def test_coarse_rejection_success_rearms(self):
        f=Factor();f.failures=[HierarchicalRejected('coarse')];f._fresh_build()
        self.assertFalse(f._upgrade_attempted);self.assertEqual(f.builds,[1e-8,2e-10])
    def test_cancelled_optional_upgrade_restores_old_inverse(self):
        f=Factor();f._fresh_build();old=f.factor;budget=f.budget;f.failures=[InterruptedError('cancel upgrade')]
        with self.assertRaises(InterruptedError):f._upgrade_preconditioner()
        self.assertIs(f.factor,old);self.assertEqual(f.budget,budget);self.assertEqual(f.tolerance,1e-8)
        self.assertIsNone(f._construction_previous);self.assertFalse(f._upgrade_preconditioner())
if __name__=='__main__':unittest.main(verbosity=2)
