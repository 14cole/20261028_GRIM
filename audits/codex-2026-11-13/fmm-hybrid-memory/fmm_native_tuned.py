"""Research-only ctypes bridge to pinned FMM2D. Integers are default 32-bit.
The library is built outside the production distribution. H1 is transformed
into GHOST's +i/4 H2 convention using -conj(FMM(conj(k),conj(strengths))).
Pinned FMM2D already includes +i/4, unlike the older summary documentation.
"""
import ctypes as C,os,pathlib,time,numpy as np
LIB=pathlib.Path(os.environ.get('FMM2D_LIBRARY','/workspace/fmm-libraries/fmm2d/lib/libfmm2d.so'))
lib=C.CDLL(str(LIB));fn=lib.hfmm2d_ndiv_;fn.restype=None
PROFILES=[]
fn.argtypes=[C.c_void_p]*26

def evaluate(points,k,charges=None,dipoles=None,normals=None,targets=None,gradient=False,eps=1e-12):
 points=np.asarray(points,dtype=np.float64)
 if points.ndim!=2 or points.shape[1]!=2 or len(points)==0:raise ValueError('points must have shape (N,2), N>0')
 if charges is None and dipoles is None:raise ValueError('charges or dipoles required')
 pts=np.asfortranarray(points.T,dtype=np.float64);ns=pts.shape[1]
 if charges is None:nd=np.atleast_2d(dipoles).shape[0]
 else:nd=np.atleast_2d(charges).shape[0]
 q=np.zeros((nd,ns),complex,order='F') if charges is None else np.asfortranarray(np.atleast_2d(charges).conj(),dtype=np.complex128)
 dip=np.zeros((nd,ns),complex,order='F') if dipoles is None else np.asfortranarray(np.atleast_2d(dipoles).conj(),dtype=np.complex128)
 vec=np.zeros((nd,2,ns),order='F') if normals is None else np.asfortranarray(np.broadcast_to(np.asarray(normals,dtype=np.float64).T,(nd,2,ns)))
 if q.shape!=(nd,ns) or dip.shape!=(nd,ns):raise ValueError('strengths must have shape (nd,N)')
 if dipoles is not None and normals is None:raise ValueError('dipoles require normals')
 if targets is not None and (np.asarray(targets).ndim!=2 or np.asarray(targets).shape[1]!=2):raise ValueError('targets must have shape (M,2)')
 zk=np.array(complex(k).conjugate(),dtype=np.complex128)
 same=targets is None;nt=0 if same else len(targets);targ=np.zeros((2,1),order='F') if same else np.asfortranarray(np.asarray(targets).T,dtype=np.float64)
 pot=np.zeros((nd,ns if same else 1),complex,order='F');grad=np.zeros((nd,2,ns if same and gradient else 1),complex,order='F');hess=np.zeros((nd,3,1),complex,order='F')
 pott=np.zeros((nd,nt if not same else 1),complex,order='F');gradt=np.zeros((nd,2,nt if not same and gradient else 1),complex,order='F');hesst=np.zeros((nd,3,1),complex,order='F')
 integers=[C.c_int(x) for x in [nd,ns,int(charges is not None),int(dipoles is not None),0,(2 if gradient else 1) if same else 0,nt,0 if same else (2 if gradient else 1),0]]
 nd_,ns_,iq,id_,iper,pg,nt_,pgt,ier=integers;tol=C.c_double(eps)
 ptr=lambda a:C.c_void_p(a.ctypes.data)
 ndiv=C.c_int(int(os.environ.get("FMM_NDIV","25")));idivflag=C.c_int(0);ifnear=C.c_int(1);timings=np.zeros(8);started=time.perf_counter()
 fn(C.byref(nd_),C.byref(tol),ptr(zk),C.byref(ns_),ptr(pts),C.byref(iq),ptr(q),C.byref(id_),ptr(dip),ptr(vec),C.byref(iper),C.byref(pg),ptr(pot),ptr(grad),ptr(hess),C.byref(nt_),ptr(targ),C.byref(pgt),ptr(pott),ptr(gradt),ptr(hesst),C.byref(ndiv),C.byref(idivflag),C.byref(ifnear),ptr(timings),C.byref(ier))
 PROFILES.append(dict(ndiv=ndiv.value,source_points=ns,rhs=nd,gradient=gradient,wall_seconds=time.perf_counter()-started,stages_seconds=timings.tolist()))
 if ier.value:raise RuntimeError('FMM2D error '+str(ier.value))
 return (-(pot if same else pott).conj(), -(grad if same else gradt).conj() if gradient else None)

if __name__=='__main__':
 from scipy.special import hankel2
 rng=np.random.default_rng(3);p=rng.random((100,2));t=rng.random((13,2))+2;q=rng.normal(size=(2,100))+1j*rng.normal(size=(2,100));v=rng.normal(size=(2,100))+1j*rng.normal(size=(2,100));norm=rng.normal(size=(100,2));delta=t[:,None]-p;dist=np.linalg.norm(delta,axis=2)
 for k in [3.,3.-.4j]:
  pot,grad=evaluate(p,k,q,targets=t,gradient=True)
  exact=.25j*hankel2(0,k*dist)@q.T
  eg=np.einsum('tni,nr->rit',-.25j*k*hankel2(1,k*dist)[:,:,None]*delta/dist[:,:,None],q.T)
  dp,_=evaluate(p,k,dipoles=v,normals=norm,targets=t)
  ed=(.25j*k*hankel2(1,k*dist)*np.einsum('tni,ni->tn',delta,norm)/dist)@v.T
  print(k,'potential',np.max(abs(pot.T-exact))/np.max(abs(exact)),'gradient',np.max(abs(grad-eg))/np.max(abs(eg)),'dipole',np.max(abs(dp.T-ed))/np.max(abs(ed)))
