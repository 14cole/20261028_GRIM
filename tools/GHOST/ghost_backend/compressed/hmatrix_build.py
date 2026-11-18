"""Sequential HMatrix inverse construction with scoped workspace accounting."""
import numpy as np
from ghost_backend.compressed.inverse import Node
from ghost_backend.linalg.hierarchical import HierarchicalRejected


def _solve_in_place(system, child, values, *live):
    # Range compression normally returns writable complex128 factors. Keep a
    # bounded copy path for other layouts/dtypes without losing its live charge.
    original_bytes = values.nbytes
    copied = values.dtype != np.complex128 or not values.flags.writeable
    if copied:
        size = values.size * np.dtype(np.complex128).itemsize
        system.check_storage(max(0, size-original_bytes))
        with system.construction.step('copy inverse child input', size, *live):
            values = np.array(values, dtype=np.complex128, copy=True)
        live = (*live, values)
    with system.construction.step('inverse child product (in place)',
                                  8*values.nbytes+1024**2, *live):
        child.solve_into(values, values)
    if copied:
        system.bytes += values.nbytes-original_bytes
    return values


def build(system, oracle, ids):
    """Build only an inverse of aligned HMatrix clusters, in double precision.

    Small nodes probe compression before their children so rejection can still
    fall back to a dense leaf. Larger nodes build children first, then consume
    each off-diagonal factor before constructing the next child product.
    """
    system.checkpoint()
    node = Node()
    node.n, node.leaf, node.checkpoint = len(ids), len(ids) <= system.leaf, system.checkpoint
    compressed = False
    if not node.leaf:
        mid = len(ids)//2
        left, right = ids[:mid], ids[mid:]
        if len(ids) <= system.DENSE_FALLBACK_LIMIT:
            before = system.bytes
            try:
                node.u12, node.v12, _ = system.compress_block(oracle, left, right)
                system.reserve(node.u12.nbytes+node.v12.nbytes)
                node.u21, node.v21, _ = system.compress_block(oracle, right, left)
                system.reserve(node.u21.nbytes+node.v21.nbytes)
                compressed = True
            except HierarchicalRejected:
                system.dense_fallbacks += 1
                system.largest_dense_fallback = max(system.largest_dense_fallback, len(ids))
                node.leaf, system.bytes = True, before
                for name in ('u12', 'u21', 'v12', 'v21'):
                    if hasattr(node, name):
                        delattr(node, name)
    if node.leaf:
        if len(ids) > system.DENSE_FALLBACK_LIMIT:
            raise HierarchicalRejected('HMatrix diagonal query exceeds its dense fallback limit.')
        raw_bytes = len(ids)**2*16
        system.check_storage(raw_bytes+8*len(ids))
        # Only these aligned diagonal subtrees have the validated 4q bound.
        # Generic or high-rank rectangular queries must not inherit it.
        with system.construction.step('leaf coefficients', 4*raw_bytes+1024**2):
            raw = oracle.get(ids, ids)
        system.leaves += 1
        node.lu = system.factor(raw)
        return node

    node.left, node.right = system.build(oracle, left), system.build(oracle, right)
    if not compressed:
        node.u12, node.v12, _ = system.compress_block(oracle, left, right)
        system.reserve(node.u12.nbytes+node.v12.nbytes)
    node.e1 = _solve_in_place(system, node.left, node.u12)
    del node.u12
    if not compressed:
        node.u21, node.v21, _ = system.compress_block(oracle, right, left)
        system.reserve(node.u21.nbytes+node.v21.nbytes)
    r, s = node.e1.shape[1], node.u21.shape[1]
    system.ranks.extend((r, s))
    system.check_storage(16*(r+s)**2+8*(r+s))
    with system.construction.step('Woodbury correction', 16*((r+s)**2+2*r*s)):
        small = np.eye(r+s, dtype=complex)
        small[r:, :r] = node.v21 @ node.e1
    # The correction matrix remains live while the second child solve runs.
    node.e2 = _solve_in_place(system, node.right, node.u21, small)
    del node.u21
    with system.construction.step('Woodbury correction', 16*2*r*s, small):
        small[:r, r:] = node.v12 @ node.e2
    node.lu = system.factor(small) if r+s else None
    return node
