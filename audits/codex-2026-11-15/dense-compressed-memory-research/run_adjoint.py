"""Check normal, transpose and adjoint packed solves against exact dense matrices."""
import os,sys,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
from monostatic import mesh_for,NativeOracle,support_radius,HMatrixOperator,HMatrixFactor,dielectric,SimpleNamespace,CPUState,_STATE,cpu_allocation_scope,execution_scope
from hooks import install,RECORD
spec=json.loads(sys.argv[1]);install(spec)
n=512;k=20;eps=complex(*spec.get('eps',[3,-.08]));mesh=mesh_for(n,'star')
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));rng=np.random.default_rng(90515)
b=rng.normal(size=(2*n,4))+1j*rng.normal(size=(2*n,4));records=[];arrays={'rhs':b}
state=CPUState(kernel_only=True)
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    a=dielectric.assemble_system(mesh,[info],'TE',k)
    oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
    h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=4*2**30)
    f=HMatrixFactor(h,storage_budget_bytes=4*2**30)
    for trans in (0,1,2):
        op=a if trans==0 else a.T if trans==1 else a.conj().T
        x=f.inverse(b,trans=trans);ref=np.linalg.solve(op,b)
        rel=float(np.max(np.linalg.norm(x-ref,axis=0)/np.linalg.norm(ref,axis=0)))
        backward=float(np.max(np.max(abs(op@x-b),axis=0)/(np.linalg.norm(op,np.inf)*np.max(abs(x),axis=0)+np.max(abs(b),axis=0))))
        assert rel<1e-7 and backward<1e-12
        records.append(dict(trans=trans,density_error=rel,exact_backward_error=backward))
        arrays['x'+str(trans)]=x;arrays['ref'+str(trans)]=ref
np.savez_compressed(spec['out']+'-adjoint.npz',**arrays)
Path(spec['out']+'.json').write_text(json.dumps(dict(spec=spec,checks=records,event=f.event,hooks=RECORD),indent=2))
print(json.dumps(records))
