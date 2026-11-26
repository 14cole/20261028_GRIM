"""Independent Line Expansion checks at ed90b65 (written before reading Codex's evidence).

Real certified section solver, real files, every output reopened from disk.
Metric everywhere: max|got - expected| / max|expected| over all samples.
Usage: python independent_checks.py [results.json]
"""
import json, sys, tempfile, traceback
from pathlib import Path
import numpy as np
from common import *
from common import _save_grim_npz
from ghost_backend.assembly.fields import load_body_requested_radar_grid
from ghost_backend.geometry.occlusion import Occluder
from ghost_backend.geometry.line_visibility import visible_intervals

R = {}
work = Path(tempfile.mkdtemp(prefix="le-"))
section = write_section(work)
AZ, EL, FREQ = [0.0, 40.0, 95.0, 200.0, 310.0], [-15.0, 25.0], [1.0, 1.6]

# ---- reference: sections only, zero attitude --------------------------------
ref_run = expand([section], output_grim=str(work/"ref.grim"), frequencies_ghz=FREQ,
                 azimuths_deg=AZ, elevations_deg=EL)
ref_payload, ref = reopen(ref_run["output"])
R["reference"] = dict(shape=list(ref.shape), max_abs_by_channel=np.abs(ref).max(axis=(0, 1, 2)).tolist(),
                      labels=[str(x) for x in ref_payload["polarizations"]], warnings=ref_run["warnings"],
                      seconds=ref_run["seconds"])

def base_from(payload, field, **changes):
    """A base file holding `field`, written by the production saver."""
    out = {k: v for k, v in payload.items() if k not in ("rcs_power", "rcs_phase", "rcs_amp_real", "rcs_amp_imag")}
    out.update(changes)
    out["rcs_amp_real"], out["rcs_amp_imag"] = field.real.copy(), field.imag.copy()
    out["rcs_power"] = (4*np.pi*np.abs(field)**2).astype(np.float32)
    out["rcs_phase"] = np.angle(field).astype(np.float32)
    return out

# ---- 1. metadata that survives reopening ------------------------------------
att = dict(axis_az_deg=25.0, axis_el_deg=-12.0, roll_deg=40.0)
a_run = expand([section], output_grim=str(work/"att.grim"), frequencies_ghz=FREQ,
               azimuths_deg=AZ, elevations_deg=EL, **att)
a_payload, a_field = reopen(a_run["output"])
try:
    grid = load_body_requested_radar_grid(a_run["output"])
    grid = None if grid is None else {k: float(grid[k]) for k in att}
except Exception as exc:
    grid = f"raised {type(exc).__name__}: {exc}"
R["metadata_after_reopen"] = dict(
    keys=sorted(a_payload),
    has_line_expansion_provenance="line_expansion_provenance_json" in a_payload,
    history=scalar(a_payload, "history"),
    attitude_readable_by_base_loader=grid,
    attitude_in_line_expansion_record=(json.loads(scalar(a_payload, "line_expansion_provenance_json") or "{}")
                                       .get("body_attitude_deg")),
    attitude_keys=[k for k in a_payload if any(s in k for s in ("axis", "roll", "attitude", "requested"))],
    attitude_changes_field=rel(a_field, ref),
)

# ---- 2. chained non-zero attitude: same section added twice => exactly 2x ---
def chain(name, **kw):
    run = expand([section], output_grim=str(work/f"{name}.grim"), body_grim=a_run["output"], **kw)
    _, got = reopen(run["output"])
    return dict(error=rel(got, 2*a_field), warnings=run["warnings"])
R["chained_attitude"] = dict(requested=att, implicit=chain("chain-implicit"),
                             explicit=chain("chain-explicit", **att))
# Third link: does an implicit chain of an explicit chain still lose it?
run3 = expand([section], output_grim=str(work/"chain3.grim"), body_grim=str(work/"chain-explicit.grim"))
R["chained_attitude"]["third_link_implicit_error_vs_3x"] = rel(reopen(run3["output"])[1], 3*a_field)

# ---- 3. degree base vs physically identical radian base ---------------------
units = json.loads(scalar(ref_payload, "units"))
deg_base = base_from(ref_payload, ref)
rad_units = dict(units, azimuth="rad", elevation="rad")
rad_base = base_from(ref_payload, ref, azimuths=np.radians(AZ), elevations=np.radians(EL),
                     units=np.asarray(json.dumps(rad_units)))
rad_base.pop("assembly_angular_coordinate_contract", None)   # an honest imported file
rad_base_tagged = base_from(ref_payload, ref, azimuths=np.radians(AZ), elevations=np.radians(EL),
                            units=np.asarray(json.dumps(rad_units)))
R["degree_vs_radian_base"] = {}
for name, payload in (("degrees", deg_base), ("radians_units_declared", rad_base),
                      ("radians_with_degree_contract_tag", rad_base_tagged)):
    try:
        _save_grim_npz(payload, str(work/f"base-{name}.grim"))
        saved_payload, _ = reopen(work/f"base-{name}.grim")
        run = expand([section], output_grim=str(work/f"out-{name}.grim"), body_grim=str(work/f"base-{name}.grim"))
        out_payload, got = reopen(run["output"])
        R["degree_vs_radian_base"][name] = dict(
            accepted=True, base_units=scalar(saved_payload, "units"),
            output_units=scalar(out_payload, "units"),
            output_azimuths=np.asarray(out_payload["azimuths"]).tolist(),
            error_vs_2x_reference=rel(got, 2*ref),
            error_of_added_part_vs_reference=rel(got - ref, ref),
            warnings=run["warnings"])
    except Exception as exc:
        R["degree_vs_radian_base"][name] = dict(accepted=False, error=f"{type(exc).__name__}: {exc}")

# ---- 4. four-channel base (VV, HH, VH, HV), reciprocal on input -------------
lab = [str(x) for x in ref_payload["polarizations"]]
iv, ih, ix = lab.index("VV"), lab.index("HH"), lab.index("VH")
R["four_channel_base"] = {}
for order in (["VV", "HH", "VH", "HV"], ["HH", "HV", "VH", "VV"], ["VV", "HV", "HH", "VH"]):
    src = {"VV": ref[..., iv], "HH": ref[..., ih], "VH": ref[..., ix], "HV": ref[..., ix]}
    field = np.stack([src[c] for c in order], axis=-1)
    payload = base_from(ref_payload, field, polarizations=np.array(order),
                        polarization_aliases_json=np.asarray(json.dumps(order)),
                        polarization_alias_primary=np.asarray(order[0]))
    name = "".join(order)
    try:
        _save_grim_npz(payload, str(work/f"b4-{name}.grim"))
        run = expand([section], output_grim=str(work/f"o4-{name}.grim"), body_grim=str(work/f"b4-{name}.grim"))
        out_payload, got = reopen(run["output"])
        out_lab = [str(x) for x in out_payload["polarizations"]]
        g = {c: got[..., out_lab.index(c)] for c in out_lab}
        R["four_channel_base"][name] = dict(
            output_labels=out_lab,
            error_by_channel={c: rel(g[c], 2*src[c]) for c in out_lab},
            max_abs_VH=float(np.abs(g["VH"]).max()), max_abs_HV=float(np.abs(g["HV"]).max()),
            reciprocity_residual=float(np.abs(g["VH"]-g["HV"]).max()/np.abs(2*src["VH"]).max()),
            HV_unchanged_from_base=bool(np.array_equal(g["HV"], src["HV"])),
            warnings=run["warnings"])
    except Exception as exc:
        R["four_channel_base"][name] = dict(error=f"{type(exc).__name__}: {exc}")

# ---- 5. analytically occluding sheet, several tessellations -----------------
# Square sheet [-1,1]^2 in z=0. Lines at z=-0.5 run along x at fixed y.
# A point (x, y, -0.5) looking along d=(sin t, 0, cos t) is blocked exactly when
# x + 0.5*tan(t) is in [-1, 1] and |y| <= 1.
def sheet(n):
    g = np.linspace(-1.0, 1.0, n+1)
    tris = []
    for i in range(n):
        for j in range(n):
            p00, p10 = (g[i], g[j], 0.0), (g[i+1], g[j], 0.0)
            p01, p11 = (g[i], g[j+1], 0.0), (g[i+1], g[j+1], 0.0)
            tris += [(p00, p10, p11), (p00, p11, p01)]
    return np.asarray(tris, float)

lines = [(-3.0, 3.0, 0.2), (-0.4, 2.6, -0.7), (-2.5, 0.3, 0.0), (-0.9, 0.9, 0.5), (1.2, 2.0, 0.1), (-3.0, 3.0, 1.5)]
starts = np.array([(a, y, -0.5) for a, b, y in lines]); ends = np.array([(b, y, -0.5) for a, b, y in lines])
def exact(tilt):
    shift = 0.5*np.tan(tilt)
    out = []
    for a, b, y in lines:
        lo, hi = max(a, -1-shift), min(b, 1-shift)
        blocked = max(0.0, hi-lo) if abs(y) <= 1 else 0.0
        out.append(1.0 - blocked/(b-a))
    return np.array(out)
R["sheet_shadow"] = {}
for n in (1, 8, 11, 12, 18, 40):
    occ = Occluder(sheet(n)); row = dict(triangles=2*n*n, leaf_limit=Occluder._LEAF_TRIANGLES, looks={})
    for deg in (0.0, 20.0, -35.0):
        t = np.radians(deg); d = np.array([np.sin(t), 0.0, np.cos(t)])
        try:
            owner, lo, hi = visible_intervals(occ, starts, ends, d)
            frac = np.bincount(owner, weights=hi-lo, minlength=len(lines))
            row["looks"][f"{deg:g}"] = dict(max_abs_fraction_error=float(np.abs(frac-exact(t)).max()),
                                             visible_fraction=np.round(frac, 9).tolist(),
                                             exact=np.round(exact(t), 9).tolist())
        except Exception as exc:
            row["looks"][f"{deg:g}"] = dict(raised=f"{type(exc).__name__}: {exc}",
                                             where=traceback.extract_tb(exc.__traceback__)[-1].name)
    R["sheet_shadow"][f"{n}x{n}"] = row

# ---- 6. the same crash through the public entry point -----------------------
# Base carrying an embedded BoR profile (a 0.15 m sphere); section placed beside it.
theta = np.linspace(0, np.pi, 25)
sphere = base_from(ref_payload, ref, body_profile_rho_m=0.15*np.sin(theta).clip(0), body_profile_z_m=-0.15*np.cos(theta),
                   body_profile_kind=np.asarray("outer_boundary"))
_save_grim_npz(sphere, str(work/"sphere-base.grim"))
for shadow in (True, False):
    try:
        run = expand([section], output_grim=str(work/f"shadow-{shadow}.grim"), body_grim=str(work/"sphere-base.grim"), shadow=shadow)
        _, got = reopen(run["output"])
        R[f"expansion_with_bor_base_shadow_{shadow}"] = dict(completed=True, added_vs_reference=rel(got-ref, ref), warnings=run["warnings"])
    except Exception as exc:
        R[f"expansion_with_bor_base_shadow_{shadow}"] = dict(completed=False, raised=f"{type(exc).__name__}: {exc}",
                                                             output_exists=(work/f"shadow-{shadow}.grim").exists())

text = json.dumps(R, indent=1, default=float)
Path(sys.argv[1] if len(sys.argv) > 1 else "independent_results.json").write_text(text + "\n")
print(text)
