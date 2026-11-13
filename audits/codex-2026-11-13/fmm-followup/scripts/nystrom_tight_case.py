"""Small dense-reference test of tight GMRES and phase-bearing cylinder check."""
import pathlib,sys,json,time,numpy as np
from scipy.linalg import solve
from scipy.special import hankel1,jv
D=pathlib.Path(__file__).parent;sys.path.insert(0,str(D/'claude_reference'))
import scatter
from cached_fmm import HelmholtzFMM
spec=json.loads(sys.argv[1]);kind=spec.get('kind','star');k=spec['k'];results=[];ref=None
for engine in ['claude','cached']:
 if engine=='cached':scatter.HelmholtzFMM=lambda x,n,k,**kw:HelmholtzFMM(x,n,k,digits=10,leaf_wavelengths=1.5,separation=2,tile_points=256)
 sc=scatter.Scatterer(kind,k,points_per_wavelength=spec.get('ppw',12));angles=np.array([0.,47.,121.]);b=sc.rhs(angles)
 if ref is None:a=sc.dense();ref=solve(a,b);np.save(spec['out']+'-reference-density.npy',ref)
 start=time.perf_counter();x,it,recursive=scatter.gmres_batch(sc.matvec,b,tol=1e-12,maxit=250);elapsed=time.perf_counter()-start
 r=a@x-b;back=np.max(np.max(abs(r),axis=0)/(np.linalg.norm(a,np.inf)*np.max(abs(x),axis=0)+np.max(abs(b),axis=0)))
 th=np.deg2rad(angles);dirs=-np.column_stack((np.cos(th),np.sin(th)));pattern=(-1j*k*(sc.nrm@dirs.T)-1j*k)*np.exp(-1j*k*(sc.x@dirs.T))*sc.w[:,None]
 amp=np.einsum('na,na->a',pattern,x);refamp=np.einsum('na,na->a',pattern,ref);np.save(spec['out']+'-'+engine+'-amplitude.npy',amp);np.save(spec['out']+'-'+engine+'-density.npy',x);np.save(spec['out']+'-reference-amplitude.npy',refamp)
 analytic=None
 if kind=='circle':
  m=np.arange(-int(k+12*k**(1/3)+20),int(k+12*k**(1/3)+20)+1);analytic=4j*np.sum((-1.)**m*jv(m,k)/hankel1(m,k));np.save(spec['out']+'-analytic.npy',np.array(analytic))
 results.append(dict(engine=engine,n=sc.n,solve_seconds=elapsed,iterations=it.tolist(),recursive_relative_residual=recursive.tolist(),fresh_fmm_relative_residual=np.max(np.linalg.norm(sc.matvec(x)-b,axis=0)/np.linalg.norm(b,axis=0)),direct_relative_residual=np.max(np.linalg.norm(r,axis=0)/np.linalg.norm(b,axis=0)),physical_backward_error=back,density_relative_error=np.max(abs(x-ref))/np.max(abs(ref)),complex_field_relative_error=np.max(abs(amp-refamp))/np.max(abs(refamp)),analytic_complex_relative_error=float(np.max(abs(amp-analytic))/abs(analytic)) if analytic is not None else None))
print(json.dumps(dict(spec,results=results)))
