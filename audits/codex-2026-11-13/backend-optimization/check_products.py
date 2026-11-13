import os,sys,json,time,resource
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/backend-optimization-study/candidate')+'/tools/GHOST')
from ghost_backend.linalg.products import adjoint_product
rng=np.random.default_rng(923)
checks=[]
for shape in [(0,4),(5,0),(1,1),(19,7),(7,19),(256,700)]:
 for width in [None,1,2,64]:
  for layout in ['C','F','stride','negative']:
   a=rng.normal(size=shape)+1j*rng.normal(size=shape)
   if layout=='F':a=np.asfortranarray(a)
   if layout=='stride':
    full=np.zeros((shape[0]*2,shape[1]*2),complex);full[::2,::2]=a;a=full[::2,::2]
   if layout=='negative':a=a[::-1,::-1]
   b=rng.normal(size=(shape[0],) if width is None else (shape[0],width))+1j*rng.normal(size=(shape[0],) if width is None else (shape[0],width))
   aa=a.copy();bb=b.copy();reference=a.conj().T@b;got=adjoint_product(a,b)
   error=np.linalg.norm(got-reference)/max(np.linalg.norm(reference),1e-300)
   assert error<5e-15,(shape,width,layout,error)
   assert np.array_equal(a,aa) and np.array_equal(b,bb)
   checks.append(dict(shape=shape,width=width,layout=layout,error=error))
for dtype in [np.complex64,np.float64,np.float32]:
 a=rng.normal(size=(91,73)).astype(dtype)
 if np.issubdtype(dtype,np.complexfloating):a+=1j*rng.normal(size=a.shape).astype(dtype)
 for bdtype in [np.complex64,np.complex128,np.float64]:
  b=rng.normal(size=(91,2)).astype(bdtype);ref=a.conj().T@b;got=adjoint_product(a,b)
  err=float(np.linalg.norm(got-ref)/np.linalg.norm(ref));assert err<10*np.finfo(got.real.dtype).eps
  checks.append(dict(dtype=str(dtype),rhs_dtype=str(bdtype),error=err))
print(json.dumps(dict(checks=checks,max_error=max(x['error'] for x in checks))))
