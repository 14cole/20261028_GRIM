"""Combined research operator: Claude panel moments plus corrected nodal near.

No production import or routing change. P1 only; retains the original FMM
support-size guard. The near compression stopping test remains sampled.
"""
import time
import numpy as np
from scipy import sparse
from moment_galerkin import MomentFar, streamed_near
from hybrid_galerkin import NearOracle, HierarchicalNear


def array_bytes(obj):
    """Unique reachable NumPy backing buffers, including sparse/geometry arrays.

    Python object overhead and native library workspaces are excluded; RSS is
    measured separately. Never includes globals or traverses callables.
    """
    seen, buffers = set(), set()
    def visit(x):
        if id(x) in seen: return 0
        seen.add(id(x))
        if isinstance(x, np.ndarray):
            root = x
            while isinstance(root.base, np.ndarray): root = root.base
            # SciPy data/index views can share a bytearray through memoryview.
            base = root.base
            if isinstance(base, memoryview):
                key = id(base.obj); size = base.nbytes
            else: key, size = id(root), root.nbytes
            if key in buffers: return 0
            buffers.add(key); return size
        if sparse.issparse(x): return sum(visit(a) for a in (x.data, x.indices, x.indptr))
        if isinstance(x, dict): return sum(visit(v) for v in x.values())
        if isinstance(x, (list, tuple)): return sum(visit(v) for v in x)
        if not callable(x):
            count = visit(vars(x)) if hasattr(x, '__dict__') else 0
            for cls in type(x).__mro__:
                slots = getattr(cls, '__slots__', ())
                if isinstance(slots, str): slots = (slots,)
                count += sum(visit(getattr(x, s)) for s in slots
                             if s not in ('__dict__','__weakref__') and hasattr(x, s))
            return count
        return 0
    return visit(obj)


class MomentHybrid:
    def __init__(self, mesh, k, mode='hybrid_nodal', tol=1e-13, order=8, separation=2, digits=10):
        started = time.perf_counter()
        self.mesh, self.k, self.n = mesh, k, len(mesh.nodes)
        oracle = NearOracle(mesh, k, order)
        if oracle.g.node_ids.shape[1] != 2: raise ValueError('P1 only')
        self.far = MomentFar(oracle.g, k, order=order, separation=separation, digits=digits)
        self.mode = mode
        if mode == 'stream':
            self.corrections, self.near_bytes, self.near_pairs, oracle = streamed_near(mesh, k, self.far, order)
        elif mode == 'hybrid_nodal':
            plan = self.far.plan
            member = np.empty(self.far.P, int)
            member[self.far.order_p] = self.far.leaf_of_panel
            panels = [np.flatnonzero(member == i) for i in range(len(plan.leaf_start))]
            self.near = HierarchicalNear(oracle, panels, plan.leaf_neighbors, tol=tol, nodal=True)
            self.near_pairs = sum(len(panels[i])*sum(len(panels[j]) for j in js)
                                  for i, js in enumerate(plan.leaf_neighbors))
            assert self.near.covered_pairs == self.near_pairs
            self.near_bytes = self.near.bytes
        else: raise ValueError(mode)
        self.kernel_seconds = oracle.seconds
        self.queried_pairs = oracle.pairs
        self.retained_bytes = array_bytes(self)
        self.setup_seconds = time.perf_counter()-started

    def apply(self, x, kind='S'):
        x = np.asarray(x, complex)
        vector = x.ndim == 1
        if vector: x = x[:, None]
        if x.ndim != 2 or x.shape[0] != self.n or not np.all(np.isfinite(x)):
            raise ValueError('Invalid RHS')
        if kind not in ('S', 'K', 'KP', 'W'): raise ValueError(kind)
        local = self.near.apply(x, kind) if self.mode == 'hybrid_nodal' else self.corrections[kind] @ x
        y = self.far.apply(x, kind) + local
        return y[:, 0] if vector else y
