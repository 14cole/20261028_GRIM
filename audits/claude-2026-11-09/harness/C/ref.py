import sys, numpy as np
sys.path.insert(0, '/home/user/20261028_GRIM/tools/GHOST')
def vec_brackets(kind, P, k, xi):
    """independent 3-D vector evaluation. P = 8 arrays [n]; xi [na] or [n,na]. returns 4 arrays [n,na]"""
    rp,zp,trp,tzp,rq,zq,trq,tzq = [np.asarray(a,float)[:,None] for a in P]
    xi = np.asarray(xi,float); xi = np.broadcast_to(xi,(rp.shape[0],xi.shape[-1]))
    one = np.ones_like(xi)
    # test point at phi=0, source at phi'=-xi
    c, s = np.cos(-xi), np.sin(-xi)
    rP = np.stack([rp*one, 0*one, zp*one],-1); rQ = np.stack([rq*c, rq*s, zq*one],-1)
    R = rP-rQ; Rn = np.linalg.norm(R,axis=-1)
    tP = np.stack([trp*one,0*one,tzp*one],-1); fP = np.stack([0*one,one,0*one],-1)
    nP = np.stack([-tzp*one,0*one,trp*one],-1)
    tQ = np.stack([trq*c, trq*s, tzq*one],-1); fQ = np.stack([-s, c, 0*one],-1)
    nQ = np.stack([-tzq*c, -tzq*s, trq*one],-1)
    p = (1+1j*k*Rn)*np.exp(-1j*k*Rn)/(4*np.pi*Rn**3)
    out=[]
    for W in (tP,fP):
        for u in (tQ,fQ):
            if kind=='mfie':
                v = np.cross(nP, np.cross(u, R))   # p W.(n x (u x R))
                out.append(p*np.sum(W*v,-1))
            else:
                # ibc: p * (W.nq R.u - W.u R.nq) with R'=rQ-rP?? code: D=rp*cx-rq => R_code = "P rotated minus Q" in Q frame = -( ... ) check numerically
                Rq = R  # P - Q
                out.append(p*(np.sum(W*nQ,-1)*np.sum(Rq*u,-1)-np.sum(W*u,-1)*np.sum(Rq*nQ,-1)))
    return out
def green(P4,k,xi):
    rp,zp,rq,zq=[np.asarray(a,float)[:,None] for a in P4]
    R=np.sqrt((rp-rq)**2+(zp-zq)**2+4*rp*rq*np.sin(xi/2)**2)
    return np.exp(-1j*k*R)/(4*np.pi*R)
def modal_trap(F, xi, modes):
    N=xi.size; modes=np.asarray(modes)
    X=np.fft.fft(F,axis=-1)[:,np.mod(modes,N)]
    return X*np.where(modes%2,-1.0,1.0)*(2*np.pi/N)
