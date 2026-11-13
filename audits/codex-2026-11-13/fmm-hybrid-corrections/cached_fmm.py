# Research derivative of Claude fmm2d.py at fe0a8eb785d6697b9b008e45798ab48eda311f43.
# Changes: configurable separation, passive complex k, target gradients,
# tiled source/target workspaces and more complete retained-array accounting.
# Not a production solver or accuracy certificate.
"""Research prototype: multilevel diagonal-form FMM for the 2D Helmholtz kernel.

Not part of GHOST. NumPy/SciPy only. Evaluates, for every target i,

    u_i = sum_{j != i} (i/4) [ a_j H0(k r_ij) + b_j k H1(k r_ij) (r_ij . n_j)/r_ij ]

(a monopole strength a_j and a dipole strength b_j with direction n_j at each
source), for one or many strength vectors at once (columns).  Sources and
targets are the same points.

Method: uniform quadtree; far interactions through plane-wave (diagonal)
translations, H0(k|X+d|) = mean_q exp(i k s_q.d) T(theta_q),
T = sum_{|l|<=L} i^l H_l(kX) exp(i l (theta - theta_X)); FFT interpolation
between levels; near interactions (adjacent leaves) through a sparse matrix.
The leaf size is kept above a fraction of the wavelength, where the diagonal
form is stable.
"""
import math
import numpy as np
from scipy.special import hankel1
from scipy import sparse


def _truncation(kd, digits):
    return int(math.ceil(kd + 1.8 * digits ** (2.0 / 3.0) * max(kd, 1e-30) ** (1.0 / 3.0))) + 2


def _resample(f, q_new):
    """Trigonometric resampling of periodic samples along axis 1 (bandlimited)."""
    q_old = f.shape[1]
    if q_new == q_old:
        return f
    F = np.fft.fft(f, axis=1)
    m = (min(q_old, q_new) - 1) // 2
    G = np.zeros((f.shape[0], q_new) + f.shape[2:], dtype=complex)
    G[:, :m + 1] = F[:, :m + 1]
    G[:, q_new - m:] = F[:, q_old - m:]
    return np.fft.ifft(G, axis=1) * (q_new / q_old)


class HelmholtzFMM:
    def __init__(self, points, normals, k, digits=8, leaf_wavelengths=0.75, max_leaf_points=None, separation=1, tile_points=0, gradients=False, near_storage=True, partition_points=None, support_radius=0., build_point_phases=True):
        self.k = k = complex(k)
        self.separation = separation = int(separation)
        self.tile_points = int(tile_points)
        self.gradients = bool(gradients)
        self.near_storage=bool(near_storage)
        if separation < 1 or k.real <= 0 or k.imag < 0: raise ValueError("Requires separation>=1 and passive H1 wavenumber")
        self.x = x = np.asarray(points, float)
        self.nrm = np.asarray(normals, float)
        self.n = n = len(x)
        lo = x.min(axis=0); span = float((x.max(axis=0) - lo).max()) * (1 + 1e-9) + 1e-300
        wavelength = 2 * math.pi / abs(k)
        levels = max(2, int(math.floor(math.log2(span / (leaf_wavelengths * wavelength)))))
        # The forced two-level tree can have subwavelength leaves. A diagonal
        # translation there is not reliably accurate. For these small electrical
        # domains, make the 4x4 leaf grid entirely direct; allocation guards still
        # apply. This is a bounded fallback, not an adaptive wideband FMM.
        self.low_frequency_direct = levels == 2 and span < 4*leaf_wavelengths*wavelength
        if self.low_frequency_direct:
            separation = max(separation,3); self.separation = separation
        self.levels = levels                       # leaf level index; root is level 0
        self.side = [span / 2 ** l for l in range(levels + 1)]
        self.lo = lo
        # ---- tree: nonempty boxes per level, integer coordinates
        ij = np.clip(np.floor(((x if partition_points is None else np.asarray(partition_points)) - lo) / self.side[levels]).astype(np.int64), 0, 2 ** levels - 1)
        key = ij[:, 0] * (1 << levels) + ij[:, 1]
        self.order = order = np.argsort(key, kind='stable')
        skey = key[order]
        leaf_keys, start = np.unique(skey, return_index=True)
        self.leaf_start = start
        self.leaf_of_point = np.searchsorted(leaf_keys, skey)          # for sorted points
        self.boxes = [None] * (levels + 1)                              # integer coords per level
        self.parent = [None] * (levels + 1)
        coords = np.stack([leaf_keys >> levels, leaf_keys & ((1 << levels) - 1)], 1)
        self.boxes[levels] = coords
        for l in range(levels, 0, -1):
            pc = self.boxes[l] // 2
            pkey = pc[:, 0] * (1 << (l - 1)) + pc[:, 1]
            uk, inv = np.unique(pkey, return_inverse=True)
            self.parent[l] = inv
            self.boxes[l - 1] = np.stack([uk >> (l - 1), uk & ((1 << (l - 1)) - 1)], 1)
        # ---- per-level quadrature
        self.L = [0] * (levels + 1); self.Q = [0] * (levels + 1); self.s = [None] * (levels + 1)
        self.theta = [None] * (levels + 1)
        for l in range(levels + 1):
            Lq = _truncation(abs(k) * (self.side[l] * math.sqrt(2.0) + 2*support_radius), digits)
            self.L[l] = Lq; self.Q[l] = 2 * Lq + 1
            th = 2 * math.pi * np.arange(self.Q[l]) / self.Q[l]
            self.theta[l] = th; self.s[l] = np.stack([np.cos(th), np.sin(th)], 1)
        # ---- interaction lists and translation tables (levels >= 2)
        self.m2l = [None] * (levels + 1)
        self.shift_up = [None] * (levels + 1)
        self.shift_down = [None] * (levels + 1)
        for l in range(2, levels + 1):
            b = self.boxes[l]; nb = len(b)
            index = {(int(i), int(j)): t for t, (i, j) in enumerate(b)}
            pb = self.boxes[l - 1]; par = self.parent[l]
            pindex = {(int(i), int(j)): t for t, (i, j) in enumerate(pb)}
            children = [[] for _ in range(len(pb))]
            for t in range(nb):
                children[par[t]].append(t)
            groups = {}
            for t in range(nb):
                pi, pj = pb[par[t]]
                bi, bj = b[t]
                for di in range(-separation,separation+1):
                    for dj in range(-separation,separation+1):
                        q = pindex.get((int(pi) + di, int(pj) + dj))
                        if q is None:
                            continue
                        for c in children[q]:
                            ox, oy = int(b[c][0] - bi), int(b[c][1] - bj)
                            if max(abs(ox), abs(oy)) > separation:
                                groups.setdefault((ox, oy), ([], []))
                                groups[(ox, oy)][0].append(t); groups[(ox, oy)][1].append(c)
            tables = []
            Lq = self.L[l]; ls = np.arange(-Lq, Lq + 1)
            for (ox, oy), (tg, sr) in groups.items():
                X = -np.array([ox, oy], float) * self.side[l]        # target centre - source centre
                rX = math.hypot(*X); tX = math.atan2(X[1], X[0])
                T = ((1j ** ls)[None, :] * hankel1(ls, k * rX)[None, :]
                     * np.exp(1j * ls[None, :] * (self.theta[l][:, None] - tX))).sum(axis=1)
                tables.append((np.asarray(tg), np.asarray(sr), T))
            self.m2l[l] = tables
        for l in range(1, levels + 1):
            # child centre relative to parent centre
            off = (self.boxes[l] % 2 - 0.5) * self.side[l]
            self.shift_down[l] = np.exp(1j * k * (off @ self.s[l - 1].T))
            self.shift_up[l] = np.exp(-1j * k * (off @ self.s[l - 1].T))   # (nboxes_l, Q_{l-1})
        # ---- leaf expansions
        centre = lo + (self.boxes[levels][self.leaf_of_point] + 0.5) * self.side[levels]
        xs = x[order]; rel = xs - centre
        self.E = self.Eout = self.dip = None
        if build_point_phases:
            phase = k * (rel @ self.s[levels].T)                               # (n, Q_leaf)
            self.Eout = np.exp(1j * phase)
            self.E = np.exp(-1j * phase)                                       # source pattern factor
            self.dip = -1j * k * (self.nrm[order] @ self.s[levels].T)          # dipole factor  (-ik s.n)
        # ---- near field: adjacent leaves, direct, self excluded
        b = self.boxes[levels]; index = {(int(i), int(j)): t for t, (i, j) in enumerate(b)}
        ends = np.append(start, n)
        neighbors=[]; counts=np.empty(n,dtype=np.int64)
        for t,(bi,bj) in enumerate(b):
            qs=[]
            for di in range(-separation,separation+1):
                for dj in range(-separation,separation+1):
                    q=index.get((int(bi)+di,int(bj)+dj))
                    if q is not None:qs.append(q)
            qs.sort();neighbors.append(np.array(qs,dtype=int))
            counts[ends[t]:ends[t+1]]=sum(ends[q+1]-ends[q] for q in qs)-1
        self.leaf_neighbors=neighbors
        self.near_pairs=int(counts.sum());self.near_mono=self.near_dip=None;self.near_grad=[]
        if near_storage:
            normals_sorted=self.nrm[order]
            number=4 if gradients else 2
            required=self.near_pairs*(16*number+4)+4*(n+1)
            if required>3*2**30:raise MemoryError('Research near-point budget exceeded: '+str(required))
            indptr=np.r_[0,np.cumsum(counts)].astype(np.int64 if self.near_pairs>=2**31 else np.int32)
            indices=np.empty(self.near_pairs,dtype=indptr.dtype);data=[np.empty(self.near_pairs,complex) for _ in range(number)]
            for t,qs in enumerate(neighbors):
                cc=np.concatenate([np.arange(ends[q],ends[q+1]) for q in qs]);step=max(1,min(64,131072//len(cc)))
                for first in range(ends[t],ends[t+1],step):
                    rr=np.arange(first,min(ends[t+1],first+step));mask=rr[:,None]!=cc[None,:];ri=np.broadcast_to(rr[:,None],mask.shape)[mask];ci=np.broadcast_to(cc[None,:],mask.shape)[mask];loi,hii=int(indptr[rr[0]]),int(indptr[rr[-1]+1]);indices[loi:hii]=ci
                    dv=xs[ri]-xs[ci];dist=np.linalg.norm(dv,axis=1);common=.25j*k*hankel1(1,k*dist)/dist
                    data[0][loi:hii]=.25j*hankel1(0,k*dist)
                    data[1][loi:hii]=common*np.einsum('ij,ij->i',dv,normals_sorted[ci])
                    if gradients:
                        data[2][loi:hii]=-common*dv[:,0];data[3][loi:hii]=-common*dv[:,1]
            matrices=[sparse.csr_matrix((v,indices,indptr),shape=(n,n),copy=False) for v in data]
            self.near_mono,self.near_dip=matrices[:2];self.near_grad=matrices[2:]
        seen=set()
        def retained(value):
            if isinstance(value,np.ndarray):
                root=value
                while isinstance(root.base,np.ndarray):root=root.base
                if id(root) in seen:return 0
                seen.add(id(root));return root.nbytes
            if sparse.issparse(value):return sum(retained(a) for a in (value.data,value.indices,value.indptr))
            if isinstance(value,(tuple,list)):return sum(retained(a) for a in value)
            return 0
        self.bytes=sum(retained(v) for v in self.__dict__.values())

    def apply(self, mono=None, dip=None, gradient=False):
        """u = S-type sum of monopoles `mono` plus D-type sum of dipoles `dip`; arrays (n,) or (n, B)."""
        if self.E is None: raise ValueError("Point phases were not built")
        if gradient and (not self.gradients or dip is not None): raise ValueError("Gradient supports charge-only plans")
        ref = mono if mono is not None else dip
        vector = ref.ndim == 1
        a = None if mono is None else (mono[:, None] if vector else mono)[self.order]
        d = None if dip is None else (dip[:, None] if vector else dip)[self.order]
        B = (a if a is not None else d).shape[1]
        levels = self.levels
        # P2M at the leaves
        M = [None] * (levels + 1)
        M[levels] = np.empty((len(self.leaf_start),self.Q[levels],B),complex)
        starts=self.leaf_start; ends=np.append(starts,self.n); first=0
        while first<len(starts):
            last=len(starts) if not self.tile_points else max(first+1,int(np.searchsorted(starts,starts[first]+self.tile_points)))
            i,j=int(starts[first]),int(ends[last]);w=0
            if a is not None: w=self.E[i:j,:,None]*a[i:j,None,:]
            if d is not None: w=w+(self.E[i:j]*self.dip[i:j])[:,:,None]*d[i:j,None,:]
            M[levels][first:last]=np.add.reduceat(w,starts[first:last]-i,axis=0)
            first=last
        del w
        # M2M upward
        for l in range(levels, 2, -1):
            up = _resample(M[l], self.Q[l - 1]) * self.shift_up[l][:, :, None]
            parent = np.zeros((len(self.boxes[l - 1]), self.Q[l - 1], B), complex)
            np.add.at(parent, self.parent[l], up)
            M[l - 1] = parent
        # M2L and L2L downward
        Lc = None
        for l in range(2, levels + 1):
            loc = np.zeros_like(M[l])
            for tg, sr, T in self.m2l[l]:
                np.add.at(loc, tg, M[l][sr] * T[None, :, None])
            if Lc is not None:
                down = Lc[self.parent[l]] * self.shift_down[l][:, :, None]
                loc += _resample(down, self.Q[l])
            Lc = loc
        # L2P
        out=np.empty((self.n,B),complex)
        grad=np.empty((self.n,2,B),complex) if gradient else None
        tile=self.tile_points or self.n
        for i in range(0,self.n,tile):
            j=min(self.n,i+tile);local=Lc[self.leaf_of_point[i:j]];E=self.Eout[i:j]
            out[i:j]=np.einsum('nq,nqb->nb',E,local)*(0.25j/self.Q[levels])
            if gradient:
                for component in range(2):
                    grad[i:j,component]=np.einsum('nq,nqb,q->nb',E,local,1j*self.k*self.s[levels][:,component])*(0.25j/self.Q[levels])
        if a is not None and self.near_storage:
            out+=self.near_mono@a
            if gradient:
                for component in range(2):grad[:,component]+=self.near_grad[component]@a
        if d is not None and self.near_storage:out+=self.near_dip@d
        result=np.empty_like(out);result[self.order]=out
        if gradient:
            g=np.empty_like(grad);g[self.order]=grad
            return (result[:,0],g[:,:,0]) if vector else (result,g)
        return result[:,0] if vector else result


def direct(points, normals, k, mono=None, dip=None, rows=None):
    """Reference: the same sum evaluated directly for the selected target rows."""
    x = np.asarray(points, float); rows = np.arange(len(x)) if rows is None else np.asarray(rows)
    out = 0
    dvec = x[rows][:, None, :] - x[None, :, :]; r = np.hypot(dvec[..., 0], dvec[..., 1])
    r[np.arange(len(rows)), rows] = 1.0
    g = 0.25j * hankel1(0, k * r); g[np.arange(len(rows)), rows] = 0
    if mono is not None:
        out = out + g @ mono
    if dip is not None:
        h = 0.25j * k * hankel1(1, k * r) * np.einsum('ijk,jk->ij', dvec, normals) / r
        h[np.arange(len(rows)), rows] = 0
        out = out + h @ dip
    return out
