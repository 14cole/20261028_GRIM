"""Incident-load numerical rank; does not forecast FMM time or compress a solution."""
import os,json,time,resource
from pathlib import Path
import numpy as np
from scipy.linalg import norm
from monostatic import mesh_for,dielectric,CPUState,_STATE,cpu_allocation_scope,execution_scope,_qr_basis
rows=[]
with _STATE.override(CPUState(kernel_only=True)),cpu_allocation_scope(1),execution_scope({'assembly_threads':1,'blas_threads':1}):
 for n,k in [(1024,20),(4096,80),(16384,320),(32768,640),(16384,20)]:
  mesh=mesh_for(n,'star')
  for count,start,stop in [(180,-90,90),(180,0,360),(360,0,360)]:
   t=time.perf_counter();angles=np.linspace(start,stop,count,endpoint=False);b=dielectric.rhs_many(mesh,k,angles)
   # Match the existing production SweepBasis row-max scaling.
   scale=np.max(abs(b),axis=1);scale[scale==0]=1;b/=scale[:,None];bn=norm(b)
   q,recovery=_qr_basis(b,2e-15*bn);error=float(norm(b-q@recovery)/bn)
   d=dict(n=n,unknowns=2*n,k=k,count=count,start=start,stop=stop,step=(stop-start)/count,rank=q.shape[1],relative_rhs_error=error,meets_auto_half_rank=q.shape[1]<count/2,phase_step_at_radius_1_2=k*1.2*np.deg2rad((stop-start)/count),seconds=time.perf_counter()-t,peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)
   rows.append(d);print(json.dumps(d),flush=True);del b,q,recovery
Path(os.environ.get('MONOSTATIC_RANK_OUTPUT','rank-scan.json')).write_text(json.dumps(rows,indent=2))
