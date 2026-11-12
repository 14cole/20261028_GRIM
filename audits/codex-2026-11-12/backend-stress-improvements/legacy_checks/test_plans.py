"""Regression checks for qualification, bounded projection and shared resource choices."""
import json, sys, tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1]).resolve()/'tools/GHOST'))
from ghost_backend.execution import dense_memory as DM, memory_budget as MB
from ghost_backend.execution.options import execution_scope
from ghost_backend.twod import solver as S
from ghost_backend.twod.adaptive_geometry import panel_parameters, point_key
from ghost_backend.twod.quadrature_quality import panel_qualification
from ghost_backend.compressed.hmatrix_factor import _RangeBlock
from ghost_backend.execution.cpu import configured_batch_size
from ghost_backend.twod.operators import _assembly_tile_size

class Qualification(unittest.TestCase):
 def test_actual_graded_interval_cap(self):
  a,b=np.array([0.,0.]),np.array([10.,0.])
  for protected in (set(),{point_key(a)},{point_key(b)},{point_key(a),point_key(b)}):
   _,p=panel_parameters({'_2d_hp_coarsening':8},0,a,b,80,False,1,protected,max_panel_length=.3)
   self.assertLessEqual(np.max(np.linalg.norm(np.diff(p,axis=0),axis=1)),.3*(1+1e-13))
   np.testing.assert_array_equal(p[[0,-1]],np.array([a,b]))
 def test_fixed_count_preserved(self):
  _,p=panel_parameters({'_2d_hp_coarsening':8},0,np.array([0.,0.]),np.array([10.,0.]),4,True,1,set(),max_panel_length=.1)
  self.assertEqual(len(p),5)
 def test_cap_cannot_bypass_panel_limit(self):
  with self.assertRaisesRegex(ValueError,'panel limit'):
   panel_parameters({},0,np.array([0.,0.]),np.array([10.,0.]),2,False,1,set(),max_panels=5,max_panel_length=.1)
 def test_both_media_and_nonfinite(self):
  mesh=NS(elements=[NS(length=1.)])
  self.assertTrue(panel_qualification(mesh,[NS(k_plus=3.,k_minus=2.)])['qualified'])
  for k in (3.001,complex(2.5,2.),float('inf'),float('nan')):
   self.assertFalse(panel_qualification(mesh,[NS(k_plus=k,k_minus=k)])['qualified'])
  self.assertFalse(panel_qualification(mesh,[])['qualified'])
  self.assertFalse(panel_qualification(mesh,[NS(k_plus=1.,k_minus=float('nan'))])['qualified'])
 def test_certificate_fails_closed(self):
  for metadata in ({},{'quadrature_qualification':[dict(qualified=False)]}):
   with self.assertRaisesRegex(ValueError,'quadrature is not qualified'):
    S._require_quadrature_qualification(dict(metadata=metadata),'base')
 def test_base_and_fine_guards_before_comparison(self):
  good=dict(metadata=dict(quadrature_qualification=[dict(qualified=True)]))
  bad=dict(metadata=dict(quadrature_qualification=[dict(qualified=False)]))
  for pair in ((good,bad),(bad,good)):
   with self.assertRaisesRegex(ValueError,'quadrature is not qualified'):
    S._certify_2d_results(*pair,{})

class Operator:
 def __init__(self,a):self.a=a;self.widths=[]
 def range_matmul(self,r0,r1,c0,c1,x,adjoint=False):
  self.widths.append(x.shape[1]);a=self.a[r0:r1,c0:c1]
  return (a.conj().T if adjoint else a)@x
 def range_workspace_bytes(self,r0,r1,c0,c1,width,adjoint=False):return width*777

class Projection(unittest.TestCase):
 def test_rectangular_shapes_ranks_and_complete_output(self):
  rng=np.random.default_rng(65)
  for m,n,k in ((31,17,0),(31,17,1),(31,17,64),(70,87,65),(123,93,193)):
   a=rng.normal(size=(m,n))+1j*rng.normal(size=(m,n))
   q=rng.normal(size=(m,k))+1j*rng.normal(size=(m,k))
   op=Operator(a);block=_RangeBlock(op,0,m,0,n,lambda:None)
   np.testing.assert_allclose(block.project(q),q.conj().T@a,rtol=2e-12,atol=2e-12)
   self.assertLessEqual(max(op.widths,default=0),64)
   self.assertEqual(block.product_workspace(k),k*777)
   self.assertEqual(block.product_workspace(k,True),max(min(k,64)*777,32*n*min(k,64)))
 def test_cancellation_between_columns(self):
  calls=[]
  def cancel():
   calls.append(1)
   if len(calls)==2:raise InterruptedError('cancel')
  op=Operator(np.eye(130,dtype=complex));block=_RangeBlock(op,0,130,0,130,cancel)
  with self.assertRaises(InterruptedError):block.project(np.eye(130,dtype=complex))
  self.assertEqual(op.widths,[64])
 def test_parallel_blocks_do_not_share_buffers(self):
  def run(seed):
   rng=np.random.default_rng(seed);a=rng.normal(size=(79,87));q=rng.normal(size=(79,131))
   block=_RangeBlock(Operator(a),0,79,0,87,lambda:None)
   np.testing.assert_allclose(block.project(q),q.T@a,atol=1e-12,rtol=1e-12)
  with ThreadPoolExecutor(3) as pool:list(pool.map(run,range(6)))

class Plans(unittest.TestCase):
 def forecast(self,cap=3.,storage='auto',scratch=True,submission=False,eligible=True,count=256):
  d=8000;matrix=16*d*d
  with execution_scope(dict(factorization='dense',dense_residual_storage=storage)), \
       patch.object(S,'_solve_memory_limit_gb',return_value=cap), \
       patch.object(DM,'scratch_available',return_value=(scratch,None if scratch else 'test disk full')):
   return DM.forecast(d,count,count,matrix+100*DM.MIB,2*matrix+16*12*d*count+128*DM.MIB,
                      32*DM.MIB,eligible,submission)
 def test_default_keeps_fast_memory_when_it_fits(self):
  p=self.forecast();self.assertEqual(p['residual_storage'],'memory');self.assertTrue(p['allow_optional_partner'])
 def test_disk_plan_fits_previously_rejected_cap(self):
  p=self.forecast(cap=2.);self.assertEqual(p['residual_storage'],'disk');self.assertLess(p['peak_bytes'],2*DM.GIB)
  self.assertEqual(p['temporary_disk_bytes'],16*8000**2);self.assertFalse(p['allow_optional_partner'])
 def test_low_cap_narrows_batch(self):
  p=self.forecast(cap=1.45);self.assertLess(p['angle_batch_size'],256);self.assertLess(p['peak_bytes'],1.45*DM.GIB)
 def test_explicit_memory_is_honored(self):
  p=self.forecast(cap=1.5,storage='memory');self.assertEqual(p['residual_storage'],'memory');self.assertGreater(p['peak_bytes'],1.5*DM.GIB)
 def test_disk_failure_cannot_make_forecast_lean(self):
  for mode in ('auto','disk'):
   p=self.forecast(cap=1.5,storage=mode,scratch=False)
   self.assertEqual(p['residual_storage'],'memory');self.assertEqual(p['temporary_disk_bytes'],0)
   self.assertGreater(p['peak_bytes'],1.5*DM.GIB)
 def test_memory_backed_scratch_is_not_a_ram_saving(self):
  if Path('/dev/shm').is_dir():
   self.assertFalse(DM.disk_backed_scratch('/dev/shm'))
  with patch.object(DM,'disk_backed_scratch',return_value=False):
   ok,reason=DM.scratch_available(16*8000**2)
   self.assertFalse(ok);self.assertIn('RAM-backed',reason)
 def test_remote_forecast_does_not_assume_local_scratch(self):
  p=self.forecast(cap=1.5,storage='disk',submission=True)
  self.assertEqual(p['residual_storage'],'memory');self.assertFalse(p['scratch_checked'])
 def test_noneligible_matrix_keeps_full_estimate(self):
  p=self.forecast(cap=1.5,eligible=False);self.assertEqual(p['residual_storage'],'memory')
 def test_batch_tile_and_partner_consume_same_plan(self):
  p=self.forecast(cap=1.45)
  with execution_scope(dict(factorization='dense')),MB._STATE.override(NS(plan=p)):
   self.assertEqual(configured_batch_size(),p['angle_batch_size'])
   self.assertEqual(configured_batch_size(planned=False),256)
   self.assertEqual(_assembly_tile_size(8000,312),128)
   self.assertGreater(_assembly_tile_size(8000,312,planned=False),128)
   self.assertFalse(DM.pair(8000,True));self.assertEqual(p['partner_matrix_bytes'],0)
  self.assertIsNone(DM.current())
 def test_cache_identity_uses_effective_tile(self):
  from ghost_backend.execution.cpu import _assembly_rule_key
  p=self.forecast(cap=1.45)
  with execution_scope(dict(factorization='dense')):
   old=_assembly_rule_key()
   with MB._STATE.override(NS(plan=p)):
    self.assertNotEqual(old,_assembly_rule_key())
    with execution_scope(dict(factorization='dense',assembly_tile=77)):
     self.assertEqual(DM.assembly_tile_setting(),77)
     self.assertEqual(_assembly_tile_size(8000,312),77)
 def test_partner_accounted_once(self):
  p=self.forecast();peak=p['peak_bytes']
  with MB._STATE.override(NS(plan=p)):
   self.assertTrue(DM.pair(8000,True));self.assertTrue(DM.pair(8000,True))
   self.assertEqual(p['peak_bytes'],peak+p['matrix_bytes'])
   self.assertFalse(DM.pair(8000,False));self.assertEqual(p['peak_bytes'],peak)
 def test_live_workspace_refusal(self):
  p=self.forecast(cap=1.45)
  with MB._STATE.override(NS(plan=p)),patch.object(S,'_process_rss_bytes',return_value=int(1.44*DM.GIB)), \
       patch.object(S,'_solve_memory_limit_gb',return_value=1.45):
   with self.assertRaisesRegex(MemoryError,'workspace'):
    DM.admit_spool(MatrixStub())
 def test_thread_local_plan(self):
  def run(cap):
   p=self.forecast(cap)
   with MB._STATE.override(NS(plan=p)):
    return DM.current()['capacity_bytes']
  # Forecast mocking is process-wide; isolate only the request-owned plan here.
  plans=[self.forecast(cap) for cap in (1.45,2.,3.)]
  def inspect(p):
   with MB._STATE.override(NS(plan=p)):return DM.current()['capacity_bytes']
  with ThreadPoolExecutor(3) as pool:self.assertEqual(list(pool.map(inspect,plans)),[p['capacity_bytes'] for p in plans])

# len() resolves on the type, not a SimpleNamespace instance attribute.
class MatrixStub:
 nbytes=16*8000**2
 def __len__(self):return 8000
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 out=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).parent/'results'
 (out/'plan-tests.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors)),indent=2)+'\n')
 sys.exit(not result.wasSuccessful())
