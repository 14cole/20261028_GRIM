"""Audit-only dielectric block factor with exact common-block reuse across TE/TM."""
import hashlib,warnings
import numpy as np
import scipy.linalg as la

def digest(a):
    h=hashlib.sha256();h.update(str(a.shape).encode())
    for i in range(0,len(a),64):h.update(np.ascontiguousarray(a[i:i+64]).tobytes())
    return h.hexdigest()

def factor(a):
    with warnings.catch_warnings():
        warnings.simplefilter('error',la.LinAlgWarning)
        return la.lu_factor(a,overwrite_a=True,check_finite=True)

class SchurFactor:
    def __init__(self,a,cache):
        self.n=len(a)//2
        if len(a)!=2*self.n:raise ValueError('Two equal density blocks required')
        n=self.n;B,C,D,E=a[:n,:n],a[:n,n:],a[n:,:n],a[n:,n:];self.D=D
        key=(digest(B),digest(C),digest(D))
        self.reused=cache.get('key')==key
        if not self.reused:
            cache.clear();lu=factor(np.array(B,order='F'));y=la.lu_solve(lu,np.array(C,order='F'),check_finite=False)
            product=D@y;cache.update(key=key,lu=lu,y=y,product=product)
        self.blu=cache['lu'];self.y=cache['y'];schur=np.array(E,order='F');schur-=cache['product'];self.slu=factor(schur)
        self.retained_factor_bytes=self.blu[0].nbytes+self.y.nbytes+self.slu[0].nbytes
        self.shared_product_bytes=cache['product'].nbytes
    def solve(self,b,trans=0):
        b=np.asarray(b,complex);vector=b.ndim==1
        if vector:b=b[:,None]
        n=self.n;b0,b1=b[:n],b[n:]
        if trans==0:
            t=la.lu_solve(self.blu,b0,check_finite=False);x1=la.lu_solve(self.slu,b1-self.D@t,check_finite=False);x0=t-self.y@x1
        elif trans in (1,2):
            def op(a):return a.T if trans==1 else a.conj().T
            x1=la.lu_solve(self.slu,b1-op(self.y)@b0,trans=trans,check_finite=False)
            x0=la.lu_solve(self.blu,b0-op(self.D)@x1,trans=trans,check_finite=False)
        else:raise ValueError('Invalid transpose')
        x=np.vstack((x0,x1));return x[:,0] if vector else x
