"""Alternating paired timings on one already-built physical operator/inverse."""
import os,sys,json,time,resource
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_CANDIDATE_ROOT','/workspace/backend-optimization-study/candidate')+'/tools/GHOST')
from ghost_backend.execution.cpu import CPUState,_STATE
from ghost_backend.execution.options import cpu_allocation_scope,execution_scope
from ghost_backend.compressed.coefficients import NativeOracle
from ghost_backend.compressed.hmatrix import HMatrixOperator,support_radius
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
import ghost_backend.compressed.hmatrix as hm
import ghost_backend.linalg.hierarchical as hf
from fmm_galerkin import circle_mesh
from types import SimpleNamespace
state=CPUState(kernel_only=True);state.reuse_operators=False;n=2048;k0=40;eps=3-.08j
mesh=circle_mesh(n,star=True,inward=True);coords=np.tile(np.array([x.xy for x in mesh.nodes]),(2,1))
info=SimpleNamespace(mu_minus=1.,mu_plus=1.,eps_minus=1.,eps_plus=eps,k_plus=k0*np.sqrt(eps),k_minus=k0,plus_region=1,minus_region=0)
rng=np.random.default_rng(821);b=rng.normal(size=(2*n,2))+1j*rng.normal(size=(2*n,2));candidate=hm.adjoint_product
methods={'baseline':lambda a,b:a.conj().T@b,'candidate':candidate};times=[];arrays={}
with _STATE.override(state),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 h=HMatrixOperator(NativeOracle(mesh,[info],'TE',k0,'dielectric'),coords,radius=support_radius(mesh,coords),budget=2**30)
 f=HMatrixFactor(h,storage_budget_bytes=2**30)
 for repeat in range(8):
  for mode in (['baseline','candidate'] if repeat%2==0 else ['candidate','baseline']):
   hm.adjoint_product=hf.adjoint_product=methods[mode]
   t=time.perf_counter()
   for i in range(8):y=h.matmul(b,trans=2)
   product=(time.perf_counter()-t)/8
   t=time.perf_counter();z=f.inverse(b,trans=2);inverse=time.perf_counter()-t
   arrays[mode+'_product']=y;arrays[mode+'_inverse']=z
   times.append(dict(repeat=repeat,mode=mode,product_seconds=product,inverse_seconds=inverse))
 np.savez_compressed('results/physical-product-paired.npz',rhs=b,**arrays)
 assert np.array_equal(arrays['baseline_product'],arrays['candidate_product'])
 assert np.array_equal(arrays['baseline_inverse'],arrays['candidate_inverse'])
 print(json.dumps(dict(times=times,medians={mode:{key:float(np.median([x[key] for x in times if x['mode']==mode and x['repeat']>=2])) for key in ['product_seconds','inverse_seconds']} for mode in methods},event=f.event,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)))
