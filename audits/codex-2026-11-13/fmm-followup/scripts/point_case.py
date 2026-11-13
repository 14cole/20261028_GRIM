import sys,json,pathlib,time,resource,numpy as np
from scipy.special import hankel1
D=pathlib.Path(__file__).parent;sys.path.insert(0,str(D/'claude_reference'))
from scatter import curve
spec=json.loads(sys.argv[1]);n=spec.get('n',4000);k=complex(*spec.get('k',[60.,0.]));rng=np.random.default_rng(20261113);x,normal,_=curve('star',n);a=rng.normal(size=(n,2))+1j*rng.normal(size=(n,2));dip=rng.normal(size=(n,2))+1j*rng.normal(size=(n,2));rows=np.sort(rng.choice(n,32,replace=False));t=time.perf_counter()
if spec.get('engine')=='claude':
 from fmm2d import HelmholtzFMM
 F=HelmholtzFMM(x,normal,k.real,digits=spec.get('digits',8),leaf_wavelengths=1.5)
else:
 from cached_fmm import HelmholtzFMM
 F=HelmholtzFMM(x,normal,k,digits=spec.get('digits',10),leaf_wavelengths=1.5,separation=spec.get('separation',2),tile_points=spec.get('tile',512),gradients=True)
setup=time.perf_counter()-t;t=time.perf_counter();u=F.apply(a,dip);elapsed=time.perf_counter()-t
ug=grad=None
if spec.get('engine')!='claude':ug,grad=F.apply(a,gradient=True)
peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2
v=x[rows,None]-x[None];r=np.linalg.norm(v,axis=-1);r[np.arange(len(rows)),rows]=1.;G=.25j*hankel1(0,k*r);G[np.arange(len(rows)),rows]=0;K=.25j*k*hankel1(1,k*r)*np.einsum('rni,ni->rn',v,normal)/r;K[np.arange(len(rows)),rows]=0;truth=G@a+K@dip
err=float(np.max(abs(u[rows]-truth))/np.max(abs(truth)));gerr=None
if grad is not None:
 exact_grad=np.einsum('rni,nb->rib',-.25j*k*hankel1(1,k*r)[:,:,None]*v/r[:,:,None],a);gerr=float(np.max(abs(grad[rows]-exact_grad))/np.max(abs(exact_grad)))
np.save(spec['out']+'.npy',u);np.save(spec['out']+'-exact.npy',truth)
if grad is not None:np.save(spec['out']+'-gradient.npy',grad);np.save(spec['out']+'-gradient-exact.npy',exact_grad)
print(json.dumps(dict(spec,setup_seconds=setup,product_seconds=elapsed,peak_before_reference_gib=peak,retained_bytes=F.bytes,near_pairs=F.near_pairs,point_relative_error=err,gradient_relative_error=gerr,checked_rows=rows.tolist())))
