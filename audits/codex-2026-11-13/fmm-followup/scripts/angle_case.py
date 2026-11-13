"""Independent angle/concurrency reproduction; retain complex amplitudes, not only RCS."""
import pathlib,sys,json,time,resource,os
import numpy as np
D=pathlib.Path(__file__).parent;sys.path.insert(0,str(D/'claude_reference'))
from scatter import Scatterer,gmres_batch
from fmm2d import direct
spec=json.loads(sys.argv[1]);angles=np.linspace(0,180,spec['angles']);start=time.perf_counter();sc=Scatterer(spec.get('kind','star'),spec['ka'],points_per_wavelength=spec.get('ppw',12));setup=time.perf_counter()-start;B=sc.rhs(angles);batch=spec.get('batch',8);chunks=[np.arange(i,min(i+batch,len(angles))) for i in range(0,len(angles),batch)];X=np.empty_like(B);iterations=np.zeros(len(angles),int)
def solve(cols):
 x,it,res=gmres_batch(sc.matvec,B[:,cols],tol=spec.get('tol',1e-8));return cols,x,it
start=time.perf_counter()
if spec['strategy']=='batch':
 for cols in chunks:_,X[:,cols],iterations[cols]=solve(cols)
elif spec['strategy']=='threads':
 from concurrent.futures import ThreadPoolExecutor
 with ThreadPoolExecutor(spec['workers']) as pool:
  for cols,x,it in pool.map(solve,chunks):X[:,cols]=x;iterations[cols]=it
else:
 import multiprocessing as mp
 with mp.get_context('fork').Pool(spec['workers']) as pool:
  for cols,x,it in pool.imap_unordered(solve,chunks):X[:,cols]=x;iterations[cols]=it
wall=time.perf_counter()-start
# Fresh FMM residual for EVERY angle, then independent direct rows for every angle.
residual=[]
for cols in chunks:residual.extend((np.linalg.norm(sc.matvec(X[:,cols])-B[:,cols],axis=0)/np.linalg.norm(B[:,cols],axis=0)).tolist())
rng=np.random.default_rng(72);rows=np.sort(rng.choice(sc.n,32,replace=False));wX=sc.w[:,None]*X
truth=.5*X[rows]+direct(sc.x,sc.nrm,sc.k,-1j*sc.eta*wX,wX,rows)+(sc.correction@X)[rows]
row_residual=float(np.max(np.abs(truth-B[rows]))/np.max(np.abs(B[rows])))
# Recover the complex far-field amplitude underlying Claude's RCS convention.
th=np.deg2rad(angles);dirs=-np.column_stack((np.cos(th),np.sin(th)));pattern=(-1j*sc.k*(sc.nrm@dirs.T)-1j*sc.eta)*np.exp(-1j*sc.k*(sc.x@dirs.T));amp=np.einsum('na,na->a',pattern*sc.w[:,None],X)
np.save(spec['out']+'-amplitude.npy',amp);np.save(spec['out']+'-rcs.npy',abs(amp)**2/(4*sc.k));np.save(spec['out']+'-residuals.npy',np.array(residual))
print(json.dumps(dict(spec,n=sc.n,setup_seconds=setup,solve_seconds=wall,iterations=iterations.tolist(),max_all_angle_fmm_relative_residual=max(residual),sampled_direct_relative_residual=row_residual,parent_peak_rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,reported_plan_bytes_partial=sc.fmm.bytes)))
