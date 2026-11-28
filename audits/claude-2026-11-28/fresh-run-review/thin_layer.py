"""Thin dielectric layer split into named sections: forecast versus factorized matrix size.

  GRIM_ROOT=<tree> python thin_layer.py <label> results/rc
"""
import json, sys
from pathlib import Path
import numpy as np
import scipy.linalg, scipy.linalg.lapack as lapack
from common import solver, selection, solve, fields_of

label, out = sys.argv[1], Path(sys.argv[2])
log, where, factored = [], ["execution"], []
resources = solver._dense_formulation_resources
def tracked(mesh, infos, pol, *a, **k):
    r = resources(mesh, infos, pol, *a, **k); log.append((where[0], pol, int(r["system_dofs"]))); return r
solver._dense_formulation_resources = tracked
forecast = selection._forecast_backend
def tracked_forecast(*a, **k):
    where[0] = "planner"
    try: return forecast(*a, **k)
    finally: where[0] = "execution"
selection._forecast_backend = tracked_forecast
solved = []
estimate = solver._estimate_memory_gb
def tracked_estimate(*a, **k):
    # The thin-layer solver prices the system it is about to assemble, on its joined midsurface.
    if (k.get("dense_resources") or {}).get("formulation") == "thin_dielectric_layer" and k.get("activate_memory_plan"):
        solved.append(int(k["system_dofs"]))
    return estimate(*a, **k)
solver._estimate_memory_gb = tracked_estimate
real_funcs = lapack.get_lapack_funcs
def tracked_funcs(names, arrays=(), *a, **k):
    funcs = real_funcs(names, arrays, *a, **k)
    single = isinstance(names, str)
    outp = []
    for n, f in zip([names] if single else list(names), [funcs] if single else funcs):
        if n in ("getrf", "gesv"):
            def g(m, *aa, _f=f, **kk):
                factored.append(int(np.shape(m)[0])); return _f(m, *aa, **kk)
            outp.append(g)
        else:
            outp.append(f)
    return outp[0] if single else outp
lapack.get_lapack_funcs = scipy.linalg.get_lapack_funcs = tracked_funcs
for name in ("lu_factor", "solve"):
    real = getattr(scipy.linalg, name)
    def w(a, *args, _r=real, **kw):
        factored.append(int(np.shape(a)[0])); return _r(a, *args, **kw)
    setattr(scipy.linalg, name, w)
realnp = np.linalg.solve
def npsolve(a, b):
    factored.append(int(np.shape(a)[0])); return realnp(a, b)
np.linalg.solve = npsolve


def layer(points, reverse=(), n=3):
    lines = ["Title: thin layer"]
    for i, (p, q) in enumerate(zip(points[:-1], points[1:])):
        a, b = (q, p) if i in reverse else (p, q)
        lines += [f"Segment: section_{i} 1", f"properties: 1 {n} 10 0 0", " ".join(f"{v:.17g}" for v in (*a, *b))]
    return "\n".join(lines + ["IBCS_Resistances:", "10 thin_dielectric 0.0005 50", "", "Dielectrics:", "50 3.2 -0.02 1 0"]) + "\n"


straight = np.column_stack((np.linspace(-0.06, 0.06, 5), np.zeros(5)))            # four sections, 3 panels each
bent = np.array([(-0.06, 0.0), (-0.02, 0.0), (0.02, 0.01), (0.06, 0.03)])       # three sections with gentle bends
FIXTURES = {"one_section": layer(np.array([(-0.06, 0.0), (0.06, 0.0)]), n=12), "four_sections": layer(straight),
            "four_sections_two_reversed": layer(straight, reverse=(1, 3)), "three_bent_sections": layer(bent, n=4)}
ANGLES = np.arange(0.0, 360.0, 10.0)
rows = []
for name, text in FIXTURES.items():
    log.clear(); factored.clear(); solved.clear()
    row = dict(tree=label, fixture=name)
    try:
        result, _ = solve(text, 3.0, ANGLES, threads=1, mesh_strategy="global", basis_order=1)
        f = fields_of(result); row["outcome"] = "solved"
        np.savez_compressed(out / f"{label}_thin_{name}.npz", angles_deg=ANGLES, TE=f["TE"], TM=f["TM"])
    except Exception as exc:
        row["outcome"] = type(exc).__name__ + ": " + str(exc)[:200]
    for source in ("planner", "execution"):
        for pol in ("TE", "TM"):
            found = {d for w, p, d in log if w == source and p == pol}
            row[f"{source}_{pol}"] = max(found) if found else None
    row["midsurface_system_sizes"] = sorted(set(solved)); row["lapack_sizes_seen"] = sorted(set(factored))
    rows.append(row); print(json.dumps(row))
json.dump(rows, open(out / f"thin_layer_{label}.json", "w"), indent=1)
