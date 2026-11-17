"""Why do old and new trees differ at rounding level for single-column solves?
argv: label, mode ('asis' | 'fortran_e' : convert every stored e1/e2 to Fortran order after the build), out npz"""
import os,sys,json
from collections import Counter
import numpy as np
sys.path.insert(0,os.environ['MONOSTATIC_AUDIT'])
from monostatic import (mesh_for,SimpleNamespace,NativeOracle,HMatrixOperator,HMatrixFactor,HMatrixSystem,support_radius,CPUState,_STATE,cpu_allocation_scope,execution_scope,dielectric)
label,mode,out=sys.argv[1:4];n=1024;k=20.;eps=3-.08j;layouts=Counter()
def walk(node):
    if node.leaf:return
    for key in ('e1','e2','v12','v21'):
        a=getattr(node,key);layouts[(key[0],'C' if a.flags.c_contiguous and not a.flags.f_contiguous else 'F' if a.flags.f_contiguous and not a.flags.c_contiguous else 'both')]+=1
        if mode=='fortran_e' and key[0]=='e':setattr(node,key,np.asfortranarray(a))
    walk(node.left);walk(node.right)
init0=HMatrixSystem.__init__
def init(self,*a,**kw):
    init0(self,*a,**kw);walk(self.root)
HMatrixSystem.__init__=init
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
    mesh=mesh_for(n,'star');info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k*np.sqrt(eps),k_minus=k,plus_region=1,minus_region=0)
    coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1));oracle=NativeOracle(mesh,[info],'TE',k,'dielectric')
    h=HMatrixOperator(oracle,coords,radius=support_radius(mesh,coords),budget=12*2**30);b=dielectric.rhs_many(mesh,k,np.linspace(-90,90,16,endpoint=False))
    f=HMatrixFactor(h,storage_budget_bytes=12*2**30)
    r=np.random.default_rng(3);p=r.standard_normal((2*n,3))+1j*r.standard_normal((2*n,3))
    res=dict(block16=f.solve(b),single=f.solve(b[:,:1]),vector=f.solve(b[:,0]),pair=f.solve(b[:,:2]),raw_apply_1=f.factor.apply(p[:,:1],solve=True),raw_apply_3=f.factor.apply(p,solve=True),raw_adjoint_1=f.factor.apply(p[:,:1],solve=True,trans=2))
np.savez(out,**res);print(label,mode,dict(layouts))
