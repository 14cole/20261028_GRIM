"""Fresh production-code solve; wrappers observe or inject explicitly named faults."""
import os,sys,json,time,resource,threading,weakref,gc,traceback
from pathlib import Path
from contextlib import contextmanager
spec=json.loads(sys.argv[1]);out=Path(spec['out'])
if spec['variant']=='baseline':os.environ['GRIM_ROOT']=os.environ['BASE_GRIM_ROOT']
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
import numpy as np
from monostatic import mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,HMatrixFactor,HMatrixSystem,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope,dielectric,op,exact_rows,DenseFactor
from ghost_backend.compressed.hmatrix import _ProductExecutor,_PRODUCT_EXECUTOR
from ghost_backend.compressed.construction import Construction
from ghost_backend.linalg.hierarchical import HierarchicalRejected
from ghost_backend.execution import memory_budget as mb
from ghost_backend.twod.formulations import robin
import ghost_backend.twod.solver as solver
started=time.perf_counter();record=dict(spec=spec,stages={},faults=[],solutions=[],build_tolerances=[])
refs=[];worker_names=set();lock=threading.Lock();state=dict(phase=[],ticks=0,enabled=bool(spec.get('cancel')),active=0,tasks=0,max_active=0,building=False)
class Cancel(InterruptedError):pass
def checkpoint():
    if not state['enabled']:return
    phase=spec['cancel']
    if phase=='products':fire=state['building'] and state['tasks']>=12 and (not spec.get('active_cancel') or state['active']>0)
    else:
        fire=False
        if phase in state['phase']:
            state['ticks']+=1;fire=state['ticks']>=spec.get('cancel_at',4)
    if fire:
        record['cancel_active_at_checkpoint']=state['active'];raise Cancel('Injected '+phase)
step0=Construction.step
@contextmanager
def step(self,label,additional,*live):
    state['phase'].append(label)
    try:
        with step0(self,label,additional,*live):yield
    finally:state['phase'].pop()
Construction.step=step
init0=HMatrixSystem.__init__
def init(self,*a,**kw):
    refs.append(weakref.ref(self));state['building']=True
    try:return init0(self,*a,**kw)
    finally:state['building']=False
HMatrixSystem.__init__=init
map0=_ProductExecutor.map
def measured(self,fn,items):
    def work(item):
        with lock:
            worker_names.add(threading.current_thread().name);state['tasks']+=1;state['active']+=1;state['max_active']=max(state['max_active'],state['active'])
        try:return fn(item)
        finally:
            with lock:state['active']-=1
    return map0(self,work,items)
_ProductExecutor.map=measured
compress0=HMatrixSystem.compress_block;rejected=[False]
def compress(self,oracle,rows,cols):
    if spec.get('fallback') and not rejected[0] and len(rows)+len(cols)<=self.DENSE_FALLBACK_LIMIT:
        rejected[0]=True;record['faults'].append('One small-node compression rejection');raise HierarchicalRejected('Injected small-node fallback')
    return compress0(self,oracle,rows,cols)
HMatrixSystem.compress_block=compress
build0=HMatrixFactor._build
def build(self,tol):record['build_tolerances'].append(float(tol));return build0(self,tol)
HMatrixFactor._build=build
count=spec.get('count',180);n=spec.get('n',2048);k=spec.get('k',40.);eps=3-.08j;pol=spec.get('pol','TE')
mesh=mesh_for(n,spec.get('geometry','star'));kind=spec.get('kind','dielectric');nd=2*n if kind=='dielectric' else n
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0,robin_impedance=0.)
infos=[info] if kind=='dielectric' else [info]*len(mesh.elements)
coords=np.tile(np.array([v.xy for v in mesh.nodes]),(2 if kind=='dielectric' else 1,1));oracle=NativeOracle(mesh,infos,pol,k,kind)
angles=np.linspace(-90,90,count,endpoint=False);storage=spec.get('storage_mib',4096)*2**20;dense=spec.get('method')=='dense';diag={} if spec.get('condition',True) else None
state_cpu=CPUState(kernel_only=True);state_cpu.reuse_operators=False;error=None
try:
 with _STATE.override(state_cpu),mb.scope(wanted_gib=spec.get('ram_gib',8)) as ledger,cpu_allocation_scope(spec.get('threads',2)),execution_scope({'assembly_threads':spec.get('threads',2),'blas_threads':1,'ram_budget_gib':spec.get('ram_gib',8),'dense_residual_storage':'memory','factorization':'dense'}):
    t=time.perf_counter()
    h=(dielectric.assemble_system(mesh,infos,pol,k) if kind=='dielectric' else robin.assemble_system(mesh,infos,pol,k)[0]) if dense else HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=storage,checkpoint=checkpoint)
    record['stages']['assembly']=time.perf_counter()-t;print(json.dumps(dict(stage='assembly',seconds=record['stages']['assembly'])),flush=True)
    b=dielectric.rhs_many(mesh,k,angles) if kind=='dielectric' else solver._robin_bie_rhs_many(mesh,oracle.alpha,oracle.pec_nodes,pol,k,angles)
    def factor():return DenseFactor(h,diagnostics=diag,force_double=True,owned_matrix=True) if dense else HMatrixFactor(h,diagnostics=diag,storage_budget_bytes=storage,checkpoint=checkpoint)
    if state['enabled']:
        caught=False
        try:factor()
        except Cancel:caught=True
        assert caught;state['enabled']=False;gc.collect()
        cleanup=dict(pending_bytes=ledger.pending_construction_bytes,live_failed_inverses=sum(r() is not None for r in refs),
            workers=[t.name for t in threading.enumerate() if t.name.startswith('ghost-')],active=state['active'],executor_reset=_PRODUCT_EXECUTOR.get() is None)
        assert cleanup['pending_bytes']==cleanup['live_failed_inverses']==cleanup['active']==0 and not cleanup['workers'] and cleanup['executor_reset']
        record['cancel_cleanup']=cleanup
    t=time.perf_counter();fac=factor();record['stages']['factor']=time.perf_counter()-t;print(json.dumps(dict(stage='factor',seconds=record['stages']['factor'],build_tolerances=record['build_tolerances'])),flush=True)
    t=time.perf_counter();x=fac.solve(b);record['stages']['solve']=time.perf_counter()-t;print(json.dumps(dict(stage='solve',seconds=record['stages']['solve'])),flush=True)
    t=time.perf_counter()
    field=(op._farfield_linear_density_many(mesh,x[:n],k,angles,'DLP',projection='matched')+1j*k*op._farfield_linear_density_many(mesh,x[:n],k,angles,'SLP',projection='matched')) if kind=='dielectric' else op._farfield_linear_density_many(mesh,x,k,angles,'SLP',projection='matched')
    record['stages']['field']=time.perf_counter()-t;record['compute_seconds']=sum(record['stages'].values())
    record['compute_peak_gib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20
    t=time.perf_counter();rows=np.sort(np.random.default_rng(20261117).choice(nd,min(96,nd),replace=False));exact,query=exact_rows(oracle,rows,nd);norm=np.sum(abs(exact),axis=1)
    residual=exact@x-b[rows];back=np.max(abs(residual)/(norm[:,None]*np.max(abs(x),axis=0)+abs(b[rows])),axis=0)
    assert np.isfinite(x).all() and np.isfinite(field).all() and np.max(back)<1e-12
    if diag is not None:assert np.isfinite(diag['condition_est'])
    np.savez_compressed(str(out)+'-batch0000.npz',angles=angles,density=x,rhs=b,field=field,rows=rows,residual=residual,row_norm=norm)
    record.update(exact_validation_seconds=time.perf_counter()-t,exact_query=query,max_exact_backward_error=float(np.max(back)),diagnostics=diag,event=fac.event,
        operator_bytes=int(h.nbytes),pending_after=ledger.pending_construction_bytes,worker_names=sorted(worker_names),max_active=state['max_active'])
    assert ledger.pending_construction_bytes==0
    record['workers_after']=[t.name for t in threading.enumerate() if t.name.startswith('ghost-')];assert not record['workers_after']
    if spec.get('fallback'):assert rejected[0] and any(e['dense_fallbacks'] for e in fac.event['preconditioners'])
    if dense:assert fac.hierarchical is None and fac.mixed is None;fac.close()
except Exception:
    error=traceback.format_exc();record['error']=error
finally:
    record.update(wall_seconds=time.perf_counter()-started,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)
    out.with_suffix('.json').write_text(json.dumps(record,indent=2,default=str));print(json.dumps(dict(case=out.name,error=error,seconds=record['wall_seconds'])),flush=True)
if error:raise SystemExit(2)
