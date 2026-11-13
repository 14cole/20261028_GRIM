"""Condition estimates and fields with condition certification on, for baseline/candidate comparison.
Exercises the adjoint paths the change touches: Compressed, opt-in Dense hierarchical (2D) and BoR hierarchical/compressed.
usage: GHOST_AUDIT_ROOT=<checkout> python claude_condition_compare.py out.json"""
import os, sys, json, warnings, inspect
os.environ["GHOST_HMATRIX_MIN_UNKNOWNS"] = "0"
sys.path.insert(0, '/home/user/20261028_GRIM/audits/claude-2026-11-10/regression')
import common, numpy as np
from common import scene, circle, bor_sphere
from ghost_backend.twod import solver as S
from ghost_backend.bor import dispatch as D
out = {}
def record(name, r):
    md = r["metadata"]; ch = md.get("channel_metadata", {})
    if not ch: out[name] = dict(amps=[[s.get(k) for k in sorted(s) if 'amp' in k] for s in r['samples']], condition={k: v for k, v in md.items() if 'condition' in k and not isinstance(v, (list, dict))}, backend=md.get('factorization')); return
    out[name] = dict(amps=[[s.get('rcs_amp_real'), s.get('rcs_amp_imag')] for s in r['samples']],
                     condition={p: ch[p].get("condition_est_max") for p in ch}, backend={p: ch[p].get('factorization', ch[p].get('linear_solver')) for p in ch})
cases2d = {'pec_two_circles': scene([("b", 2, "2 1 0 0 0", circle(.1, 300)), ("c", 2, "2 1 0 0 0", circle(.1, 300, x0=.201))]),
           'dielectric_circle': scene([("b", 3, "3 1 0 1 0", circle(.1, 400))], diel="1 3.0 -0.08 1.0 0.0")}
for name, g in ({} if os.environ.get('BOR_ONLY') else cases2d).items():
    for backend in ('compressed', 'hierarchical', 'dense'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = S.solve_monostatic_rcs_2d(g, [10.0], [0.0, 45.0, 120.0], geometry_units="meters", compute_condition_number=True, strict_quality_gate=False,
                                              execution_options=dict(factorization=backend, mesh_strategy="global", assembly_threads=1, blas_threads=1))
            record('2d/%s/%s' % (name, backend), r)
        except Exception as e: out['2d/%s/%s' % (name, backend)] = dict(error='%s: %s' % (type(e).__name__, str(e)[:200]))
bor = {'pec_sphere': (scene([("b", 2, "2 1 0 0 0", bor_sphere(0.1, 160))]), 6.0), 'dielectric_sphere': (scene([("b", 3, "3 1 0 1 0", bor_sphere(0.1, 120))], diel="1 3.0 -0.08 1.0 0.0"), 3.0)}
params = inspect.signature(D.solve_monostatic_rcs_bor).parameters
for name, (g, f) in bor.items():
    for backend in ('hierarchical', 'compressed', 'dense'):
        try:
            kw = dict(geometry_units="meters", workers=1, bor_options=dict(factorization=backend))
            if 'compute_condition_number' in params: kw['compute_condition_number'] = True
            if 'strict_quality_gate' in params: kw['strict_quality_gate'] = False
            with warnings.catch_warnings():
                warnings.simplefilter("ignore"); r = D.solve_monostatic_rcs_bor(g, [f], [0.0, 30.0, 90.0, 180.0], **kw)
            record('bor/%s/%s' % (name, backend), r)
        except Exception as e: out['bor/%s/%s' % (name, backend)] = dict(error='%s: %s' % (type(e).__name__, str(e)[:200]))
json.dump(out, open(sys.argv[1], 'w'), indent=1)
