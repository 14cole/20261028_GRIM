"""Planner versus execution unknown counts on connected impedance sheets.

One Automatic specified-mesh solve per fixture. Every call that sizes a system is logged
with whether it came from the backend forecast or from execution.

  GRIM_ROOT=<95f8719> python sheet_unknowns.py results/sheet_unknowns.json
"""
import json, sys
import numpy as np
from common import solver, selection, solve

log, where = [], ["execution"]
resources = solver._dense_formulation_resources
def tracked(mesh, infos, pol, *a, **k):
    out = resources(mesh, infos, pol, *a, **k)
    log.append((where[0], pol, int(out["system_dofs"]), int(len(mesh.elements))))
    return out
solver._dense_formulation_resources = tracked
forecast = selection._forecast_backend
def tracked_forecast(*a, **k):
    where[0] = "planner"
    try:
        return forecast(*a, **k)
    finally:
        where[0] = "execution"
selection._forecast_backend = tracked_forecast


def chain(points, flags, kind=1):
    """Consecutive points joined by one named segment each; flags cycles the sheet flag."""
    lines = ["Title: connected sheets"]
    for i, (p, q) in enumerate(zip(points[:-1], points[1:])):
        lines += [f"Segment: piece_{i} {kind}", f"properties: {kind} 0 {flags[i % len(flags)]} 0 0",
                  " ".join(f"{v:.17g}" for v in (*p, *q))]
    return lines


def geo(lines, pec=False):
    tail = ["IBCS_Resistances:"] + ([] if pec else ["10 constant 75 -20 0 0", "11 constant 150 10 0 0"]) + ["", "Dielectrics:"]
    return "\n".join(lines + tail) + "\n"


t = np.linspace(0.15 * np.pi, 0.85 * np.pi, 10)
arc = np.column_stack((0.2 * np.cos(t), 0.2 * np.sin(t)))                    # nine pieces on an open arc
zig = np.array([(0.03 * i, 0.02 * (i % 2)) for i in range(8)])               # seven pieces, a corner at every joint
ring_t = -2 * np.pi * np.arange(7) / 6
ring = np.column_stack((0.1 * np.cos(ring_t), 0.1 * np.sin(ring_t)))         # six pieces closing on themselves
FIXTURES = {
    "single_sheet": geo(chain(np.array([(-0.1, 0.0), (0.1, 0.0)]), [10])),
    "arc_9_pieces_one_flag": geo(chain(arc, [10])),
    "arc_9_pieces_two_flags": geo(chain(arc, [10, 11])),
    "arc_9_pieces_alternately_reversed": geo(sum((chain(np.array([q, p]) if i % 2 else np.array([p, q]), [10])[1:]
                                                  for i, (p, q) in enumerate(zip(arc[:-1], arc[1:]))), ["Title: reversed"])
                                             ).replace("piece_0", "piece"),
    "zigzag_7_pieces": geo(chain(zig, [10, 11])),
    "closed_ring_6_pieces": geo(chain(ring, [10])),
    "pec_ring_6_pieces_control": geo(chain(ring, [0], kind=2), pec=True),
}
# The reversed fixture reuses one name per piece; make them distinct.
lines, n = [], 0
for line in FIXTURES["arc_9_pieces_alternately_reversed"].splitlines():
    if line.startswith("Segment:"):
        line = f"Segment: rev_{n} 1"; n += 1
    lines.append(line)
FIXTURES["arc_9_pieces_alternately_reversed"] = "\n".join(lines) + "\n"

rows = []
for name, text in FIXTURES.items():
    for degree in (1, 2, 3):
        log.clear()
        row = dict(fixture=name, degree=degree)
        try:
            result, _ = solve(text, 5.0, np.arange(0.0, 180.0, 15.0), threads=1, mesh_strategy="global", basis_order=degree)
            row["outcome"] = "solved"
        except Exception as exc:
            row["outcome"] = type(exc).__name__ + ": " + str(exc)[:160]
        for source in ("planner", "execution"):
            for pol in ("TE", "TM"):
                found = sorted({(d, e) for w, p, d, e in log if w == source and p == pol})
                row[f"{source}_{pol}"] = found[-1][0] if found else None
                row[f"{source}_{pol}_elements"] = found[-1][1] if found else None
        row["planner_called"] = any(w == "planner" for w, *_ in log)
        rows.append(row)
        print(name, degree, row["outcome"][:40], "planner TE/TM", row["planner_TE"], row["planner_TM"],
              "execution TE/TM", row["execution_TE"], row["execution_TM"],
              "MISMATCH" if row["planner_TE"] != row["execution_TE"] or row["planner_TM"] != row["execution_TM"] else "")
json.dump(rows, open(sys.argv[1], "w"), indent=1)
