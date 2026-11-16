"""Reviewer lifecycle tests of the inverse-upgrade policy. Production code only (no research hooks).
Run once per source tree (GRIM_ROOT). argv: json {n,kind,k,out}. Written before reading Codex's run_slot.py."""
import os,sys,json,gc,weakref
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,HMatrixFactor,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope,dielectric,exact_rows)
from ghost_backend.compressed.factor import CompressedFactor
import ghost_backend.compressed.factor as factor_module
spec=json.loads(sys.argv[1]);out=Path(spec['out']);n=spec['n'];k=float(spec['k']);eps=3-.08j;rec=dict(spec=spec,source=str(Path(factor_module.__file__)))
attempts=[];up0=CompressedFactor._upgrade_preconditioner
def up(self):
    before=getattr(self,'_upgrade_attempted',False);tol=self.tolerance;r=up0(self)
    attempts.append(dict(flag_before=bool(before),tolerance_before=tol,returned=bool(r),reason=(self.event.get('preconditioner_upgrade') or {}).get('reason') if not before else 'flag already set'))
    return r
CompressedFactor._upgrade_preconditioner=up
class Cancel(InterruptedError):pass
arm=dict(on=False,count=0,at=0)
def checkpoint():
    if arm['on']:
        arm['count']+=1
        if arm['count']>=arm['at']:arm['on']=False;raise Cancel('reviewer cancel')
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(2),execution_scope({'assembly_threads':2,'blas_threads':1}):
    mesh=mesh_for(n,spec['kind']);info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));oracle=NativeOracle(mesh,[info],'TE',k,'dielectric');nd=2*n
    h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30,checkpoint=checkpoint)
    b=dielectric.rhs_many(mesh,k,np.linspace(-90,90,16,endpoint=False))
    sample=np.sort(np.random.default_rng(1116).choice(nd,96,False));exact,_=exact_rows(oracle,sample,nd);rownorm=np.sum(abs(exact),axis=1)
    def bwd(x):return float(np.max(abs(exact@x-b[sample])/(rownorm[:,None]*np.max(abs(x),axis=0)[None,:]+abs(b[sample]))))
    arrays={}
    def solve(f,label,store):
        r0=f.event['refinement_steps'];a0=len(attempts);x=f.solve(b);arrays[label]=x
        store.append(dict(step=label,corrections=f.event['refinement_steps']-r0,tolerance=f.tolerance,inverse_bytes=int(f.factor.bytes),factorizations=f.event['factorizations'],
            flag=bool(getattr(f,'_upgrade_attempted',False)),upgrade_calls=len(attempts)-a0,backward_error=bwd(x)));return x
    def fresh():return HMatrixFactor(h,checkpoint=checkpoint,storage_budget_bytes=12*2**30)
    # A/B: ordinary sequence
    seq=[];f=fresh();seq.append(dict(step='constructed',tolerance=f.tolerance,factorizations=f.event['factorizations'],flag=bool(getattr(f,'_upgrade_attempted',False))))
    solve(f,'first',seq);solve(f,'stable',seq);f._fresh_build();seq.append(dict(step='_fresh_build',tolerance=f.tolerance,factorizations=f.event['factorizations'],flag=bool(getattr(f,'_upgrade_attempted',False))))
    solve(f,'rebuilt',seq);solve(f,'rebuilt_stable',seq)
    g=fresh();solve(g,'new_first',seq);solve(g,'new_stable',seq)
    rec['sequence']=seq;rec['upgrades_naturally']=bool(seq[1]['tolerance']<seq[0]['tolerance'])
    rec['rebuilt_stable_bitwise_equal_stable']=bool(np.array_equal(arrays['rebuilt_stable'],arrays['stable']));rec['new_stable_bitwise_equal_stable']=bool(np.array_equal(arrays['new_stable'],arrays['stable']))
    rec['rebuilt_stable_vs_stable_relL2']=float(np.max(np.linalg.norm(arrays['rebuilt_stable']-arrays['stable'],axis=0)/np.linalg.norm(arrays['stable'],axis=0)))
    np.savez(str(out)+'-first-two.npz',first=arrays['first'],stable=arrays['stable'],rhs=b)
    # D: cancelled in-object rebuild on the (possibly upgraded) factor g
    flag0=bool(getattr(g,'_upgrade_attempted',False));ref=weakref.ref(g.factor);arm.update(on=True,count=0,at=25);raised=None
    try:g._fresh_build()
    except Cancel:raised='Cancel'
    arm['on']=False;gc.collect()
    can=dict(raised=raised,flag_before=flag0,flag_after_cancel=bool(getattr(g,'_upgrade_attempted',False)),inverse_is_none=g.factor is None,old_inverse_collected=ref() is None,steps=[])
    g._fresh_build();can['flag_after_successful_rebuild']=bool(getattr(g,'_upgrade_attempted',False));solve(g,'cancel_recovered',can['steps']);solve(g,'cancel_recovered_stable',can['steps'])
    can['recovered_stable_bitwise_equal_stable']=bool(np.array_equal(arrays['cancel_recovered_stable'],arrays['stable']));rec['cancel']=can
    # C: adversarial - upgrade always denied by budget
    adv=[];a=fresh();a.budget=int(2*a.factor.bytes);del attempts[:]
    for i in range(3):solve(a,f'denied_{i}',adv)
    a._fresh_build();a.budget=int(2*a.factor.bytes)
    for i in range(3):solve(a,f'denied_after_rebuild_{i}',adv)
    a._fresh_build();a.budget=int(2*a.factor.bytes)
    for i in range(2):solve(a,f'denied_after_second_rebuild_{i}',adv)
    rec['adversarial']=dict(steps=adv,upgrade_calls=list(attempts),total_factorizations=a.event['factorizations'],
        real_attempts=sum(1 for t in attempts if not t['flag_before']),bitwise_all_equal=bool(all(np.array_equal(arrays['denied_0'],arrays[s['step']]) for s in adv)))
rec['max_backward_error']=max(s['backward_error'] for s in seq+can['steps']+adv if 'backward_error' in s)
Path(str(out)+'.json').write_text(json.dumps(rec,indent=1))
print(spec['kind'],2*n,'upgrades',rec['upgrades_naturally'],'seq',[(s['step'],s.get('corrections'),s['tolerance']) for s in seq],'| rebuilt==stable',rec['rebuilt_stable_bitwise_equal_stable'],'| cancel',can['raised'],can['flag_before'],can['flag_after_cancel'],can['flag_after_successful_rebuild'],[s['corrections'] for s in can['steps']],'| adv corr',[s['corrections'] for s in adv],'builds',a.event['factorizations'],'real attempts',rec['adversarial']['real_attempts'],'| bwd %.1e'%rec['max_backward_error'],flush=True)
