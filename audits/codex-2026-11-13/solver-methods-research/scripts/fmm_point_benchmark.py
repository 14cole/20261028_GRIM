import pathlib,sys,json,time,resource,numpy as np
from scipy.special import hankel2
from fmm_native import evaluate
spec=json.loads(sys.argv[1]);n=spec['n'];nd=spec.get('rhs',1);frequency=spec['ghz'];length=6.096;k=2*np.pi*frequency*1e9/299792458.;eps=spec.get('eps',1e-12)
theta=-np.linspace(0,2*np.pi,n,endpoint=False);r=length/2*(.8+.2*np.cos(5*theta));points=np.column_stack((r*np.cos(theta),r*np.sin(theta)));rng=np.random.default_rng(20261113);charges=rng.normal(size=(nd,n))+1j*rng.normal(size=(nd,n));selected=np.sort(rng.choice(n,min(32,n),replace=False));error=None;fmm_peak=None;baseline_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2;start=time.perf_counter()
try:
 value,_=evaluate(points,k,charges=charges,eps=eps);elapsed=time.perf_counter()-start;fmm_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2
 delta=points[selected,None]-points[None];dist=np.linalg.norm(delta,axis=2);mask=dist>0;kernel=np.zeros(dist.shape,complex);kernel[mask]=.25j*hankel2(0,k*dist[mask]);exact=kernel@charges.T
 measured=value[:,selected].T;relative=float(np.max(abs(exact-measured))/np.max(abs(exact)))
 # Full outputs retained for deterministic reproduction, not just summary peaks.
 np.save(spec['out'],value)
except Exception as exc:elapsed=time.perf_counter()-start;error=repr(exc);relative=None
print(json.dumps(dict(spec,seconds=elapsed,error=error,sampled_relative_max=relative,checked_targets=len(selected),baseline_peak_rss_gib=baseline_rss,fmm_peak_rss_gib=fmm_peak,dense_equivalent_gib=16*n*n/2**30,peak_rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2,kind='point_kernel_only_not_a_galerkin_solve')))
