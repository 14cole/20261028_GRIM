"""C-1: TE must refuse a free TYPE 2 end in every scene, and keep closed topologies."""
from common import *
from ghost_backend.twod import solver as S

ANG = [0.0, 45.0, 90.0, 135.0, 270.0]
DIEL = "1 3.0 -0.1 1.0 0.0"
body = ("d", 3, "3 -20 0 1 0", rect(-0.05, -0.03, 0.05, 0.03))
strip = ("s", 2, "2 -20 0 0 0", rows([(-0.05, 0.08), (0.05, 0.08)]))
plate = ("s", 2, "2 -20 0 0 0", rect(-0.05, 0.0799, 0.05, 0.0801))
sheet = ("sh", 1, "1 -20 10 0 0", rows([(-0.05, -0.08), (0.05, -0.08)]))
SHEET_IBC = "10 constant 150 60 0 0"


def co(g, **kw):
    return S.solve_monostatic_rcs_2d(g, [1.5], ANG, geometry_units="meters", solver_method="direct", **kw)


def single(g, pol):
    return S.solve_monostatic_rcs_2d_single_polarization(g, [1.5], ANG, pol, geometry_units="meters",
                                                         solver_method="direct")


MSG = "Open TYPE 2"
# --- scenes that used to be solved wrongly: now refused for TE -------------
check("dielectric + open strip refused (co-pol)", *raises(lambda: co(scene([body, strip], diel=DIEL)), ValueError, MSG))
check("dielectric + open strip refused (TE single)", *raises(lambda: single(scene([body, strip], diel=DIEL), "TE"), ValueError, MSG))
check("sheet + open strip refused (TE)", *raises(lambda: single(scene([sheet, strip], ibc=SHEET_IBC), "TE"), ValueError, MSG))
coat_outer = ("o", 3, "3 -20 0 1 0", circle(0.05, 96, y0=-0.02))
coat_core = ("c", 4, "4 -20 0 1 0", circle(0.035, 72, y0=-0.02))
check("coated body + open strip refused (TE)", *raises(lambda: single(scene([coat_outer, coat_core, ("s", 2, "2 -20 0 0 0", rows([(-0.05, 0.08), (0.05, 0.08)]))], diel=DIEL), "TE"), ValueError, MSG))
check("certified entry refuses dielectric + open strip", *raises(lambda: S.solve_monostatic_rcs_2d_certified(scene([body, strip], diel=DIEL), [1.5], ANG, geometry_units="meters"), ValueError, MSG))
check("bistatic entry refuses dielectric + open strip", *raises(lambda: S.solve_bistatic_rcs_2d(scene([body, strip], diel=DIEL), [1.5], [0.0, 90.0], [0.0, 90.0], geometry_units="meters"), ValueError, MSG))
touch = ("s", 2, "2 -20 0 0 0", rows([(0.0, 0.03), (0.0, 0.09)]))  # one end on the dielectric face
check("strip ending on a dielectric face refused (preflight intersection)", *raises(lambda: single(scene([body, touch], diel=DIEL), "TE"), ValueError))
vertex = ("s", 2, "2 -20 0 0 0", rows([(0.05, 0.03), (0.05, 0.09)]))  # one end on a dielectric vertex, one free
check("strip from a dielectric vertex with a free end refused (TE)", *raises(lambda: single(scene([body, vertex], diel=DIEL), "TE"), ValueError))
check("lone open strip still refused (TE)", *raises(lambda: single(scene([strip]), "TE"), ValueError, MSG))

# --- TM keeps working on the same scenes ------------------------------------
r_open = single(scene([body, strip], diel=DIEL), "TM")
r_plate = single(scene([body, plate], diel=DIEL), "TM")
d = np.max(np.abs(db(r_open["samples"], None) - db(r_plate["samples"], None)))
check("TM dielectric + open strip agrees with thin plate", d < 0.15, "max |dB diff| {:.3f}".format(d))

# --- closed topologies must still solve for TE --------------------------------
ok = co(scene([body, plate], diel=DIEL))
check("dielectric + thin closed plate solves", len(ok["samples"]) == 2 * len(ANG))
check("closed PEC square solves", len(co(scene([("b", 2, "2 -20 0 0 0", rect(-0.05, -0.05, 0.05, 0.05))]))["samples"]) == 10)
# closed conductor stitched from two segments with different impedance flags
half_a = ("a", 2, "2 -20 0 0 0", arc(0.05, math.pi, 0.0, 24))
half_b = ("b", 2, "2 -20 10 0 0", arc(0.05, 0.0, -math.pi, 24))
check("PEC|IBC stitched closed contour solves", len(co(scene([half_a, half_b], ibc="10 constant 75 -20 0 0"))["samples"]) == 10)
# partial coating: bare TYPE 2 arc meets TYPE 3 caps and the TYPE 4 core arc at two junctions
bare = ("bare", 2, "2 0 0 0 0", arc(0.07, math.pi, 0.0, 40))
core = ("core", 4, "4 0 0 1 0", arc(0.07, 0.0, -math.pi, 40))
outline = ("coat", 3, "3 0 0 1 0", rows([(0.07, 0.0), (0.1, 0.0)]) + "\n" + arc(0.1, 0.0, -math.pi, 56) + "\n" + rows([(-0.1, 0.0), (-0.07, 0.0)]))
pc = co(scene([bare, core, outline], diel="1 3.0 0.0 1.0 0.0"))
check("partial coating (TYPE 2/3/4 junctions) solves", len(pc["samples"]) == 10 and np.all(np.isfinite(db(pc["samples"], "VV"))))
# sheet next to a separated closed conductor
sp = co(scene([sheet, ("b", 2, "2 -20 0 0 0", rect(-0.05, 0.0, 0.05, 0.05))], ibc=SHEET_IBC))
check("sheet + separated closed PEC solves", len(sp["samples"]) == 10)
check("dielectric alone solves", len(co(scene([body], diel=DIEL))["samples"]) == 10)
check("coated PEC solves", len(co(scene([coat_outer, coat_core], diel=DIEL))["samples"]) == 10)
finish()
