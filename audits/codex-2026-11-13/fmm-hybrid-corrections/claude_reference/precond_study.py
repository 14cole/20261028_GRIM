"""Preconditioner comparison for the P1 dielectric transmission system (TE/TM), research only.

The operator is the dense assembled system (GHOST's own formulation); the FMM operators agree with it to
about 1e-13, so iteration counts carry over. What is compared is the preconditioner: its size, its setup
and the GMRES iterations it gives, for mesh refinement at fixed k and for growing electrical size.
Every preconditioner is built only from matrix entries inside the FMM near field (or a subset).

usage: python precond_study.py '<json: n, k, kind (TE|TM), eps [re, im], star, angles>'
"""
import json, os, sys, time
import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse import csc_matrix, csr_matrix
from scipy.sparse.linalg import LinearOperator, gmres, spilu
sys.path.insert(0, os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.twod.formulations import dielectric
from ghost_backend.twod.assembly.geometry_plan import AssemblyGeometry
from ghost_backend.linalg.workspace import equilibrated_scaling_and_norm_1
from ghost_backend.execution.options import execution_scope, cpu_allocation_scope
from fmm_galerkin import circle_mesh
from moment_galerkin import MomentFar
from types import SimpleNamespace
spec = json.loads(sys.argv[1]); n = spec['n']; k0 = float(spec['k']); kind = spec['kind']; epsr = complex(*spec.get('eps', [3., -.08])); k1 = k0*np.sqrt(epsr)
mesh = circle_mesh(n, star=spec.get('star', True), inward=True); angles = np.array(spec.get('angles', [0., 47.]))
out = dict(spec, results=[]); RESTART = spec.get('restart', 80); MAXCYC = spec.get('cycles', 6); out.update(restart=RESTART, max_iterations=RESTART*MAXCYC)
with cpu_allocation_scope(1), execution_scope({'assembly_threads': 1, 'blas_threads': 1}):
    infos = [SimpleNamespace(mu_minus=1., mu_plus=1., eps_minus=1., eps_plus=epsr, k_plus=k1, k_minus=k0, plus_region=1, minus_region=0)]
    t = time.perf_counter(); a = dielectric.assemble_system(mesh, infos, kind, k0); b = dielectric.rhs_many(mesh, k0, angles); out['dense_assembly_s'] = round(time.perf_counter()-t, 1)
    rows, cols, norma = equilibrated_scaling_and_norm_1(a); A = a/rows[:, None]/cols[None, :]; nd = len(A); B = b/rows[:, None]
    out.update(unknowns=nd, dense_mib=round(A.nbytes/2**20, 1))
    g = AssemblyGeometry(mesh)
    def tree(k, separation):
        far = MomentFar(g, k, separation=separation); P = far.P; member = np.empty(P, int); member[far.order_p] = far.leaf_of_panel
        leaf_of_node = np.full(n, -1); leaf_of_node[g.node_ids[:, 0]] = member                       # a node belongs to the leaf of the panel it starts
        return far.plan, member, leaf_of_node
    def near_mask(k, separation):
        plan, member, _ = tree(k, separation); nl = len(plan.leaf_start); adj = np.zeros((nl, nl), bool)
        for i, js in enumerate(plan.leaf_neighbors): adj[i, js] = True
        pan = adj[member][:, member]                                                                   # panel-pair near mask
        m = np.zeros((n, n), bool)
        for a_ in range(2):
            for b_ in range(2): m[np.ix_(g.node_ids[:, a_], g.node_ids[:, b_])] |= pan
        return m, plan, float(pan.mean())
    def system_mask(sep):
        me, plan_e, fe = near_mask(k0, sep); mi, plan_i, fi = near_mask(k1, sep)
        return np.block([[me, mi], [me, mi]]), fe, fi                                                 # exterior operators act on u, interior on v
    def run(name, pre, setup_s, nbytes, extra=None):
        its = []; res = []; t = time.perf_counter(); ok = []
        for c in range(B.shape[1]):
            hist = []; y, info = gmres(LinearOperator((nd, nd), matvec=lambda v: A@v, dtype=complex), B[:, c], M=pre, rtol=1e-12, atol=0, restart=RESTART, maxiter=MAXCYC,
                                       callback=lambda v: hist.append(1), callback_type='pr_norm')
            its.append(len(hist)); ok.append(info == 0); res.append(float(np.linalg.norm(A@y-B[:, c])/np.linalg.norm(B[:, c])))
        row = dict(preconditioner=name, iterations=its, converged=ok, true_residual=max(res), solve_s=round(time.perf_counter()-t, 2), setup_s=round(setup_s, 2),
                   factor_mib=round(nbytes/2**20, 2), factor_over_dense=round(nbytes/A.nbytes, 3)); row.update(extra or {})
        out['results'].append(row); print(json.dumps(row), file=sys.stderr, flush=True)
    run('none', None, 0., 0)
    for sep, drop, fill in ((2, 1e-3, 5), (2, 1e-2, 3), (1, 1e-3, 5)):
        t = time.perf_counter(); mask, fe, fi = system_mask(sep); near = csc_matrix(np.where(mask, A, 0))
        try:
            ilu = spilu(near, drop_tol=drop, fill_factor=fill); nb = sum(z.data.nbytes+z.indices.nbytes+z.indptr.nbytes for z in (ilu.L, ilu.U))
            run('near-ilu sep=%d drop=%g' % (sep, drop), LinearOperator((nd, nd), matvec=ilu.solve, dtype=complex), time.perf_counter()-t, nb,
                dict(near_share_exterior=round(fe, 3), near_share_interior=round(fi, 3), near_matrix_mib=round((near.data.nbytes+near.indices.nbytes)/2**20, 1)))
        except Exception as exc:
            out['results'].append(dict(preconditioner='near-ilu sep=%d drop=%g' % (sep, drop), error=str(exc)[:200]))
    from scipy.sparse.linalg import splu
    for sep in (1, 2):
        t = time.perf_counter(); mask, fe, fi = system_mask(sep); lu = splu(csc_matrix(np.where(mask, A, 0)))
        nb = sum(z.data.nbytes+z.indices.nbytes+z.indptr.nbytes for z in (lu.L, lu.U))
        run('near exact sparse LU sep=%d' % sep, LinearOperator((nd, nd), matvec=lu.solve, dtype=complex), time.perf_counter()-t, nb)
    for width in spec.get('bands', [8, 32]):                                 # banded in boundary order: nodes within `width` panels, exact LU
        t = time.perf_counter(); i = np.arange(n); d = np.abs(i[:, None]-i[None, :]); m = np.minimum(d, n-d) <= width
        lu = splu(csc_matrix(np.where(np.block([[m, m], [m, m]]), A, 0))); nb = sum(z.data.nbytes+z.indices.nbytes+z.indptr.nbytes for z in (lu.L, lu.U))
        run('cyclic band +-%d nodes, exact LU' % width, LinearOperator((nd, nd), matvec=lu.solve, dtype=complex), time.perf_counter()-t, nb)
    t = time.perf_counter(); i = np.arange(n); blocks = np.linalg.inv(np.stack([np.stack([A[i, i], A[i, i+n]], 1), np.stack([A[i+n, i], A[i+n, i+n]], 1)], 1))
    run('node 2x2 blocks', LinearOperator((nd, nd), matvec=lambda v: np.einsum('nab,bn->an', blocks, v.reshape(2, n)).ravel(), dtype=complex), time.perf_counter()-t, blocks.nbytes)
    # low-accuracy hierarchical copy of the whole system, factorised exactly: the best a loose compressed factorisation could do
    planh, memberh, leafh = tree(k0, 1); nlh = len(planh.leaf_start); ownh = [np.flatnonzero(leafh == i) for i in range(nlh)]; nearh = [set(map(int, js)) for js in planh.leaf_neighbors]
    scale = np.linalg.norm(A, 2)
    for eps in spec.get('lowrank', [1e-1, 1e-2, 1e-3]):
        t = time.perf_counter(); C = A.copy(); stored = 0; maxrank = 0
        for i in range(nlh):
            for j in range(nlh):
                if not len(ownh[i]) or not len(ownh[j]): continue
                for bi in (0, n):
                    for bj in (0, n):
                        ix = np.ix_(ownh[i]+bi, ownh[j]+bj)
                        if j in nearh[i]: stored += len(ownh[i])*len(ownh[j]); continue
                        u, sv, vh = np.linalg.svd(A[ix], full_matrices=False); r = int(np.sum(sv > eps*scale)); maxrank = max(maxrank, r)
                        C[ix] = (u[:, :r]*sv[:r])@vh[:r]; stored += r*(len(ownh[i])+len(ownh[j]))
        lu = lu_factor(C)
        run('exact LU of rank-truncated system, eps=%g' % eps, LinearOperator((nd, nd), matvec=lambda v, lu=lu: lu_solve(lu, v), dtype=complex), time.perf_counter()-t, stored*16,
            dict(note='factor_mib is the storage of the truncated operator, a lower bound for a compressed factorisation', max_block_rank=maxrank, approximation_error=float(np.linalg.norm(C-A, 2)/scale)))
    # domain decomposition on the exterior tree's leaves: u and v unknowns of a leaf's nodes form one subdomain
    plan, member, leaf_of_node = tree(k0, 1); nl = len(plan.leaf_start); adj = [np.asarray(js) for js in plan.leaf_neighbors]
    own = [np.flatnonzero(leaf_of_node == i) for i in range(nl)]
    def schwarz(overlap, restricted=True):
        t = time.perf_counter(); doms = []; nbytes = 0
        for i in range(nl):
            if not len(own[i]): continue
            nodes = own[i] if not overlap else np.unique(np.concatenate([own[j] for j in adj[i]]))
            idx = np.concatenate([nodes, nodes+n]); lu = lu_factor(A[np.ix_(idx, idx)]); nbytes += lu[0].nbytes
            keep = np.isin(nodes, own[i]) if restricted else np.ones(len(nodes), bool)
            doms.append((idx, lu, np.concatenate([keep, keep])))
        def apply(v):
            y = np.zeros(nd, complex)
            for idx, lu, keep in doms:
                z = lu_solve(lu, v[idx]); y[idx[keep]] += z[keep]
            return y
        return LinearOperator((nd, nd), matvec=apply, dtype=complex), time.perf_counter()-t, nbytes, max(len(d[0]) for d in doms)
    plan2, member2, leaf2 = tree(k0, 2); adj2 = [np.asarray(js) for js in plan2.leaf_neighbors]
    for label, overlap in (('block-jacobi by leaf', False), ('restricted Schwarz, one-leaf overlap', True), ('restricted Schwarz, two-leaf overlap', 2))[:3 if n <= 1024 else 2]:
        if overlap == 2: adj = adj2; own = [np.flatnonzero(leaf2 == i) for i in range(len(adj2))]; nl = len(adj2)
        pre, ts, nb, biggest = schwarz(overlap); run(label, pre, ts, nb, dict(subdomains=nl, largest_subdomain=int(biggest)))
print(json.dumps(out))
