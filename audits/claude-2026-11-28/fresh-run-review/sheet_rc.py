"""Sheet planning on a new bent, split, partly reversed impedance sheet, plus an ordinary control.

  GRIM_ROOT=<tree> python sheet_rc.py <label> results/rc

Records, per basis degree: desktop forecast unknowns, HPC forecast unknowns in both channel
orders, the sizes of the matrices actually factorized, and the complete complex fields.
"""
import json, sys
from pathlib import Path
import numpy as np
import scipy.linalg
from common import solver, selection, solve, snapshot, fields_of
import ghost_backend.hpc.scheduler as hpc
from ghost_backend.twod.preparation import prepare_geometry
from ghost_backend.execution.options import execution_scope, validate_options

label, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
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
for name in ("lu_factor", "lu"):
    real = getattr(scipy.linalg, name)
    def wrapped(a, *args, _real=real, **kw):
        factored.append(int(np.shape(a)[0])); return _real(a, *args, **kw)
    setattr(scipy.linalg, name, wrapped)
import scipy.linalg.lapack as lapack
real_getrf = lapack.get_lapack_funcs
def tracked_funcs(names, arrays=(), *a, **k):
    funcs = real_getrf(names, arrays, *a, **k)
    single = isinstance(names, str)
    listed = [names] if single else list(names)
    wrapped = []
    for n, f in zip(listed, [funcs] if single else funcs):
        if n == "getrf":
            def g(m, *aa, _f=f, **kk):
                factored.append(int(np.shape(m)[0])); return _f(m, *aa, **kk)
            wrapped.append(g)
        else:
            wrapped.append(f)
    return wrapped[0] if single else wrapped
lapack.get_lapack_funcs = tracked_funcs
scipy.linalg.get_lapack_funcs = tracked_funcs

# Hook-shaped sheet: 5 pieces along one leg, a 70 degree bend, 6 along the other; odd pieces reversed.
leg1 = np.column_stack((np.linspace(-0.12, 0.0, 6), np.zeros(6)))
ang = np.deg2rad(70.0)
leg2 = np.array([(0.02 * i * np.cos(ang), 0.02 * i * np.sin(ang)) for i in range(1, 7)])
pts = np.vstack((leg1, leg2))
lines = ["Title: hook"]
for i, (p, q) in enumerate(zip(pts[:-1], pts[1:])):
    a, b = (q, p) if i % 2 else (p, q)
    lines += [f"Segment: hook_{i} 1", f"properties: 1 0 {10 + i % 2} 0 0", " ".join(f"{v:.17g}" for v in (*a, *b))]
HOOK = "\n".join(lines + ["IBCS_Resistances:", "10 constant 75 -20 0 0", "11 constant 150 10 0 0", "", "Dielectrics:"]) + "\n"

def ring(r, n):
    t = -2 * np.pi * np.arange(n + 1) / n
    p = np.column_stack((r * np.cos(t), r * np.sin(t)))
    return [" ".join(f"{v:.17g}" for v in (*a, *b)) for a, b in zip(p[:-1], p[1:])]
COATED = "\n".join(["Title: coated", "Segment: outer 3", "properties: 3 0 0 1 0"] + ring(0.06, 48) +
                   ["Segment: inner 4", "properties: 4 0 0 1 0"] + ring(0.045, 40) +
                   ["IBCS_Resistances:", "", "Dielectrics:", "1 2.8 -0.06 1 0"]) + "\n"
ANGLES = np.arange(0.0, 360.0, 5.0)
rows = []
for fixture, text in (("hook_sheet", HOOK), ("coated_cylinder_control", COATED)):
    snap = snapshot(text)
    _, _, materials, scale = prepare_geometry(snap, None, "meters")
    for degree in (1, 2, 3):
        log.clear(); factored.clear()
        result, _ = solve(text, 4.0, ANGLES, threads=1, mesh_strategy="global", basis_order=degree)
        f = fields_of(result)
        np.savez_compressed(out / f"{label}_{fixture}_p{degree}.npz", angles_deg=ANGLES, TE=f["TE"], TM=f["TM"])
        row = dict(tree=label, fixture=fixture, degree=degree, factored_sizes=sorted(set(factored)),
                   backend=result["metadata"].get("linear_backend"))
        for source in ("planner", "execution"):
            for pol in ("TE", "TM"):
                found = {d for w, p, d in log if w == source and p == pol}
                row[f"{source}_{pol}"] = max(found) if found else None
        options = dict(validate_options(dict(basis_order=degree, mesh_strategy="global")), factorization="dense")
        for order in ((("VV", "TE"), ("HH", "TM")), (("HH", "TM"), ("VV", "TE"))):
            with execution_scope(options):
                rec = hpc._resource_records_for_frequency(solver, snap, materials, 4.0, order, scale, solver.MAX_PANELS_DEFAULT)
            row["hpc_" + "_then_".join(c for _, c in order)] = {c: int(rec[r]["system_dofs"]) for r, c in order}
        for single in (("VV", "TE"), ("HH", "TM")):
            with execution_scope(options):
                rec = hpc._resource_records_for_frequency(solver, snap, materials, 4.0, (single,), scale, solver.MAX_PANELS_DEFAULT)
            row["hpc_" + single[1] + "_alone"] = int(rec[single[0]]["system_dofs"])
        rows.append(row); print(json.dumps(row))
json.dump(rows, open(out / f"sheet_rc_{label}.json", "w"), indent=1)
