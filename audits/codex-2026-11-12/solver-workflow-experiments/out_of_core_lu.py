"""Audit prototype: disk-resident partial-pivoted complex128 blocked LU.

No production integration or reduced admission claims. Flush+MADV_DONTNEED
bounds mapped residency on Linux; filesystem cache remains OS/cgroup memory.
"""
import mmap,os,time,warnings
from pathlib import Path
import numpy as np
import scipy.linalg as la

class DiskLU:
    def __init__(self,source,path,block=128,evict=True):
        self.n=int(source.shape[0]);self.block=int(block);self.evict=evict
        if source.shape!=(self.n,self.n) or self.block<1:raise ValueError('Square matrix and positive block required')
        self.path=Path(path);self.a=np.memmap(self.path,dtype=np.complex128,mode='w+',shape=source.shape,order='F')
        self.fd=os.open(self.path,os.O_RDWR)
        self.piv=np.arange(self.n,dtype=np.int64);self.bytes_read=0;self.bytes_written=0;self.flushes=0
        try:
            for j in range(0,self.n,self.block):
                self.a[:,j:j+self.block]=source[:,j:j+self.block];self.bytes_written+=self.a[:,j:j+self.block].nbytes;self.release()
                if isinstance(source,np.memmap):source._mmap.madvise(mmap.MADV_DONTNEED)
            started=time.perf_counter();self.factor();self.factor_seconds=time.perf_counter()-started
        except BaseException:
            self.close();raise
    def release(self):
        self.a.flush();self.flushes+=1
        if self.evict:
            self.a._mmap.madvise(mmap.MADV_DONTNEED)
            os.posix_fadvise(self.fd,0,0,os.POSIX_FADV_DONTNEED)
    def read(self,rows,cols):
        v=np.array(self.a[rows,cols],order='F',copy=True);self.bytes_read+=v.nbytes;return v
    def write(self,rows,cols,value):
        self.a[rows,cols]=value;self.bytes_written+=value.nbytes
    def factor(self):
        n,b=self.n,self.block
        for k in range(0,n,b):
            e=min(n,k+b);panel=self.read(slice(k,n),slice(k,e))
            with warnings.catch_warnings():
                warnings.simplefilter('error',la.LinAlgWarning)
                panel,p=la.lu_factor(panel,overwrite_a=True,check_finite=True)
            self.piv[k:e]=k+p;self.write(slice(k,n),slice(k,e),panel);self.release()
            for j in range(0,n,b):
                z=min(n,j+b)
                if j==k:continue
                # Apply the panel's pivot sequence to already computed L and future columns.
                tile=self.read(slice(0,n),slice(j,z))
                for local,target in enumerate(p):
                    a=k+local;c=k+int(target)
                    if a!=c:tile[[a,c],:]=tile[[c,a],:]
                self.write(slice(0,n),slice(j,z),tile);del tile;self.release()
            for j in range(e,n,b):
                z=min(n,j+b)
                upper=la.solve_triangular(panel[:e-k],self.read(slice(k,e),slice(j,z)),lower=True,unit_diagonal=True,check_finite=False)
                self.write(slice(k,e),slice(j,z),upper)
                trailing=self.read(slice(e,n),slice(j,z));trailing-=panel[e-k:]@upper
                self.write(slice(e,n),slice(j,z),trailing);del trailing,upper;self.release()
            del panel
    def solve(self,rhs,trans=0):
        if trans not in (0,1,2):raise ValueError('Invalid transpose')
        x=np.array(rhs,dtype=np.complex128,copy=True,order='F');vector=x.ndim==1
        if vector:x=x[:,None]
        n,b=self.n,self.block;ranges=[(k,min(n,k+b)) for k in range(0,n,b)]
        if trans==0:
            for k,p in enumerate(self.piv):
                if k!=p:x[[k,p]]=x[[p,k]]
            for k,e in ranges:
                tile=self.read(slice(k,n),slice(k,e));x[k:e]=la.solve_triangular(tile[:e-k],x[k:e],lower=True,unit_diagonal=True,check_finite=False)
                x[e:]-=tile[e-k:]@x[k:e];del tile;self.release()
            for k,e in reversed(ranges):
                tile=self.read(slice(0,e),slice(k,e));x[k:e]=la.solve_triangular(tile[k:e],x[k:e],lower=False,check_finite=False)
                x[:k]-=tile[:k]@x[k:e];del tile;self.release()
        else:
            def op(a):return a.T if trans==1 else a.conj().T
            # U^T/H y=b, then L^T/H z=y, then x=P^-1 z.
            for k,e in ranges:
                tile=self.read(slice(0,e),slice(k,e));x[k:e]-=op(tile[:k])@x[:k]
                x[k:e]=la.solve_triangular(tile[k:e],x[k:e],lower=False,trans=trans,check_finite=False);del tile;self.release()
            for k,e in reversed(ranges):
                tile=self.read(slice(k,n),slice(k,e));x[k:e]-=op(tile[e-k:])@x[e:]
                x[k:e]=la.solve_triangular(tile[:e-k],x[k:e],lower=True,unit_diagonal=True,trans=trans,check_finite=False);del tile;self.release()
            for k in range(n-1,-1,-1):
                p=self.piv[k]
                if k!=p:x[[k,p]]=x[[p,k]]
        return x[:,0] if vector else x
    def close(self):
        if getattr(self,'a',None) is not None:self.a._mmap.close();self.a=None
        if getattr(self,'fd',None) is not None:os.close(self.fd);self.fd=None
        self.path.unlink(missing_ok=True)

class FusedDiskLU(DiskLU):
    """Apply pivots and the trailing update in one visit to each column slab."""
    def factor(self):
        n,b=self.n,self.block
        for k in range(0,n,b):
            e=min(n,k+b);panel=self.read(slice(k,n),slice(k,e))
            with warnings.catch_warnings():
                warnings.simplefilter('error',la.LinAlgWarning)
                panel,p=la.lu_factor(panel,overwrite_a=True,check_finite=True)
            self.piv[k:e]=k+p;self.write(slice(k,n),slice(k,e),panel);self.release()
            for j in range(0,n,b):
                z=min(n,j+b)
                if j==k:continue
                tile=self.read(slice(0,n),slice(j,z))
                for local,target in enumerate(p):
                    a=k+local;c=k+int(target)
                    if a!=c:tile[[a,c],:]=tile[[c,a],:]
                if j>=e:
                    upper=la.solve_triangular(panel[:e-k],tile[k:e],lower=True,unit_diagonal=True,check_finite=False)
                    tile[k:e]=upper;tile[e:]-=panel[e-k:]@upper;del upper
                self.write(slice(0,n),slice(j,z),tile);del tile;self.release()
            del panel
