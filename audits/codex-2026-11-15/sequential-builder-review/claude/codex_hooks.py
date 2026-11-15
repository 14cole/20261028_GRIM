"""Research-only inverse packing with a bounded conversion and double fallback.

Retained-storage checks and the process RAM admission are unchanged.
"""
import numpy as np
from hooks_original import memory
RECORD = {'packing': [], 'residual_products': [], 'conversions': []}
CHUNK = 65536

def convert(a):
    """Accept a finite complex64 conversion only within eps32 * component scale.

    A wholly tiny array whose meaningful scale is below float32 is kept in
    double. This also handles overflow, and measures component underflow even
    when only one component of a complex value disappears.
    """
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        small = a.astype(np.complex64)
    scale = error = lost_max = 0.
    lost_count = 0
    finite = True
    for start in range(0, a.size, CHUNK):
        x = a.flat[start:start+CHUNK]
        y = small.flat[start:start+CHUNK]
        if not np.isfinite(x).all():
            raise FloatingPointError('Nonfinite source inverse factor')
        finite = finite and bool(np.isfinite(y).all())
        for before, after in ((x.real,y.real), (x.imag,y.imag)):
            scale = max(scale, float(np.max(np.abs(before), initial=0.)))
            error = max(error, float(np.max(np.abs(before-after), initial=0.)))
            lost = (before != 0) & (after == 0)
            lost_count += int(np.count_nonzero(lost))
            lost_max = max(lost_max, float(np.max(np.abs(before[lost]), initial=0.)))
    # Compare by division so eps * scale cannot underflow to zero.
    relative = error/scale if scale else 0.
    accept = finite and relative <= np.finfo(np.float32).eps
    return (small if accept else a), dict(accepted=bool(accept),
        component_scale=scale, relative_max_component_error=relative,
        lost_components=lost_count, max_lost_component=lost_max,
        reason='bounded conversion' if accept else 'retain double: conversion exceeds bound')

def install(spec):
    mode = spec.get('packing', 'none')
    if mode in ('none','construction'):
        import hooks_original
        hooks_original.install(spec)
        RECORD.update(hooks_original.RECORD)
        return
    if mode != 'bounded':
        raise ValueError(mode)
    from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
    original = HMatrixSystem.build
    def build(self,*args,**kwargs):
        node = original(self,*args,**kwargs)
        if node.leaf:
            return node
        saved = 0
        for key in ('v12','v21','e1','e2'):
            a = getattr(node,key)
            if a.dtype != np.complex128:
                continue
            # Full converted array plus bounded validation temporaries; original
            # remains charged to self.bytes throughout conversion and validation.
            additional = a.size*8 + 80*min(a.size,CHUNK)
            with self.construction.step('bounded research inverse packing',additional):
                small, record = convert(a)
                delta = a.nbytes-small.nbytes
                setattr(node,key,small)
                self.bytes -= delta
                saved += delta
                RECORD['conversions'].append(dict(n=node.n,key=key,**record))
        RECORD['packing'].append(dict(n=node.n,saved_bytes=saved,
            accounted_bytes=self.bytes,**memory()))
        return node
    HMatrixSystem.build = build
