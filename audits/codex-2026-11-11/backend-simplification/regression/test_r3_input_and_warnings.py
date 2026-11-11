"""R-3b, R-3g, R-3l, M-1 telemetry: early input refusal, protection warning, env validation."""
import os
import subprocess
import sys
import time
from common import *
from ghost_backend.twod import solver as S

g = scene([("b", 2, "2 1 0 0 0", circle(0.1, 400))])
MSG = "more than once"
cases = {
    "monostatic": lambda: S.solve_monostatic_rcs_2d(g, [1.0], [10.0, 10.0], geometry_units="meters"),
    "survey": lambda: S.solve_monostatic_rcs_2d_survey(g, [1.0], [10.0, 10.0], geometry_units="meters"),
    "certified": lambda: S.solve_monostatic_rcs_2d_certified(g, [1.0], [10.0, 10.0], geometry_units="meters"),
    "bistatic observation": lambda: S.solve_bistatic_rcs_2d(g, [1.0], [0.0, 90.0], [5.0, 5.0], geometry_units="meters"),
    "bistatic incidence": lambda: S.solve_bistatic_rcs_2d_survey(g, [1.0], [0.0, 0.0], [5.0, 6.0], geometry_units="meters"),
    "multi-frequency": lambda: S.solve_monostatic_rcs_2d(g, [1.0, 1.1], [10.0, 10.0], geometry_units="meters"),
}
for name, fn in cases.items():
    start = time.perf_counter()
    ok, detail = raises(fn, ValueError, MSG)
    check("duplicate angle refused before solving ({})".format(name), ok and time.perf_counter() - start < 1.0, detail)
r = S.solve_monostatic_rcs_2d_single_polarization(g, [1.0], [10.0, 10.0], "TM", geometry_units="meters")
check("single-polarization diagnostic API still accepts duplicates", len(r["samples"]) == 2)
r = S.solve_monostatic_rcs_2d(g, [1.0], [0.0, 360.0], geometry_units="meters")
check("distinct values 0 and 360 still accepted", len(r["samples"]) == 4)

# R-3g: closed conductor next to an open strip (TM) is solved unprotected, and now says so.
ring = ("b", 2, "2 1 0 0 0", circle(0.1, 240))
strip = ("s", 2, "2 -20 0 0 0", rows([(-0.05, 0.2), (0.05, 0.2)]))
f = 2.4048255577 * 0.299792458 / (2 * np.pi * 0.1)
tm = lambda segs: S.solve_monostatic_rcs_2d_single_polarization(scene(segs), [f], [0.0, 90.0], "TM", geometry_units="meters",
                                                                solver_method="direct")["metadata"]["warnings"]
check("closed + open conductor warns about missing resonance protection", any("not protected" in w for w in tm([ring, strip])))
check("open strip alone has no such warning", not any("not protected" in w for w in tm([strip])))
r = S.solve_monostatic_rcs_2d(scene([ring]), [f], [0.0, 90.0], geometry_units="meters", solver_method="direct")
check("closed conductor alone has no warnings", r["metadata"]["warnings"] == [], r["metadata"]["warnings"])

# M-1 telemetry: the paired-assembly record reports solve estimate plus partner matrix.
r = S.solve_monostatic_rcs_2d(scene([("b", 2, "2 1 0 0 0", circle(0.1, 600))]), [1.0], [0.0], geometry_units="meters",
                              execution_options=dict(factorization="dense"))
records = [e for e in r["metadata"]["experimental_cpu"]["memory_estimates"] if e.get("method") == "paired_polarization_assembly"]
ok = bool(records) and all(abs(e["total_peak_gib"] - e["solve_estimate_gib"] - e["partner_matrix_bytes"] / 1024**3) < 1e-12
                           and e["total_peak_gib"] <= e["admission_limit_gib"] for e in records)
check("paired-assembly telemetry includes the partner matrix", ok, records[:1])

# R-3l: a malformed threshold is reported by name (fresh interpreter: the value is read at solve time).
code = ("import sys; sys.path.insert(0, {!r}); from common import *; from ghost_backend.twod import solver as S\n"
        "g = scene([('b', 2, '2 1 0 0 0', circle(0.1, 60))])\n"
        "try:\n    S.solve_monostatic_rcs_2d(g, [1.0], [0.0], geometry_units='meters', solver_method='direct')\n"
        "except ValueError as e:\n    print('VALUE', e)\n").format(os.path.dirname(os.path.abspath(__file__)))
for bad in ("abc", "-5"):
    out = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, GHOST_HIERARCHICAL_MIN_UNKNOWNS=bad),
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
    check("GHOST_HIERARCHICAL_MIN_UNKNOWNS={!r} refused by name".format(bad), "VALUE GHOST_HIERARCHICAL_MIN_UNKNOWNS" in out, out[-120:])
finish()
