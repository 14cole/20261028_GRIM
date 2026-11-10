import numpy as np, scipy.special as sp
class DenseOracle:
    def __init__(s,A): s.A=A; s.n=len(A); s.calls=0; s.entries=0
    def get_with_error(s,rows,cols):
        s.calls+=1; s.entries+=len(rows)*len(cols)
        v=s.A[np.ix_(rows,cols)]
        return v, np.zeros(v.shape)
def kernel(xy, ka, w):
    d=np.linalg.norm(xy[:,None]-xy[None],axis=2)
    d[d<1e-14]=w/4
    return 0.25j*sp.hankel1(0,ka*d)*w
def circle(n,x0=0.,r=1.):
    th=2*np.pi*(np.arange(n)+.5)/n
    return np.c_[x0+r*np.cos(th), r*np.sin(th)]
