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
    def __init__(self, points, normals, k, digits=8, leaf_wavelengths=0.75, max_leaf_points=None):
        self.k = k = float(k)
        self.x = x = np.asarray(points, float)
        self.nrm = np.asarray(normals, float)
        self.n = n = len(x)
        lo = x.min(axis=0); span = float((x.max(axis=0) - lo).max()) * (1 + 1e-9) + 1e-300
        wavelength = 2 * math.pi / k
        levels = max(2, int(math.floor(math.log2(span / (leaf_wavelengths * wavelength)))))
        self.levels = levels                       # leaf level index; root is level 0
        self.side = [span / 2 ** l for l in range(levels + 1)]
        self.lo = lo
        # ---- tree: nonempty boxes per level, integer coordinates
        ij = np.clip(np.floor((x - lo) / self.side[levels]).astype(np.int64), 0, 2 ** levels - 1)
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
            Lq = _truncation(k * self.side[l] * math.sqrt(2.0), digits)
            self.L[l] = Lq; self.Q[l] = 2 * Lq + 1
            th = 2 * math.pi * np.arange(self.Q[l]) / self.Q[l]
            self.theta[l] = th; self.s[l] = np.stack([np.cos(th), np.sin(th)], 1)
        # ---- interaction lists and translation tables (levels >= 2)
        self.m2l = [None] * (levels + 1)
        self.shift_up = [None] * (levels + 1)
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
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        q = pindex.get((int(pi) + di, int(pj) + dj))
                        if q is None:
                            continue
                        for c in children[q]:
                            ox, oy = int(b[c][0] - bi), int(b[c][1] - bj)
                            if max(abs(ox), abs(oy)) > 1:
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
            self.shift_up[l] = np.exp(-1j * k * (off @ self.s[l - 1].T))   # (nboxes_l, Q_{l-1})
        # ---- leaf expansions
        centre = lo + (self.boxes[levels][self.leaf_of_point] + 0.5) * self.side[levels]
        xs = x[order]; rel = xs - centre
        phase = k * (rel @ self.s[levels].T)                               # (n, Q_leaf)
        self.E = np.exp(-1j * phase)                                       # source pattern factor
        self.dip = -1j * k * (self.nrm[order] @ self.s[levels].T)          # dipole factor  (-ik s.n)
        # ---- near field: adjacent leaves, direct, self excluded
        b = self.boxes[levels]; index = {(int(i), int(j)): t for t, (i, j) in enumerate(b)}
        ends = np.append(start, n)
        rows, cols = [], []
        for t, (bi, bj) in enumerate(b):
            mine = np.arange(ends[t], ends[t + 1])
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    q = index.get((int(bi) + di, int(bj) + dj))
                    if q is None:
                        continue
                    other = np.arange(ends[q], ends[q + 1])
                    rows.append(np.repeat(mine, len(other))); cols.append(np.tile(other, len(mine)))
        rows = np.concatenate(rows); cols = np.concatenate(cols)
        keep = rows != cols; rows, cols = rows[keep], cols[keep]
        dvec = xs[rows] - xs[cols]; r = np.hypot(dvec[:, 0], dvec[:, 1])
        mono = 0.25j * hankel1(0, k * r)
        dipo = 0.25j * k * hankel1(1, k * r) * np.einsum('ij,ij->i', dvec, self.nrm[order][cols]) / r
        self.near_mono = sparse.csr_matrix((mono, (rows, cols)), shape=(n, n))
        self.near_dip = sparse.csr_matrix((dipo, (rows, cols)), shape=(n, n))
        self.near_pairs = len(rows)
        self.bytes = (self.E.nbytes + self.dip.nbytes + self.near_mono.data.nbytes * 2 + self.near_mono.indices.nbytes * 2
                      + sum(T.nbytes for l in range(2, levels + 1) for _, _, T in self.m2l[l])
                      + sum(a.nbytes for a in self.shift_up[1:]))

    def apply(self, mono=None, dip=None):
        """u = S-type sum of monopoles `mono` plus D-type sum of dipoles `dip`; arrays (n,) or (n, B)."""
        ref = mono if mono is not None else dip
        vector = ref.ndim == 1
        a = None if mono is None else (mono[:, None] if vector else mono)[self.order]
        d = None if dip is None else (dip[:, None] if vector else dip)[self.order]
        B = (a if a is not None else d).shape[1]
        levels = self.levels
        # P2M at the leaves
        w = 0
        if a is not None:
            w = self.E[:, :, None] * a[:, None, :]
        if d is not None:
            w = w + (self.E * self.dip)[:, :, None] * d[:, None, :]
        M = [None] * (levels + 1)
        M[levels] = np.add.reduceat(w, self.leaf_start, axis=0)             # (nleaf, Q, B)
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
                down = Lc[self.parent[l]] * np.conj(self.shift_up[l])[:, :, None]
                loc += _resample(down, self.Q[l])
            Lc = loc
        # L2P
        out = np.einsum('nq,nqb->nb', np.conj(self.E), Lc[self.leaf_of_point]) * (0.25j / self.Q[levels])
        if a is not None:
            out += self.near_mono @ a
        if d is not None:
            out += self.near_dip @ d
        result = np.empty_like(out); result[self.order] = out
        return result[:, 0] if vector else result


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
