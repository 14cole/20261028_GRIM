"""Reviewer harness: threaded determinism and phase-targeted cancellation/recovery of the
HMatrix inverse build. Written before reading Codex's run_readiness.py.
argv: json spec {name,n,kind,k,threads,builder('production'|'sequential'),out}"""
import os,sys,json,gc,time,threading,weakref,traceback
from contextlib import contextmanager
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,HMatrixFactor,HMatrixSystem,support_radius,
    CPUState,_STATE,cpu_allocation_scope,execution_scope,dielectric,exact_rows)
from ghost_backend.compressed.construction import Construction
from ghost_backend.execution import memory_budget as mb
spec=json.loads(sys.argv[1]);out=Path(spec['out']);T=int(spec['threads'])
# integrated production tree: no research hooks
class Cancel(InterruptedError):pass
state=dict(labels=[],target=None,count=0,trigger=0,fired=None,worker_names=set(),systems=[],active=0,need_active=False,task_threads=set(),tasks_started=0,tasks_finished=0)
lock=threading.Lock()
from ghost_backend.compressed import hmatrix as _hm
map0=_hm._ProductExecutor.map
def _map(self,function,items):
    def tracked(item):
        with lock:state['active']+=1;state['tasks_started']+=1;state['task_threads'].add(threading.current_thread().name)
        try:return function(item)
        finally:
            with lock:state['active']-=1;state['tasks_finished']+=1
    return map0(self,tracked,items)
_hm._ProductExecutor.map=_map
step0=Construction.step
@contextmanager
def step(self,label,additional,*live):
    state['labels'].append(label)
    try:
        with step0(self,label,additional,*live):yield
    finally:state['labels'].pop()
Construction.step=step
def checkpoint():
    me=threading.current_thread().name
    if me!='MainThread':state['worker_names'].add(me)
    if state['target'] is not None and state['fired'] is None and state['target'] in state['labels']:
        state['count']+=1
        if state['count']>=state['trigger'] and (state['active']>0 or not state['need_active']):
            state['fired']=dict(label_stack=list(state['labels']),raising_thread=me,
                live_threads=sorted(t.name for t in threading.enumerate() if t.name!='MainThread'),active_product_tasks=state['active'],tasks_started=state['tasks_started'],tasks_finished=state['tasks_finished'],checkpoint_calls_in_phase=state['count'])
            raise Cancel('reviewer cancellation in '+state['target'])
init0=HMatrixSystem.__init__
def init(self,*a,**k):
    state['systems'].append(weakref.ref(self));return init0(self,*a,**k)
HMatrixSystem.__init__=init
def workers_alive():return sorted(t.name for t in threading.enumerate() if t.name.startswith('ghost-'))
record=dict(spec=spec,phases=[]);n=spec['n'];k=float(spec['k']);eps=3-.08j
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(T),execution_scope({'assembly_threads':T,'blas_threads':1}):
    mesh=mesh_for(n,spec['kind']);info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');nd=2*n
    t=time.perf_counter();h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30,checkpoint=checkpoint);record['assembly_seconds']=time.perf_counter()-t
    record['ledger_state_present']=mb.current() is not None
    angles=np.linspace(-90,90,16,endpoint=False);b=dielectric.rhs_many(mesh,k,angles)
    sample=np.sort(np.random.default_rng(20261116).choice(nd,96,False));exact,_=exact_rows(oracle,sample,nd);rownorm=np.sum(abs(exact),axis=1)
    def backward(x):return float(np.max(abs(exact@x-b[sample])/(rownorm[:,None]*np.max(abs(x),axis=0)[None,:]+abs(b[sample]))))
    def fresh():return HMatrixFactor(h,checkpoint=checkpoint,storage_budget_bytes=12*2**30)
    state['task_threads'].clear();fac=fresh();control=fac.solve(b);record['control']=dict(backward_error=backward(control),inverse_bytes=int(fac.factor.bytes),
        refinement_steps=fac.event['refinement_steps'],product_task_threads=sorted(state['task_threads']),operator_bytes=int(h.bytes))
    np.savez(str(out)+'-control.npz',density=control,rhs=b,angles=angles,rows=sample,residual=exact@control-b[sample],row_norm=rownorm)
    phases=[('sample products',6),('leaf coefficients',3),('Woodbury correction',3),('projected QR',3)]
    phases.append(('inverse child product (in place)',4))
    for mode in ('new_factor','same_factor'):
        for label,trigger in (phases if mode=='new_factor' else phases[-1:]):
            del state['systems'][:];state.update(target=label,count=0,trigger=trigger,fired=None,need_active=(label=='sample products' and T>1),tasks_started=0,tasks_finished=0);state['worker_names'].clear();state['task_threads'].clear()
            op_bytes=int(h.bytes);pending0=getattr(mb.current(),'pending_construction_bytes',None);raised=None
            try:
                if mode=='new_factor':victim=fresh();del victim
                else:fac._fresh_build()
            except Cancel as e:raised='Cancel'
            except BaseException as e:raised=type(e).__name__+': '+str(e)[:200]
            fired=state['fired'];state['target']=None
            sys.last_traceback=None;gc.collect();gc.collect()
            entry=dict(mode=mode,target=label,trigger=trigger,raised=raised,fired=fired,
                product_task_threads=sorted(state['task_threads']),active_tasks_after=state['active'],tasks_started_total=state['tasks_started'],tasks_finished_total=state['tasks_finished'],workers_alive_after=workers_alive(),
                inverse_objects_started=len(state['systems']),inverse_objects_alive_after_gc=sum(r() is not None for r in state['systems']),
                operator_bytes_unchanged=int(h.bytes)==op_bytes,pending_construction_bytes=(pending0,getattr(mb.current(),'pending_construction_bytes',None)),
                same_factor_inverse_is_none=(fac.factor is None) if mode=='same_factor' else None)
            try:
                if mode=='new_factor':rec=fresh()
                else:fac._fresh_build();rec=fac
                x=rec.solve(b);entry.update(recovered=True,bitwise_equal_control=bool(np.array_equal(x,control)),max_abs_diff=float(np.max(abs(x-control))),
                    backward_error=backward(x),inverse_bytes=int(rec.factor.bytes))
                if mode=='new_factor':del rec
            except BaseException as e:entry.update(recovered=False,recovery_error=traceback.format_exc()[-800:])
            record['phases'].append(entry);print(json.dumps({k_:v for k_,v in entry.items() if k_!='fired'}),flush=True);print('   fired',json.dumps(fired),flush=True)
Path(str(out)+'.json').write_text(json.dumps(record,indent=1))
