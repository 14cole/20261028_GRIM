"""Research prototype: P1 Galerkin S, K, K', W with a panel-moment far field.

Independent implementation of the adapter requested in Codex's CLAUDE_TASKS.md.
Not part of GHOST.

The far field uses the diagonal-form FMM tree, interaction lists and
translations of cached_fmm.HelmholtzFMM, built on ONE point per panel (its
centre).  Instead of phase tables at eight Gauss points per panel (E, Eout and
dip: 24 complex rows per panel), it stores the plane-wave moments of the two
linear basis functions of each panel: 2 source rows and 2 target rows.

    source[p, a, q] = L_p * sum_g w_g phi_a(t_g) exp(-i kappa s_q.(y_pg - c))
    target[p, a, q] = L_p * sum_g w_g phi_a(t_g) exp(+i kappa s_q.(y_pg - c))

with kappa = conj(k) (the tree works with H0^(1); GHOST's kernel is recovered
as -conj(F(conj x))).  Normals are constant on a panel, so the double-layer and
normal-derivative factors are -/+ i kappa (s.n_p) times the same moments, and
the derivative moments of the Maue form of W are +/-(m_0 + m_1)/L_p.  Moments
are built in bounded tiles; the eight-point tables are never allocated.  When
the tree falls back to the all-near treatment no far data is stored at all.

The near field is supplied by the caller (any object with corrections[kind] @ x).
"""
import time
import numpy as np
from cached_fmm import HelmholtzFMM, _resample


class MomentFar:
    def __init__(self, geometry, k, order=8, digits=10, separation=2, leaf_wavelengths=1.5, tile_panels=256):
        g = self.g = geometry
        self.k = k; kappa = self.kappa = complex(k).conjugate()
        self.P = P = len(g.lengths)
        t0 = time.perf_counter()
        self.plan = plan = HelmholtzFMM(g.centers, g.normals, kappa, digits=digits, leaf_wavelengths=leaf_wavelengths,
                                        separation=separation, gradients=False, near_storage=False,
                                        support_radius=float(max(g.lengths)) / 2, build_point_phases=False)
        # the plan's own one-point phase tables are not used
        plan.E = plan.Eout = plan.dip = None
        if max(g.lengths) > .2 * plan.side[-1]:
            raise ValueError('Panel too long for the box-support bound')
        self.direct = bool(plan.low_frequency_direct)
        self.order_p = plan.order                     # panels in tree order
        self.leaf_of_panel = plan.leaf_of_point       # for tree-ordered panels
        self.source = self.target = self.sdotn = None
        if not self.direct:
            q, w = np.polynomial.legendre.leggauss(order); q = (q + 1) / 2; w = w / 2
            phi = np.column_stack((1 - q, q))                                  # (order, 2)
            Q = plan.Q[plan.levels]; s = plan.s[plan.levels]                   # (Q, 2)
            centre = plan.lo + (plan.boxes[plan.levels][self.leaf_of_panel] + 0.5) * plan.side[plan.levels]
            self.source = np.empty((P, 2, Q), complex); self.target = np.empty((P, 2, Q), complex)
            for a in range(0, P, tile_panels):
                ids = self.order_p[a:a + tile_panels]
                pts = g.p0[ids][:, None, :] + q[None, :, None] * g.segments[ids][:, None, :]      # (T, order, 2)
                phase = kappa * ((pts - centre[a:a + tile_panels][:, None, :]) @ s.T)            # (T, order, Q)
                wl = (g.lengths[ids][:, None, None] * w[None, :, None] * phi[None]).transpose(0, 2, 1)   # (T, 2, order)
                self.source[a:a + tile_panels] = wl @ np.exp(-1j * phase)
                self.target[a:a + tile_panels] = wl @ np.exp(1j * phase)
            self.sdotn = (g.normals[self.order_p] @ s.T)                        # (P, Q) real
        self.nodes = g.node_ids[self.order_p]                                  # (P, 2) in tree order
        self.lengths = g.lengths[self.order_p]; self.normals = g.normals[self.order_p]
        self.bytes = sum(a.nbytes for a in (self.source, self.target, self.sdotn) if a is not None) + plan_translation_bytes(plan)
        self.seconds = time.perf_counter() - t0

    # ---- translation of leaf multipoles to leaf locals (same passes as HelmholtzFMM.apply)
    def _translate(self, M_leaf):
        p = self.plan; levels = p.levels; B = M_leaf.shape[2]
        M = [None] * (levels + 1); M[levels] = M_leaf
        for l in range(levels, 2, -1):
            up = _resample(M[l], p.Q[l - 1]) * p.shift_up[l][:, :, None]
            parent = np.zeros((len(p.boxes[l - 1]), p.Q[l - 1], B), complex)
            np.add.at(parent, p.parent[l], up); M[l - 1] = parent
        Lc = None
        for l in range(2, levels + 1):
            loc = np.zeros_like(M[l])
            for tg, sr, T in p.m2l[l]:
                np.add.at(loc, tg, M[l][sr] * T[None, :, None])
            if Lc is not None:
                loc += _resample(Lc[p.parent[l]] * p.shift_down[l][:, :, None], p.Q[l])
            Lc = loc
        return Lc

    def _pass(self, coeff, src, tgt, tile=512):
        """coeff (P, 2, B) basis coefficients in tree order; src/tgt callables giving (T, 2, Q) moment slices.
        Returns (P, 2, B) tested values."""
        p = self.plan; P = self.P; B = coeff.shape[2]; Q = p.Q[p.levels]
        starts = p.leaf_start; M = np.empty((len(starts), Q, B), complex)
        ends = np.append(starts, P); first = 0
        while first < len(starts):                         # leaves in tiles of about `tile` panels
            last = max(first + 1, int(np.searchsorted(starts, starts[first] + tile)))
            i, j = int(starts[first]), int(ends[last])
            w = np.einsum('paq,pab->pqb', src(i, j), coeff[i:j])
            M[first:last] = np.add.reduceat(w, starts[first:last] - i, axis=0); first = last
        Lc = self._translate(M)
        out = np.empty((P, 2, B), complex)
        for i in range(0, P, tile):
            j = min(P, i + tile)
            out[i:j] = np.einsum('paq,pqb->pab', tgt(i, j), Lc[self.leaf_of_panel[i:j]]) * (0.25j / Q)
        return out

    def apply(self, x, kind):
        """Far-field part of the Galerkin operator applied to nodal vectors x (n, B), GHOST convention."""
        n, B = x.shape
        if self.direct:
            return np.zeros((n, B), complex)
        xc = np.conj(x)[self.nodes]                         # (P, 2, B), H1 space
        S, T = self.source, self.target; ik = 1j * self.kappa
        plain_s = lambda i, j: S[i:j]; plain_t = lambda i, j: T[i:j]
        if kind == 'S':
            tested = self._pass(xc, plain_s, plain_t)
        elif kind == 'K':                                   # dipole sources, factor -i kappa (s.n)
            tested = self._pass(xc, lambda i, j: S[i:j] * (-ik * self.sdotn[i:j])[:, None, :], plain_t)
        elif kind == 'KP':                                  # normal derivative at the target, +i kappa (s.n)
            tested = self._pass(xc, plain_s, lambda i, j: T[i:j] * (ik * self.sdotn[i:j])[:, None, :])
        elif kind == 'W':
            sign = np.array([-1.0, 1.0])
            ds = lambda i, j: (S[i:j].sum(axis=1) / self.lengths[i:j, None])[:, None, :] * sign[None, :, None]
            dt = lambda i, j: (T[i:j].sum(axis=1) / self.lengths[i:j, None])[:, None, :] * sign[None, :, None]
            a = self._pass(xc, ds, dt)                      # derivative-derivative term
            z = 0
            for c in range(2):
                nc = self.normals[:, c]
                z = z + self._pass(xc, lambda i, j: S[i:j] * nc[i:j, None, None], lambda i, j: T[i:j] * nc[i:j, None, None])
            y = np.zeros((n, B), complex)
            np.add.at(y, self.nodes[:, 0], -np.conj(a[:, 0]) + self.k ** 2 * np.conj(z[:, 0]))
            np.add.at(y, self.nodes[:, 1], -np.conj(a[:, 1]) + self.k ** 2 * np.conj(z[:, 1]))
            return y
        else:
            raise ValueError(kind)
        y = np.zeros((n, B), complex)
        np.add.at(y, self.nodes[:, 0], -np.conj(tested[:, 0])); np.add.at(y, self.nodes[:, 1], -np.conj(tested[:, 1]))
        return y


def plan_translation_bytes(plan):
    total = 0
    for l in range(2, plan.levels + 1):
        total += sum(T.nbytes + tg.nbytes + sr.nbytes for tg, sr, T in plan.m2l[l])
    for l in range(1, plan.levels + 1):
        total += plan.shift_up[l].nbytes + plan.shift_down[l].nbytes
    return total


def streamed_near(mesh, k, far, order=8, row_batch=64):
    """Nodal CSR near matrices for S, K, W over the panel pairs the far field leaves out (bounded chunks).
    Same construction as Codex's 'stream' mode, on this adapter's own tree."""
    from scipy.sparse import coo_matrix, csr_matrix
    from hybrid_galerkin import NearOracle
    oracle = NearOracle(mesh, k, order); g = oracle.g; n = len(mesh.nodes); plan = far.plan
    member = np.empty(far.P, int); member[far.order_p] = far.leaf_of_panel
    panels = [np.flatnonzero(member == i) for i in range(len(plan.leaf_start))]; neighbors = plan.leaf_neighbors
    near_pairs = sum(len(panels[i]) * sum(len(panels[j]) for j in js) for i, js in enumerate(neighbors))
    data = [bytearray() for _ in range(3)]; indices = [bytearray() for _ in range(3)]
    ptr = [np.zeros(n + 1, dtype=np.int64) for _ in range(3)]; offset = [0] * 3
    for a in range(0, n, row_batch):
        b = min(n, a + row_batch); ip = np.flatnonzero(np.any((g.node_ids >= a) & (g.node_ids < b), axis=1)); pi = []; pj = []
        for i in ip:
            j = np.concatenate([panels[v] for v in neighbors[member[i]]]); pi.append(np.full(len(j), i)); pj.append(j)
        pi = np.concatenate(pi); pj = np.concatenate(pj); v = oracle.pairs_values(pi, pj)
        r = np.repeat(g.node_ids[pi], 2, axis=1).ravel(); c = np.tile(g.node_ids[pj], (1, 2)).ravel(); keep = (r >= a) & (r < b)
        for z in range(3):
            csr = coo_matrix((v[z].ravel()[keep], (r[keep] - a, c[keep])), shape=(b - a, n)).tocsr()
            data[z].extend(csr.data.tobytes()); indices[z].extend(csr.indices.astype(np.int32, copy=False).tobytes())
            ptr[z][a + 1:b + 1] = csr.indptr[1:] + offset[z]; offset[z] += csr.nnz
    corr = {name: csr_matrix((np.frombuffer(data[z], complex), np.frombuffer(indices[z], np.int32), ptr[z]), shape=(n, n), copy=False)
            for z, name in enumerate(['S', 'K', 'W'])}
    corr['KP'] = corr['K'].T
    nbytes = sum(m.data.nbytes + m.indices.nbytes + m.indptr.nbytes for m in (corr['S'], corr['K'], corr['W']))
    return corr, nbytes, near_pairs, oracle


class MomentGalerkin:
    def __init__(self, mesh, k, order=8, digits=10, separation=2):
        from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
        t = time.perf_counter(); self.mesh = mesh; self.n = len(mesh.nodes); self.k = k
        self.far = MomentFar(AssemblyGeometry(mesh), k, order, digits, separation)
        self.corrections, self.near_bytes, self.near_pairs, oracle = streamed_near(mesh, k, self.far, order)
        self.kernel_seconds = oracle.seconds
        self.retained_bytes = self.far.bytes + self.near_bytes
        self.setup_seconds = time.perf_counter() - t

    def apply(self, x, kind='S'):
        x = np.asarray(x); vector = x.ndim == 1
        if vector: x = x[:, None]
        y = self.far.apply(x, kind) + self.corrections[kind] @ x
        return y[:, 0] if vector else y

