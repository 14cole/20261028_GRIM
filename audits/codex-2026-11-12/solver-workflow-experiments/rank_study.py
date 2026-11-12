"""Kernel-only directional-rank study; not an implementation of directional FMM."""
import json
from pathlib import Path
import numpy as np
from scipy.special import hankel2
from scipy.linalg import svdvals
from threadpoolctl import threadpool_limits
P=Path(__file__).resolve().parent;records=[]
with threadpool_limits(limits=1):
 for width in [1.,.25]:
  t=np.linspace(-width/2,width/2,256);x=np.column_stack((np.zeros(256),t));y=np.column_stack((np.full(256,3.),t))
  dist=np.linalg.norm(x[:,None,:]-y[None,:,:],axis=2)
  for f in [2.,5.,10.,15.,18.]:
   k=2*np.pi*f*1e9/299792458.;a=hankel2(0,k*dist);s=svdvals(a)
   # Arbitrary unitary row/column demodulation cannot alter singular values.
   direction=np.array([.96,.28]);left=np.exp(1j*k*x@direction);right=np.exp(-1j*k*y@direction);d=svdvals(left[:,None]*a*right[None,:])
   discrepancy=float(np.max(abs(s-d))/s[0]);assert discrepancy<1e-12
   records.append(dict(frequency_ghz=f,cluster_width_m=width,separation_m=3.,samples_per_cluster=256,rank_relative_1e12=int(np.count_nonzero(s>s[0]*1e-12)),rank_relative_1e8=int(np.count_nonzero(s>s[0]*1e-8)),demodulated_rank_relative_1e12=int(np.count_nonzero(d>d[0]*1e-12)),relative_singular_value_change=discrepancy))
(P/'RANK_STUDY.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))
