"""Why is same-factor recovery on the slot not bit-identical? Repeat without any cancellation."""
import os,sys,json
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,HMatrixFactor,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope,dielectric)
import gather_v2;gather_v2.install()
n=1024;k=20.;eps=3-.08j;out={}
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(2),execution_scope({'assembly_threads':2,'blas_threads':1}):
    mesh=mesh_for(n,'slot');info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
    h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30);b=dielectric.rhs_many(mesh,k,np.linspace(-90,90,16,endpoint=False))
    def snap(f):return dict(tolerance=f.tolerance,inverse_bytes=int(f.factor.bytes),refinement_steps=f.event['refinement_steps'],factorizations=f.event['factorizations'],preconditioners=len(f.event['preconditioners']),upgrade=str(f.event.get('preconditioner_upgrade'))[:200])
    f1=HMatrixFactor(h,storage_budget_bytes=12*2**30);out['fresh_before_solve']=snap(f1);x1=f1.solve(b);out['fresh_after_solve']=snap(f1)
    x1b=f1.solve(b);out['second_solve_same_factor_bitwise']=bool(np.array_equal(x1,x1b));out['after_second_solve']=snap(f1)
    f1._fresh_build();out['after_fresh_build_no_cancel']=snap(f1);x2=f1.solve(b);out['after_rebuild_solve']=snap(f1)
    out['rebuild_without_cancel_bitwise_equal_first']=bool(np.array_equal(x1,x2));out['max_abs_diff']=float(np.max(abs(x1-x2)));out['max_abs_density']=float(np.max(abs(x1)));out['max_per_angle_relative_L2_diff']=float(np.max(np.linalg.norm(x1-x2,axis=0)/np.linalg.norm(x1,axis=0)))
    x4=f1.solve(b);out['third_solve_after_rebuild']=snap(f1);out['third_solve_bitwise_equal_second']=bool(np.array_equal(x2,x4))
    f2=HMatrixFactor(h,storage_budget_bytes=12*2**30);x3=f2.solve(b);out['second_fresh_factor_bitwise_equal_first']=bool(np.array_equal(x1,x3))
print(json.dumps(out,indent=1));json.dump(out,open('out/slot_attribution.json','w'),indent=1)
