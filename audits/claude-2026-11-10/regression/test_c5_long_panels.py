"""C-5: under-resolved negative N is refused; long panels on unenforced meshes are flagged."""
from common import *
from ghost_backend.twod import solver as S

F = 0.299792458  # wavelength 1 m


def square(n, side=10):
    return scene([("s", 2, "2 {} 0 0 0".format(n), rect(0, 0, side, side))])


def solve(n, **kw):
    return S.solve_monostatic_rcs_2d(square(n), [F], [0.0, 30.0], geometry_units="meters", solver_method="direct", **kw)


for n in (-1, -2, -3):
    check("N={} refused with the density floor on".format(n), *raises(lambda n=n: solve(n), ValueError, "safety floor"))
r = solve(-4)
check("N=-4 accepted", len(r["samples"]) == 4)
check("N=-4 raises no long-panel warning", not any("Electrically long" in w for w in r["metadata"]["warnings"]), r["metadata"]["warnings"])
check("positive N below the floor still refused", *raises(lambda: solve(5), ValueError, "safety floor"))
r = solve(0)
check("automatic N=0 raises no long-panel warning", not any("Electrically long" in w for w in r["metadata"]["warnings"]))

# With enforcement off (exploratory runs) the mesh is accepted and flagged.
r = solve(-1, execution_options=dict(enforce_mesh_density=False, factorization="dense"))
flagged = [w for w in r["metadata"]["warnings"] if "Electrically long" in w]
check("unenforced N=-1 is solved and warned about", len(flagged) == 1, flagged[:1])
check("warning reaches both channels", all(any("Electrically long" in w for w in r["metadata"]["channel_metadata"][pol]["warnings"]) for pol in ("VV", "HH")))
r = solve(-2, execution_options=dict(enforce_mesh_density=False, factorization="dense"))
check("unenforced N=-2 (|k|L = pi) is warned about", any("Electrically long" in w for w in r["metadata"]["warnings"]))
r = solve(-3, execution_options=dict(enforce_mesh_density=False, factorization="dense"))
check("unenforced N=-3 (|k|L = 2.1) is inside the calibrated range", not any("Electrically long" in w for w in r["metadata"]["warnings"]))
finish()
