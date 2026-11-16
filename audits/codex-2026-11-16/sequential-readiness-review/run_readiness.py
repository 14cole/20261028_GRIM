"""Fresh physical threading/cancellation checks of the reviewed HMatrix prototype."""
import os,sys,json,time,threading,weakref,gc,traceback,resource
from pathlib import Path
import numpy as np
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,support_radius,
    CPUState,_STATE,cpu_allocation_scope,execution_scope,dielectric,op,exact_rows,DenseFactor,HMatrixFactor)
from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
from ghost_backend.compressed.hmatrix import _ProductExecutor,_PRODUCT_EXECUTOR
from ghost_backend.compressed.construction import Construction
from ghost_backend.execution import memory_budget as mb
import corrected_builder,gather_v2
spec=json.loads(sys.argv[1]);out=Path(spec['out']);started=time.perf_counter()
record=dict(spec=spec,production_changed=False,mesh_certified=False)
workers=set();lock=threading.Lock();stats=dict(tasks=0,active=0,max_active=0,cancel_requested=False,build_active=False)
refs=[];cancel_enabled=bool(spec.get('cancel'));recovered=False
class RequestedCancellation(InterruptedError):pass
def checkpoint():
    if cancel_enabled and stats['cancel_requested']:
        with lock:record['active_tasks_when_cancel_observed']=stats['active']
        raise RequestedCancellation('Injected during threaded inverse range products')
if spec['method']=='compressed':
    corrected_builder.install(dict(builder=spec['builder'],packing='none'))
    gather_v2.install()
    step0=Construction.step
    def priced(self,label,additional,*live):
        if label=='leaf coefficients' and isinstance(self.owner,HMatrixSystem):additional=2*int(additional)+2**20
        return step0(self,label,additional,*live)
    Construction.step=priced
    init0=HMatrixSystem.__init__
    def init(self,*a,**kw):
        refs.append(weakref.ref(self));stats['build_active']=True
        try:return init0(self,*a,**kw)
        finally:stats['build_active']=False
    HMatrixSystem.__init__=init
    map0=_ProductExecutor.map
    def measured(self,fn,items):
        def call(item):
            with lock:
                workers.add(threading.current_thread().name);stats['tasks']+=1;stats['active']+=1
                stats['max_active']=max(stats['max_active'],stats['active'])
                if cancel_enabled and stats['build_active'] and stats['tasks']>=12:stats['cancel_requested']=True
            try:return fn(item)
            finally:
                with lock:stats['active']-=1
        return map0(self,call,items)
    _ProductExecutor.map=measured
    inverse0=HMatrixFactor.inverse;calls=[]
    def inverse(self,b,trans=0,*a,**kw):
        before=self.event['refinement_steps']
        try:return inverse0(self,b,trans,*a,**kw)
        finally:calls.append(dict(phase=getattr(self,'_solve_phase','unknown'),trans=int(trans),columns=np.asarray(b).shape[-1] if np.asarray(b).ndim==2 else 1,corrections=self.event['refinement_steps']-before))
    HMatrixFactor.inverse=inverse
state=CPUState(kernel_only=True);state.reuse_operators=False
threads=spec['threads'];n=2048;k=40.;eps=3-.08j;angles=np.linspace(-90,90,180,endpoint=False)
mesh=mesh_for(n,'star');coords=np.tile(np.array([v.xy for v in mesh.nodes]),(2,1))
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');diagnostics={};error=None
try:
 with _STATE.override(state),mb.scope(wanted_gib=8) as ledger,cpu_allocation_scope(threads),execution_scope({'assembly_threads':threads,'blas_threads':1,'ram_budget_gib':8.,'dense_residual_storage':'memory','factorization':'dense'}):
    t=time.perf_counter()
    h=dielectric.assemble_system(mesh,[info],'TE',k) if spec['method']=='dense' else HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=4*2**30,checkpoint=checkpoint)
    record['assembly_seconds']=time.perf_counter()-t
    def factor():
        return DenseFactor(h,diagnostics=diagnostics,force_double=True,owned_matrix=True) if spec['method']=='dense' else HMatrixFactor(h,diagnostics=diagnostics,storage_budget_bytes=4*2**30,checkpoint=checkpoint)
    if cancel_enabled:
        caught=False
        try:factor()
        except RequestedCancellation as exc:record['cancel_exception']=str(exc);caught=True
        assert caught,'Cancellation trigger was not reached'
        cancel_enabled=False;gc.collect()
        live_threads=[t.name for t in threading.enumerate() if t.name.startswith('ghost-hmatrix')]
        live_builds=sum(r() is not None for r in refs)
        record['cancel_cleanup']=dict(pending_bytes=ledger.pending_construction_bytes,live_threads=live_threads,
            live_failed_inverse_objects=live_builds,executor_context_reset=_PRODUCT_EXECUTOR.get() is None,
            task_count=stats['tasks'],max_active=stats['max_active'],active_after=stats['active'])
        assert ledger.pending_construction_bytes==0 and not live_threads and live_builds==0 and _PRODUCT_EXECUTOR.get() is None and stats['active']==0
        recovered=True
    t=time.perf_counter();fac=factor();record['factor_seconds']=time.perf_counter()-t
    b=dielectric.rhs_many(mesh,k,angles);x=fac.solve(b)
    field=op._farfield_linear_density_many(mesh,x[:n],k,angles,'DLP',projection='matched')+1j*k*op._farfield_linear_density_many(mesh,x[:n],k,angles,'SLP',projection='matched')
    rows=np.sort(np.random.default_rng(6149).choice(2*n,96,replace=False));exact,query=exact_rows(oracle,rows,2*n);norm=np.sum(abs(exact),axis=1)
    residual=exact@x-b[rows];back=np.max(abs(residual)/(norm[:,None]*np.max(abs(x),axis=0)+abs(b[rows])),axis=0)
    assert np.isfinite(x).all() and np.isfinite(field).all() and np.max(back)<1e-12
    assert np.isfinite(diagnostics['condition_est'])
    np.savez_compressed(str(out)+'-batch0000.npz',angles=angles,density=x,rhs=b,field=field,rows=rows,residual=residual,row_norm=norm)
    record.update(diagnostics=diagnostics,event=fac.event,exact_row_max_backward_error=float(np.max(back)),exact_query=query,
        recovered_after_cancel=recovered,pending_after_solve=ledger.pending_construction_bytes,
        live_threads_after_solve=[t.name for t in threading.enumerate() if t.name.startswith('ghost-hmatrix')])
    assert ledger.pending_construction_bytes==0 and not record['live_threads_after_solve']
    if spec['method']=='compressed':
        record['hooks']=corrected_builder.RECORD;record['inverse_calls']=calls
        if threads>1:assert len(workers)>=2,workers
    else:
        assert fac.lu is not None and fac.hierarchical is None and fac.mixed is None
        fac.close()
except Exception:
    error=traceback.format_exc();record['error']=error
finally:
    record.update(worker_names=sorted(workers),worker_statistics=stats,wall_seconds=time.perf_counter()-started,
        peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)
    out.with_suffix('.json').write_text(json.dumps(record,indent=2,default=str))
    print(json.dumps(dict(label=out.name,error=error,seconds=record['wall_seconds'])),flush=True)
if error:raise SystemExit(2)
