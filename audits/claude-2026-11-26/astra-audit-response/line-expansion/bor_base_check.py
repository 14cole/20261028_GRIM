"""End-to-end: a real BoR deliverable as the Line Expansion base, default shadowing on.

Solves a PEC sphere with the BoR solver, exports it with the production exporter
at a non-zero body attitude, adds a section twice (chained), and checks the
reopened files. Usage: python bor_base_check.py [out.json]
"""
import json, math, sys, tempfile
from pathlib import Path
import numpy as np
from common import *
from ghost_backend.assembly.fields import (
    load_body_requested_radar_grid, radar_frame_basis, radar_grid_aspects)
from ghost_backend.bor import dispatch
from ghost_backend.geometry.frames import to_axis_frame
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot
from ghost_backend.io.solver_export import export_solver_result

work = Path(tempfile.mkdtemp(prefix="le-bor-"))
R, FREQ = 0.15, [1.0]
AZ = [float(a) for a in range(0, 360, 30)]; EL = [0.0, 25.0]
ATT = dict(axis_az_deg=20.0, axis_el_deg=-10.0, roll_deg=15.0)

theta = np.linspace(0, math.pi, 49)
pts = [(R*math.sin(t), R*math.cos(t)) for t in theta]; pts[0], pts[-1] = (0.0, R), (0.0, -R)
text = "Title: sphere\nSegment: sphere 2\nproperties: 2 1 0 0 0\n" + "\n".join(
    "{:.15g} {:.15g} {:.15g} {:.15g}".format(*pts[i], *pts[i+1]) for i in range(len(pts)-1)
) + "\nIBCS_Resistances:\n\nDielectrics:\n\n"
snapshot = build_geometry_snapshot(*parse_geometry(text)) if isinstance(parse_geometry(text), tuple) else build_geometry_snapshot(parse_geometry(text))
aspects = sorted({float(a) for a in np.asarray(radar_grid_aspects(AZ, EL, ATT["axis_az_deg"], ATT["axis_el_deg"])).ravel()})
result = dispatch.solve_monostatic_rcs_bor(snapshot, FREQ, aspects, geometry_units="meters", workers=1)
base = export_solver_result(result, str(work/"body.grim"), context=dict(
    solver_kind="bor", snapshot=snapshot, units="meters",
    radar_grid=dict(azimuths_deg=AZ, elevations_deg=EL, frequencies_ghz=FREQ, **ATT)))[0]
body_payload, body = reopen(base)

section = dict(write_section(work), root=(0.25, -0.02, 0.0), tip=(0.25, 0.02, 0.0), normal=(0.0, 0.0, 1.0))
out = {"base_keys_of_interest": sorted(k for k in body_payload if "body_" in k or "requested" in k),
       "base_attitude": {k: float(load_body_requested_radar_grid(base)[k]) for k in ATT}}
alone = reopen(expand([section], output_grim=str(work/"alone.grim"), frequencies_ghz=FREQ,
                      azimuths_deg=AZ, elevations_deg=EL, **ATT)["output"])[1]
runs = {}
for name, source, kw in (("shadow_on", base, dict(shadow=True)), ("shadow_off", base, dict(shadow=False))):
    try:
        run = expand([section], output_grim=str(work/f"{name}.grim"), body_grim=source, **kw)
        payload, field = reopen(run["output"]); runs[name] = (run, payload, field)
    except Exception as exc:
        out[name] = dict(failed=f"{type(exc).__name__}: {exc}")
if "shadow_off" in runs:
    out["shadow_off"] = dict(error_vs_body_plus_section=rel(runs["shadow_off"][2], body + alone),
                             warnings=runs["shadow_off"][0]["warnings"])
if "shadow_on" in runs:
    run, payload, field = runs["shadow_on"]; added = field - body
    directions, _ = radar_frame_basis(AZ, EL, **ATT)
    p = to_axis_frame(np.array([(0.25, y, 0.0) for y in np.linspace(-0.02, 0.02, 9)]))
    along = p @ directions.T; miss2 = (p**2).sum(1)[:, None] - along**2
    hidden = np.all((along < 0) & (miss2 < (0.9*R)**2), axis=0).reshape(len(AZ), len(EL))
    clear = np.all((along > 0) | (miss2 > (1.1*R)**2), axis=0).reshape(len(AZ), len(EL))
    peak = np.abs(alone).max()
    out["shadow_on"] = dict(
        hidden_looks=int(hidden.sum()), clear_looks=int(clear.sum()),
        max_added_on_hidden_looks_rel=float(np.abs(added[hidden]).max()/peak),
        max_error_on_clear_looks_rel=float(np.abs(added[clear]-alone[clear]).max()/peak),
        unshadowed_section_on_hidden_looks_rel=float(np.abs(alone[hidden]).max()/peak),
        warnings=run["warnings"],
        output_attitude={k: float(load_body_requested_radar_grid(run["output"])[k]) for k in ATT},
        body_model_kept=all(k in payload for k in ("body_profile_rho_m", "body_model_aspects_deg", "body_model_amp_vv_real")),
        provenance=json.loads(scalar(payload, "line_expansion_provenance_json") or "null"))
    from ghost_backend.assembly.fields import load_body_grim, load_body_profile_grim, require_body_radar_support
    try:      # the output must still serve as an Assembly Body dataset
        load_body_grim(run["output"]); load_body_profile_grim(run["output"], require_feature_surface=True)
        require_body_radar_support(run["output"], FREQ, AZ, EL, ATT["axis_az_deg"], ATT["axis_el_deg"])
        out["output_usable_as_assembly_body"] = True
    except Exception as exc:
        out["output_usable_as_assembly_body"] = f"{type(exc).__name__}: {exc}"
    from ghost_backend.assembly.workflow import (
        FeatureAssemblyRequest, execute_feature_assembly, prepare_feature_assembly, prepare_feature_input_preview)
    try:      # real Assembly preview, preparation and execution on the expanded BoR file
        source = prepare_feature_input_preview(base_grim=run["output"]).body_source
        plan = prepare_feature_assembly(FeatureAssemblyRequest(base_grim=run["output"], output_grim=work/"assembly.grim"))
        done = execute_feature_assembly(plan, acknowledged_plan_sha256=plan.prepared_plan_sha256)
        out["assembly_on_output"] = dict(body_source=source, samples=int(field.size),
                                         max_field_difference=rel(reopen(done)[1], field))
    except Exception as exc:
        out["assembly_on_output"] = f"{type(exc).__name__}: {exc}"
    # The same real export with only its attitude request removed (as an axis edit leaves it).
    stripped = {k: v for k, v in body_payload.items() if k != "requested_radar_grid_json"}
    from common import _save_grim_npz
    no_request = _save_grim_npz(stripped, str(work/"body-no-request.grim"))
    for label, kw in (("implicit", {}), ("stated", ATT)):
        r = expand([section], output_grim=str(work/f"noreq-{label}.grim"), body_grim=no_request, shadow=False, **kw)
        out[f"request_removed_{label}"] = dict(error_vs_body_plus_section=rel(reopen(r["output"])[1], body + alone),
                                               warnings=r["warnings"])
    chained = expand([section], output_grim=str(work/"chained.grim"), body_grim=run["output"], shadow=True)
    out["chained_implicit"] = dict(error_vs_body_plus_2x_added=rel(reopen(chained["output"])[1], body + 2*added),
                                   warnings=chained["warnings"])
    try:
        expand([section], output_grim=str(work/"conflict.grim"), body_grim=run["output"], axis_az_deg=0.0)
        out["conflicting_attitude"] = "accepted"
    except ValueError as exc:
        out["conflicting_attitude"] = "refused: " + str(exc)[:140]
text = json.dumps(out, indent=1, default=float)
Path(sys.argv[1] if len(sys.argv) > 1 else "bor_base_results.json").write_text(text + "\n"); print(text)
