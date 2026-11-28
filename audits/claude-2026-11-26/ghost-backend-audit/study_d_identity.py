"""Does the second polarization get memory credit for a matrix it does not reuse?

Real geometry, assembly, session lookup, factorization and gates. Only the reading of
available RAM is controlled, per polarization, to move the automatic assembly tile.

  GRIM_ROOT=<tree> python study_d_identity.py <tree-label> <out.json>
"""
import json, sys
import numpy as np
import harness
from harness import cylinder_geo, solve_fixed, fields_of
import ghost_backend.twod.solver as solver
import ghost_backend.twod.assembly.session as session
import ghost_backend.execution.dense_memory as dense_memory

REAL = solver._detect_available_gb
state = dict(pol=None, te=None, tm=None, log=[])


def available():
    wanted = {"TE": state["te"], "TM": state["tm"]}.get(state["pol"])
    return REAL() if wanted is None else wanted


resources = solver._dense_formulation_resources
def tracked_resources(mesh, infos, pol, *a, **k):
    state["pol"] = pol
    return resources(mesh, infos, pol, *a, **k)


take = session.AssemblySession.take
def tracked_take(self, key, polarization):
    pending = self.pending
    out = take(self, key, polarization)
    if polarization == "TM":
        state["log"].append(dict(event="lookup", retained_tile=None if pending is None else pending[0][-1],
                                 requested_tile=key[-1], hit=out is not None))
    return out


limit = solver._solve_memory_limit_gb
def tracked_limit(resident_gb=0.0):
    out = limit(resident_gb)
    if state["pol"] == "TM":
        state["log"].append(dict(event="limit", credit_bytes=int(round(resident_gb * 2**30)), limit_gib=out))
    return out


forecast = dense_memory.forecast
def tracked_forecast(*a, **k):
    plan = forecast(*a, **k)
    if k.get("execution"):
        state["log"].append(dict(event="plan", pol=state["pol"], tile=plan["assembly_tile"],
                                 batch=plan["angle_batch_size"], storage=plan["residual_storage"],
                                 peak_gib=plan["peak_bytes"] / 2**30, capacity_gib=plan["capacity_bytes"] / 2**30,
                                 credit_bytes=plan.get("reused_matrix_credit_bytes")))
    return plan


solver._detect_available_gb = available
solver._dense_formulation_resources = tracked_resources
session.AssemblySession.take = tracked_take
solver._solve_memory_limit_gb = tracked_limit
dense_memory.forecast = tracked_forecast

TEXT = cylinder_geo(0.12, 1056, a=0.10, eps=2.8 - 0.06j, center=(0.03, -0.02))
ANGLES = np.arange(-90.0, 90.0)


def run(te, tm, tile=None):
    state.update(pol=None, te=te, tm=tm, log=[])
    more = {} if tile is None else dict(assembly_tile=tile)
    row = dict(te_available_gib=te, tm_available_gib=tm, explicit_tile=tile)
    try:
        result, _ = solve_fixed(TEXT, 10.0, ANGLES, "dense", dense_residual_storage="disk", **more)
        f = fields_of(result)
        row.update(outcome="solved", te=[f["TE"].real.tolist(), f["TE"].imag.tolist()],
                   tm=[f["TM"].real.tolist(), f["TM"].imag.tolist()])
    except MemoryError as exc:
        row.update(outcome="refused", message=str(exc)[:200])
    log = state["log"]
    lookups = [e for e in log if e["event"] == "lookup"]
    end = log.index(lookups[0]) if lookups else len(log)
    limits = [e for e in log[:end] if e["event"] == "limit"]
    # The gate is the last limit read before the lookup (or the last one if refused).
    row.update(lookup=lookups[-1] if lookups else None, final_gate=limits[-1] if limits else None,
               tm_plans=[e for e in log if e["event"] == "plan" and e["pol"] == "TM"],
               te_plans=[e for e in log if e["event"] == "plan" and e["pol"] == "TE"])
    credit = row["final_gate"]["credit_bytes"] if row["final_gate"] else 0
    row["credited_without_reuse"] = bool(credit and row["outcome"] == "solved" and not (row["lookup"] or {}).get("hit"))
    return row


if __name__ == "__main__":
    label, out = sys.argv[1:3]
    reserve = 0.1 * REAL()
    rows = []
    for x in np.arange(0.30, 0.741, 0.04):            # TE free, TM tight
        rows.append(dict(case="tighten", **run(None, reserve + float(x))))
    for x in np.arange(0.30, 0.741, 0.04):            # TE tight, TM free
        rows.append(dict(case="relax", **run(reserve + float(x), None)))
    for x in np.arange(0.30, 0.741, 0.04):            # tile pinned, TM tight
        rows.append(dict(case="pinned", **run(None, reserve + float(x), tile=128)))
    rows.append(dict(case="ambient", **run(None, None)))
    json.dump(dict(tree=label, reserve_gib=reserve, rows=rows), open(out, "w"))
    for r in rows:
        g, l = r["final_gate"] or {}, r["lookup"] or {}
        print(label, r["case"], r["tm_available_gib"] and round(r["tm_available_gib"] - reserve, 2),
              r["te_available_gib"] and round(r["te_available_gib"] - reserve, 2), r["outcome"],
              "tiles", l.get("retained_tile"), "->", l.get("requested_tile"), "hit", l.get("hit"),
              "credit", g.get("credit_bytes"), "limit %.3f" % g.get("limit_gib", float("nan")),
              "batch", [p["batch"] for p in r["tm_plans"]][-1:], "BAD" if r["credited_without_reuse"] else "")
