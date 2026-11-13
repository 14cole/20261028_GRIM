"""Review probe of ghost_backend.linalg.products.adjoint_product against the expression it replaces."""
import os, sys, json, itertools, tracemalloc
import numpy as np
sys.path.insert(0, os.environ['GRIM_ROOT']+'/tools/GHOST')
from ghost_backend.linalg.products import adjoint_product
rng = np.random.default_rng(77); out = dict(cases=0, not_bitwise=[], dtype_mismatch=[], shape_mismatch=[], aliasing=[], max_rel=0.0, branches=dict(direct=0, conjugated=0))
def rand(shape, dt):
    x = rng.normal(size=shape).astype(dt)
    if np.issubdtype(dt, np.complexfloating): x = x+1j*rng.normal(size=shape).astype(dt)
    return x.astype(dt)
dts = [np.complex128, np.complex64, np.float64, np.float32]
for (m, r), width, da, db, layout in itertools.product([(300, 12), (12, 300), (64, 64), (1, 5), (5, 1), (0, 3), (3, 0), (2000, 40)], [None, 1, 2, 7, 40, 400], dts, dts, ['C', 'F', 'slice', 'rev']):
    a = rand((m, r), da); b = rand((m,) if width is None else (m, width), db)
    if layout == 'F': a = np.asfortranarray(a); b = np.asfortranarray(b)
    if layout == 'slice': a = np.repeat(a, 2, axis=1)[:, ::2]; b = np.repeat(b, 2, axis=0)[::2]
    if layout == 'rev': a = a[::-1]; b = b[::-1]
    a0, b0 = a.copy(), b.copy(); ref = a.conj().T @ b; got = adjoint_product(a, b); out['cases'] += 1
    osize = a.shape[1]*(1 if b.ndim == 1 else b.shape[1])
    out['branches']['direct' if a.nbytes <= b.nbytes+osize*np.result_type(a, b).itemsize else 'conjugated'] += 1
    tag = dict(shape=[m, r], width=width, a=np.dtype(da).name, b=np.dtype(db).name, layout=layout)
    if got.dtype != ref.dtype: out['dtype_mismatch'].append(tag)
    if got.shape != ref.shape: out['shape_mismatch'].append(tag); continue
    if not (np.array_equal(a, a0) and np.array_equal(b, b0)) or np.shares_memory(got, a) or np.shares_memory(got, b): out['aliasing'].append(tag)
    if ref.size and abs(ref).max() > 0:
        rel = float(abs(got-ref).max()/max(abs(ref).max(), 1e-300)); out['max_rel'] = max(out['max_rel'], rel); key='double' if np.finfo(a.dtype).bits == 64 and np.finfo(b.dtype).bits == 64 else 'single_involved'; out.setdefault('max_rel_'+key,0.0); out['max_rel_'+key]=max(out['max_rel_'+key],rel)
        if not np.array_equal(got, ref): out['not_bitwise'].append(dict(tag, rel=rel))
# special values propagate the same way
a = rand((50, 4), np.complex128); b = rand((50, 2), np.complex128); a[3, 1] = np.nan; b[7, 0] = np.inf
with np.errstate(all='ignore'): out['nonfinite_pattern_same'] = bool(np.array_equal(np.isfinite(adjoint_product(a, b)), np.isfinite(a.conj().T @ b)))
# temporary memory: tall factor, two right-hand sides
a = rand((8192, 256), np.complex128); b = rand((8192, 2), np.complex128)
for name, fn in (('old', lambda: a.conj().T @ b), ('new', lambda: adjoint_product(a, b))):
    tracemalloc.start(); fn(); out['temporary_mib_'+name] = tracemalloc.get_traced_memory()[1]/2**20; tracemalloc.stop()
out['not_bitwise_count'] = len(out['not_bitwise']); out['not_bitwise'] = out['not_bitwise'][:5]
print(json.dumps(out, indent=1))
