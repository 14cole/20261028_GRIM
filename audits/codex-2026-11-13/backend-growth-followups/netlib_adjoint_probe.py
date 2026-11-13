"""Independent Netlib BLAS identity check via CBLAS, not NumPy replacement.
Tests complex64 and complex128, including factor/RHS strides copied for CBLAS.
This supplements, but does not claim, a full alternate-BLAS solver run.
"""
import ctypes as ct,json,hashlib
from pathlib import Path
import numpy as np
libpath='/usr/lib/x86_64-linux-gnu/blas/libblas.so.3.12.1';lib=ct.CDLL(libpath)
def product(a,b,adjoint):
 dtype=np.result_type(a,b);a=np.array(a,dtype=dtype,order='F');b=np.array(b,dtype=dtype,order='F');c=np.zeros((a.shape[1],b.shape[1]),dtype=dtype,order='F')
 one=np.array(1,dtype=dtype);zero=np.array(0,dtype=dtype)
 f=lib.cblas_zgemm if dtype==np.complex128 else lib.cblas_cgemm
 f.argtypes=[ct.c_int]*6+[ct.c_void_p,ct.c_void_p,ct.c_int,ct.c_void_p,ct.c_int,ct.c_void_p,ct.c_void_p,ct.c_int];f.restype=None
 f(102,113 if adjoint else 112,111,a.shape[1],b.shape[1],a.shape[0],one.ctypes.data,a.ctypes.data,max(1,a.shape[0]),b.ctypes.data,max(1,b.shape[0]),zero.ctypes.data,c.ctypes.data,max(1,a.shape[1]))
 return c
rng=np.random.default_rng(8473);records=[]
for dtype in [np.complex64,np.complex128]:
 for shape in [(317,47),(47,317),(64,64),(1,5),(5,1)]:
  for width in [1,2,17,80]:
   for layout in ['C','F','reverse','stride']:
    a=(rng.normal(size=shape)+1j*rng.normal(size=shape)).astype(dtype);b=(rng.normal(size=(shape[0],width))+1j*rng.normal(size=(shape[0],width))).astype(dtype)
    if layout=='F':a=np.asfortranarray(a);b=np.asfortranarray(b)
    if layout=='reverse':a=a[::-1];b=b[::-1]
    if layout=='stride':a=np.repeat(a,2,axis=0)[::2];b=np.repeat(b,2,axis=0)[::2]
    ref=product(a,b,True);got=product(a,b.conj(),False).conj();npref=a.conj().T@b
    error=float(np.linalg.norm(got-ref)/max(np.linalg.norm(ref),1e-300));cross=float(np.linalg.norm(got-npref)/max(np.linalg.norm(npref),1e-300))
    assert max(error,cross)<50*np.finfo(dtype).eps
    records.append(dict(dtype=np.dtype(dtype).name,shape=shape,width=width,layout=layout,identity_error=error,versus_numpy=cross))
Path('results/netlib-adjoint.json').write_text(json.dumps(dict(library=libpath,sha256=hashlib.sha256(Path(libpath).read_bytes()).hexdigest(),cases=records),indent=2))
