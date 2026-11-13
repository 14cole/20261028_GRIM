"""Review probe for safe_cross.scaled_components: components that are zero on the 8 sampled rows but not elsewhere,
and components much smaller than their partners (physical-unit scaling)."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.environ['GRIM_ROOT']+'/tools/GHOST')
from safe_cross import scaled_components
from ghost_backend.compressed.hmatrix import HMatrixRejected
rng = np.random.default_rng(5); m, n = 72, 80
def lowrank(r): return (rng.normal(size=(m, r))+1j*rng.normal(size=(m, r)))@(rng.normal(size=(r, n))+1j*rng.normal(size=(r, n)))
a = lowrank(3); sample = np.unique(np.linspace(0, m-1, 8, dtype=int)); out = []
def run(label, values):
    def fetch(rows=None, cols=None):
        r = np.arange(m) if rows is None else rows; c = np.arange(n) if cols is None else cols
        return [z[np.ix_(r, c)] for z in values]
    try:
        f, est = scaled_components(fetch, (m, n), 1e-13, np.random.default_rng(8), 36)
        errs = [float(np.linalg.norm(u@v-z)/max(np.linalg.norm(z), 1e-300)) for z, (u, v) in zip(values, f)]
        out.append(dict(case=label, relative_errors=errs, ranks=[u.shape[1] for u, v in f], component_norms=[float(np.linalg.norm(z)) for z in values]))
    except HMatrixRejected as e:
        out.append(dict(case=label, rejected=str(e)))
for size in (1.0, 1e-6, 1e-12, 1e-15, 1e-20):
    hidden = lowrank(2)*size; hidden[sample] = 0          # zero on every sampled row, nonzero on the others
    run('zero on sampled rows, size %g elsewhere' % size, [a, hidden, 2*a])
for size in (1e-6, 1e-12, 1e-20):
    run('small everywhere, size %g' % size, [a, lowrank(2)*size, 2*a])
print(json.dumps(out, indent=1))

