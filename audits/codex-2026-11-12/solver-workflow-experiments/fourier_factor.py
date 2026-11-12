"""Research factor for explicitly declared uniform rotationally symmetric meshes.

Full assembled matrix remains the residual authority. This is not a geometry
classifier, general compression method, or a production alternate backend.
"""
import numpy as np
class FourierFactor:
    def __init__(self,a,parts=1):
        self.parts=parts;self.n=len(a);self.m=self.n//parts
        if self.m*parts!=self.n:raise ValueError('Invalid density blocks')
        columns=np.empty((parts,parts,self.m),complex);worst=0.;scale=0.
        for r in range(parts):
            for c in range(parts):
                column=np.array(a[r*self.m:(r+1)*self.m,c*self.m]);columns[r,c]=column
                # Check every matrix entry in bounded row blocks, not sampled symmetry.
                for i in range(0,self.m,64):
                    rows=np.arange(i,min(self.m,i+64))
                    block=a[r*self.m+rows[:,None],c*self.m+np.arange(self.m)[None,:]]
                    delta=block-column[(rows[:,None]-np.arange(self.m)[None,:])%self.m]
                    worst=max(worst,float(np.max(abs(delta))));scale=max(scale,float(np.max(abs(block))))
        self.symmetry_error=worst/max(scale,1e-300)
        if self.symmetry_error>1e-11:raise ValueError('Matrix is not sufficiently block circulant')
        self.symbol=np.moveaxis(np.fft.fft(columns,axis=2),2,0)
    def solve(self,b,trans=0):
        b=np.asarray(b,complex);vector=b.ndim==1
        if vector:b=b[:,None]
        rhs=np.moveaxis(np.fft.fft(b.reshape(self.parts,self.m,-1),axis=1),1,0)
        symbol=self.symbol
        if trans==1:symbol=symbol[(-np.arange(self.m))%self.m].transpose(0,2,1)
        elif trans==2:symbol=symbol.conj().transpose(0,2,1)
        elif trans!=0:raise ValueError('Invalid transpose')
        answer=np.linalg.solve(symbol,rhs)
        x=np.fft.ifft(np.moveaxis(answer,0,1),axis=1).reshape(self.n,-1)
        return x[:,0] if vector else x

class SectorFourierFactor:
    """Cyclic sector decomposition: dense local blocks, Fourier modes by sector."""
    def __init__(self,a,sectors=7):
        import scipy.linalg as la
        self.n=len(a);self.sectors=sectors;self.q=self.n//sectors
        if self.q*sectors!=self.n:raise ValueError('Equal sector DOF counts required')
        q=self.q;blocks=np.stack([a[r*q:(r+1)*q,:q] for r in range(sectors)])
        worst=scale=0.
        for r in range(sectors):
            for c in range(sectors):
                block=a[r*q:(r+1)*q,c*q:(c+1)*q]
                worst=max(worst,float(np.max(abs(block-blocks[(r-c)%sectors]))));scale=max(scale,float(np.max(abs(block))))
        self.symmetry_error=worst/max(scale,1e-300)
        if self.symmetry_error>1e-11:raise ValueError('Matrix does not respect declared cyclic sectors')
        symbol=np.fft.fft(blocks,axis=0);self.factors=[la.lu_factor(np.array(x,order='F'),overwrite_a=True,check_finite=True) for x in symbol]
        self.retained_bytes=sum(lu.nbytes+piv.nbytes for lu,piv in self.factors)
    def solve(self,b,trans=0):
        import scipy.linalg as la
        b=np.asarray(b,complex);vector=b.ndim==1
        if vector:b=b[:,None]
        if trans not in (0,1,2):raise ValueError('Invalid transpose')
        rhs=np.fft.fft(b.reshape(self.sectors,self.q,-1),axis=0)
        x=np.empty_like(rhs)
        for k in range(self.sectors):x[k]=la.lu_solve(self.factors[(-k)%self.sectors if trans==1 else k],rhs[k],trans=trans,check_finite=False)
        x=np.fft.ifft(x,axis=0).reshape(self.n,-1)
        return x[:,0] if vector else x
