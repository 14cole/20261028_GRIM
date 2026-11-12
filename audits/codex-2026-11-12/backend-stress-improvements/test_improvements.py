"""Admission/ownership regressions, including the formerly inconsistent 24 GiB plan."""
import json,os,sys,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
ROOT=Path(sys.argv[1]).resolve();P=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/GHOST'))
from ghost_backend.execution.options import execution_scope,cpu_allocation_scope,option
from ghost_backend.twod import solver as S
from ghost_backend.execution import dense_memory as DM
from ghost_backend.compressed import runtime as CR,hmatrix as H
from ghost_backend.twod.formulations import dielectric as D
GIB=2**30

class DenseOwnership(unittest.TestCase):
    def forecast(self,record,submission=False):
        r=dict(nodes=4000,panels=4000,system_dofs=8000,basis_width=2,formulation='single_dielectric',**record)
        with cpu_allocation_scope(4),execution_scope(dict(factorization='dense',assembly_threads=4,dense_residual_storage='disk')),patch.object(S,'_solve_memory_limit_gb',return_value=1.8),patch.object(DM,'scratch_available',return_value=(True,None)):
            S._estimate_memory_gb(4000,False,system_dofs=8000,n_rhs=19,dense_resources=r,submission_planning=submission)
        return r['memory_estimate']
    def test_owned_matrix_allows_previously_refused_budget(self):
        old=self.forecast({});new=self.forecast(D.assembly_resources(4000))
        self.assertGreater(old['peak_bytes'],1.8*GIB)
        self.assertLess(new['peak_bytes'],1.8*GIB)
        self.assertEqual(old['phase_bytes']['assembly']-new['phase_bytes']['assembly'],16*4000**2)
    def test_unequal_rules_keep_the_operator(self):
        self.assertEqual(self.forecast({})['peak_bytes'],self.forecast(D.assembly_resources(4000,8,7))['peak_bytes'])
    def test_submission_still_prices_two_system_matrices(self):
        p=self.forecast(D.assembly_resources(4000),True)
        self.assertEqual(p['residual_storage'],'memory');self.assertFalse(p['scratch_checked'])
        self.assertGreater(p['phase_bytes']['factorization'],2*16*8000**2)
    def test_actual_assembly_matches_declared_ownership(self):
        from geometry_cases import build
        from ghost_backend.geometry.io import parse_geometry,build_geometry_snapshot
        text,_=build(dict(material='diel',shape='circle',n=64,length_m=.1,frequency_ghz=2.))
        geometry=build_geometry_snapshot(*parse_geometry(text));assemble=D.assemble_system;zeros=np.zeros
        for degree,rule in [(degree,rule) for degree in (1,2,3) for rule in ((8,8),(8,7))]:
            observations=[]
            def traced(mesh,infos,pol,k0,obs_order=8,src_order=8):
                n=len(mesh.nodes);shapes=[]
                def record(shape,*args,**kwargs):
                    if isinstance(shape,tuple) and shape in ((n,n),(2*n,2*n)):shapes.append(shape)
                    return zeros(shape,*args,**kwargs)
                resources=S._dense_formulation_resources(mesh,infos,pol,obs_order=rule[0],src_order=rule[1])
                with patch.object(np,'zeros',side_effect=record):a=assemble(mesh,infos,pol,k0,*rule)
                observations.append((n,shapes,resources));return a
            with execution_scope(dict(factorization='dense',basis_order=degree,assembly_threads=1,blas_threads=1)),patch.object(D,'assemble_system',side_effect=traced):
                result=S.solve_monostatic_rcs_2d_survey(geometry,[2.],[0.],geometry_units='meters')
            self.assertTrue(result['metadata']['quality_gate']['passed'])
            n,shapes,r=observations[0]
            self.assertIn((2*n,2*n),shapes)
            self.assertEqual((n,n) in shapes,rule[0]!=rule[1])
            self.assertEqual(r['assembly_operator_entries'],n*n if rule[0]!=rule[1] else 0)

class HierarchicalSelection(unittest.TestCase):
    def test_common_threshold_for_explicit_and_automatic(self):
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop('GHOST_HMATRIX_MIN_UNKNOWNS',None)
            for mode in ('compressed','automatic'):
                with execution_scope(dict(factorization=mode)):
                    self.assertFalse(H.selected(1023));self.assertTrue(H.selected(1024));self.assertTrue(H.selected(8000))
    def test_explicit_override_and_disable(self):
        for value,expected in [('0',False),('8192',False),('1024',True)]:
            with patch.dict(os.environ,GHOST_HMATRIX_MIN_UNKNOWNS=value),execution_scope(dict(factorization='compressed')):
                self.assertEqual(H.selected(8000),expected)
        with patch.dict(os.environ,GHOST_HMATRIX_MIN_UNKNOWNS='-1'):
            with self.assertRaises(ValueError):H.minimum_unknowns()
    def test_unsupported_oracle_stays_excluded(self):
        oracle=NS(mesh=None,get_with_error=lambda *x:None,kind='thin',B=1)
        self.assertIn('magnetic contrast',H.unsupported(oracle))
    def test_failed_explicit_request_is_not_repeated_identically(self):
        from ghost_backend.execution.options import configured_execution
        from ghost_backend.linalg.hierarchical import HierarchicalRejected
        calls=[]
        @configured_execution
        def request(solver_method):
            calls.append(1);raise HierarchicalRejected('injected rank failure')
        with self.assertRaisesRegex(HierarchicalRejected,'injected rank failure'):
            request(solver_method=S.EXPERIMENTAL_METHOD,execution_options=dict(factorization='compressed',ram_budget_gib=1.))
        self.assertEqual(len(calls),1)


    def test_automatic_retry_retains_failure_evidence(self):
        from ghost_backend.execution.options import configured_execution
        from ghost_backend.execution import selection
        calls=[]
        @configured_execution
        def request(solver_method):
            calls.append(option('factorization'))
            if len(calls)==1:raise MemoryError('injected admitted backend failure')
            return {'metadata':{}}
        chosen=dict(selected='dense',retry_order=['compressed'],reason='test')
        with patch.object(selection,'select_backend',return_value=chosen):
            result=request(solver_method=S.EXPERIMENTAL_METHOD,execution_options=dict(factorization='automatic',ram_budget_gib=1.))
        self.assertEqual(calls,['dense','compressed'])
        evidence=result['metadata']['backend_selection']
        self.assertEqual(evidence['selected'],'compressed')
        self.assertEqual(evidence['failed_attempts'][0]['error'],'MemoryError')
        self.assertGreaterEqual(evidence['failed_attempts'][0]['wall_seconds'],0)

class PairingBudget(unittest.TestCase):
    def real(self):return json.loads((P/'coated10-resources.json').read_text())
    def price(self,r,cap,storage=0,live=None,submission=False):
        r=dict(r)
        with execution_scope(dict(factorization='compressed',compressed_storage_mib=storage,ram_budget_gib=cap)),patch.object(S,'_solve_memory_limit_gb',return_value=cap):
            return CR.planned_forecast(r['nodes'],r['system_dofs'],19,19,4,r,submission_planning=submission,live_residency_bytes=live)
    def test_actual_coated10_plan_funds_predicted_payload(self):
        p=self.price(self.real(),24.)
        self.assertFalse(p['paired_assembly']);self.assertTrue(p['pairing_fixed']);self.assertTrue(p['storage_fits'])
        self.assertLess(p['peak_bytes'],24*GIB)
        self.assertGreater(p['storage_limit_bytes'],18*GIB)
        self.assertEqual(p['storage_limit_bytes'],CR.planned_storage_bytes(p,24*GIB))
    def test_cap_remainder_cannot_turn_a_separate_plan_back_into_a_pair(self):
        r=self.real();m=dict(r['hmatrix_storage']);m.update(operator_bytes=GIB,inverse_bytes=GIB,inverse_peak_bytes=int(1.2*GIB),assembly_workspace_bytes=2*GIB)
        r.update(hmatrix_storage=m,nodes=1000,system_dofs=2000)
        p=self.price(r,6.)
        # The remainder could hold two operators plus the inverse. But their
        # doubled assembly workspace would exceed the complete reservation.
        self.assertGreater(p['storage_limit_bytes'],3*GIB)
        self.assertFalse(p['paired_assembly']);self.assertLess(p['peak_bytes'],6*GIB)
        self.assertTrue(p['storage_fits'])
    def test_reservation_sweep_and_live_residency(self):
        r=self.real()
        for cap in (.5,1.,2.,4.,8.,12.,16.,20.,24.,32.,48.,64.):
            for live in (None,2*GIB):
                p=self.price(r,cap,live=live)
                self.assertEqual(p['storage_limit_bytes'],CR.planned_storage_bytes(p,int(cap*GIB)))
                if p['paired_assembly']:
                    self.assertTrue(p['storage_fits']);self.assertLessEqual(p['peak_bytes'],cap*GIB)
                resident=p['resident_operator_bytes']+p['inverse_ceiling_bytes']
                self.assertEqual(p['storage_fits'],resident<=p['storage_limit_bytes'])
    def test_explicit_cap_is_not_enlarged(self):
        p=self.price(self.real(),64.,storage=4096)
        self.assertEqual(p['storage_limit_bytes'],4096*2**20)
        self.assertFalse(p['paired_assembly']);self.assertFalse(p['storage_fits'])
    def test_submission_remains_unqualified_by_local_capacity(self):
        a=self.price(self.real(),2.,submission=True);b=self.price(self.real(),64.,submission=True)
        self.assertEqual(a,b);self.assertFalse(a['pairing_fixed'])
        self.assertEqual(a['storage_policy'],'submission_payload_forecast')
    def test_simultaneous_plans_do_not_share_pairing(self):
        def work(cap):
            with execution_scope(dict(factorization='compressed',compressed_storage_mib=0,ram_budget_gib=cap)):
                r=self.real();p=CR.planned_forecast(r['nodes'],r['system_dofs'],19,19,4,r)
                return p['paired_assembly'],p['storage_limit_bytes']
        caps=[24.,64.,24.,64.]
        with patch.object(S,'_solve_memory_limit_gb',side_effect=lambda *a:option('ram_budget_gib')):
            with ThreadPoolExecutor(4) as pool:values=list(pool.map(work,caps))
        self.assertEqual(values[0],values[2]);self.assertEqual(values[1],values[3]);self.assertNotEqual(values[0][0],values[1][0])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (P/'checks'/'improvement-tests.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors)),indent=2)+'\n')
    sys.exit(not result.wasSuccessful())
