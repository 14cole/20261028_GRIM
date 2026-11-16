"""Fresh slot lifecycle checks; injected failures select real production branches."""
import os,sys,json,time,traceback,threading,gc,weakref
from pathlib import Path
from contextlib import contextmanager
spec=json.loads(sys.argv[1]);out=Path(spec['out'])
if spec['variant']=='original':os.environ['GRIM_ROOT']=os.environ['BASE_GRIM_ROOT']
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
import numpy as np
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,HMatrixFactor,HMatrixSystem,
    support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope,dielectric,op,exact_rows,DenseFactor)
from ghost_backend.execution import memory_budget as mb
from ghost_backend.compressed.construction import Construction
from ghost_backend.compressed.hmatrix import _PRODUCT_EXECUTOR
from ghost_backend.linalg.hierarchical import HierarchicalRejected
from ghost_backend.compressed import preconditioner_hints
started=time.perf_counter();record=dict(spec=spec,solves=[],snapshots=[],build_tolerances=[],faults=[])
state=dict(cancel=False,labels=[],ticks=0);refs=[]
class Cancel(InterruptedError):pass
def checkpoint():
    if state['cancel'] and 'inverse child product' in state['labels']:
        state['ticks']+=1
        if state['ticks']==4:raise Cancel('Injected inside inverse child solve')
step0=Construction.step
@contextmanager
def step(self,label,additional,*live):
    state['labels'].append(label)
    try:
        with step0(self,label,additional,*live):yield
    finally:state['labels'].pop()
Construction.step=step
init0=HMatrixSystem.__init__
def init(self,*a,**kw):refs.append(weakref.ref(self));return init0(self,*a,**kw)
HMatrixSystem.__init__=init
build0=HMatrixFactor._build
def tracked_build(self,tol):record['build_tolerances'].append(float(tol));return build0(self,tol)
HMatrixFactor._build=tracked_build
cpu=CPUState(kernel_only=True);cpu.reuse_operators=False
n=1024;k=20.;eps=3-.08j;mesh=mesh_for(n,'slot');coords=np.tile(np.array([v.xy for v in mesh.nodes]),(2,1))
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');error=None
try:
 with _STATE.override(cpu),mb.scope(wanted_gib=8) as ledger,cpu_allocation_scope(2),execution_scope({'assembly_threads':2,'blas_threads':1,'ram_budget_gib':8.,'factorization':'dense','dense_residual_storage':'memory'}):
    dense=spec['scenario']=='dense'
    h=dielectric.assemble_system(mesh,[info],'TE',k) if dense else HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=4*2**30,checkpoint=checkpoint)
    rows=np.sort(np.random.default_rng(2026111609).choice(2*n,96,replace=False));exact,query=exact_rows(oracle,rows,2*n);norm=np.sum(abs(exact),axis=1)
    record['exact_query']=query
    def fresh():return HMatrixFactor(h,diagnostics={} if spec.get('condition') else None,checkpoint=checkpoint,storage_budget_bytes=4*2**30)
    def snap(f,label):
        record['snapshots'].append(dict(label=label,tolerance=f.tolerance,inverse_bytes=int(f.factor.bytes) if f.factor is not None else None,
            upgrade_attempted=getattr(f,'_upgrade_attempted',False),tightened=getattr(f,'tightened',False),pending_bytes=ledger.pending_construction_bytes))
    def solve(f,label,count):
        angles=np.linspace(-90,90,count,endpoint=False);b=dielectric.rhs_many(mesh,k,angles)
        before=f.event.get('refinement_steps',0);t=time.perf_counter();x=f.solve(b);elapsed=time.perf_counter()-t
        field=op._farfield_linear_density_many(mesh,x[:n],k,angles,'DLP',projection='matched')+1j*k*op._farfield_linear_density_many(mesh,x[:n],k,angles,'SLP',projection='matched')
        residual=exact@x-b[rows];back=np.max(abs(residual)/(norm[:,None]*np.max(abs(x),axis=0)+abs(b[rows])),axis=0)
        assert np.isfinite(x).all() and np.isfinite(field).all() and np.max(back)<1e-12
        np.savez_compressed(str(out)+'-'+label+'.npz',angles=angles,rhs=b,density=x,field=field,rows=rows,row_norm=norm,residual=residual)
        record['solves'].append(dict(label=label,count=count,seconds=elapsed,corrections=f.event.get('refinement_steps',0)-before,
            tolerance=None if dense else f.tolerance,inverse_bytes=None if dense else int(f.factor.bytes),
            max_exact_backward_error=float(np.max(back)),upgrade_attempted=getattr(f,'_upgrade_attempted',False),
            event=json.loads(json.dumps(f.event,default=str)),diagnostics=f.diagnostics))
        assert ledger.pending_construction_bytes==0
        return x
    if dense:
        f=DenseFactor(h,diagnostics={},force_double=True,owned_matrix=True)
        assert f.hierarchical is None and f.mixed is None
        solve(f,'dense16',16);solve(f,'dense180',180);f.close()
    elif spec['scenario']=='hint_failure':
        hint_calls=[0]
        def hint(f):
            hint_calls[0]+=1
            if hint_calls[0]>1:return False
            f._hint_attempted=True;f._build(1e-10);f.event['preconditioner_hint']={'accepted':True,'test_injected':True};return True
        preconditioner_hints.try_build=hint
        f=fresh();orig_refine=f._refine;injected=[False]
        def rejected(b,trans):
            if not injected[0]:injected[0]=True;record['faults'].append('One injected hinted refinement rejection');raise HierarchicalRejected('Injected hinted solve rejection')
            return orig_refine(b,trans)
        f._refine=rejected
        solve(f,'fallback1',16);solve(f,'fallback2',16)
        assert f._hint_failed and f._upgrade_attempted and f.tolerance==1e-8
        assert record['build_tolerances']==[1e-10,1e-8],record['build_tolerances']
    else:
        count=spec.get('count',16);f=fresh();snap(f,'initial');control=solve(f,'initial',count);solve(f,'stable',count)
        assert f.tolerance==1e-10 and f._upgrade_attempted
        if spec['scenario']=='cancel':
            refs.clear();state['cancel']=True;caught=False
            try:f._fresh_build()
            except Cancel:caught=True
            state['cancel']=False;gc.collect();assert caught
            cleanup=dict(factor_is_none=f.factor is None,attempt_still_consumed=f._upgrade_attempted,pending_bytes=ledger.pending_construction_bytes,
                live_failed_inverses=sum(r() is not None for r in refs),workers=[t.name for t in threading.enumerate() if t.name.startswith('ghost-')],executor_reset=_PRODUCT_EXECUTOR.get() is None)
            record['cancel_cleanup']=cleanup
            assert cleanup['factor_is_none'] and cleanup['attempt_still_consumed'] and cleanup['pending_bytes']==0 and cleanup['live_failed_inverses']==0 and not cleanup['workers'] and cleanup['executor_reset']
        if spec['scenario']=='tighten':
            old_sampler=f.sampled_errors;fired=[False]
            def reject_sample(x,b):
                if not fired[0]:fired[0]=True;record['faults'].append('One injected sample-row rejection to trigger real operator tightening');return np.ones(b.shape[1])
                return old_sampler(x,b)
            f.sampled_errors=reject_sample
            solve(f,'rebuilt',count);assert f.tightened and fired[0]
        else:
            f._fresh_build();snap(f,'after_rebuild');solve(f,'rebuilt',count)
        solve(f,'rebuilt_stable',count);record['final_diagnostics']=f.diagnostics
        f2=fresh();solve(f2,'new_factor_same_operator',count)
    record['pending_after']=ledger.pending_construction_bytes
    record['workers_after']=[t.name for t in threading.enumerate() if t.name.startswith('ghost-')]
    assert record['pending_after']==0 and not record['workers_after']
except Exception:
    error=traceback.format_exc();record['error']=error
finally:
    record['wall_seconds']=time.perf_counter()-started;out.with_suffix('.json').write_text(json.dumps(record,indent=2,default=str))
    print(json.dumps(dict(case=out.name,error=error,seconds=record['wall_seconds'])),flush=True)
if error:raise SystemExit(2)
