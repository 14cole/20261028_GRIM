"""GRIM-side checks on files Line Expansion writes: the Assembly panel and Axis Edit.

Drives the real offscreen GRIM Assembly panel and GRIM's own Axis Edit and save.
Needs GRIM_ROOT (the repository root is put on sys.path for GRIM_Backend).
Usage: python grim_app_check.py [out.json]
"""
import json, os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import numpy as np
from common import *
from common import _save_grim_npz
sys.path.insert(0, str(GRIM_ROOT))
from PySide6.QtWidgets import QApplication
from GRIM_Backend.assembly.model import preflight_base_grim
from GRIM_Backend.assembly.panel import FeatureAssemblyPanel
from GRIM_Backend.datasets.grid import RcsGrid
from ghost_backend.assembly import workflow
from ghost_backend.assembly.fields import recorded_line_expansion_attitude

work = Path(tempfile.mkdtemp(prefix="le-grim-"))
os.environ["GRIM_ASSEMBLY_DRAFT_DIR"] = str(work/"drafts")
app = QApplication.instance() or QApplication([])
section = write_section(work)
ATT = dict(axis_az_deg=-35.0, axis_el_deg=18.0, roll_deg=50.0)
GRID = dict(frequencies_ghz=[1.2], azimuths_deg=[0.0, 80.0, 150.0, 260.0], elevations_deg=[5.0, 30.0])
R = {}

# ---- Assembly panel on a fresh sections-only output ---------------------------------
base = expand([section], output_grim=str(work/"sections.grim"), **GRID, **ATT)["output"]
payload, field = reopen(base)
mesh = work/"patch.stl"
mesh.write_text("solid p\nfacet normal 0 0 1\nouter loop\nvertex -1 -1 .2\nvertex 1 -1 .2\nvertex 0 1 .2\nendloop\nendfacet\nendsolid p\n")
half = dict(payload, body_profile_rho_m=np.array([0.0, 0.01, 0.0]))            # rho without z: must stay rejected
_save_grim_npz(half, str(work/"half-profile.grim"))

def panel_state(path, stl):
    pre = preflight_base_grim(path)
    panel = FeatureAssemblyPanel(service=workflow)
    panel.set_base_grim(str(path))
    if stl:
        panel.set_surface_mesh(str(mesh)); panel.surface_units.setCurrentIndex(panel.surface_units.findData("meters"))
    panel.output_picker.set_path(str(work/"panel-out.grim"))
    panel._update_workflow_readiness(); app.processEvents()
    row = dict(classifier_valid=bool(pre.valid), embedded_bor=bool(pre.embedded_bor) if hasattr(pre, "embedded_bor") else None,
               summary=pre.summary, validate_enabled=panel.preview_button.isEnabled(),
               calculate_enabled=panel.build_button.isEnabled())
    panel.close(); panel.deleteLater(); app.processEvents()
    return row

R["file_keys"] = dict(has_request="requested_radar_grid_json" in payload, has_profile="body_profile_rho_m" in payload,
                      has_line_expansion_record="line_expansion_provenance_json" in payload)
R["panel_sections_only"] = panel_state(base, stl=False)
R["panel_sections_with_stl"] = panel_state(base, stl=True)
R["panel_incomplete_profile_pair"] = panel_state(work/"half-profile.grim", stl=True)

# ---- GRIM Axis Edit on a Line Expansion output ---------------------------------------
def attitude_record(p):
    record = json.loads(scalar(p, "line_expansion_provenance_json") or "{}")
    return record.get("body_attitude_deg"), record.get("body_attitude_source")

edited = work/"relabeled.grim"
RcsGrid.load(str(base)).edit_axis_value("azimuth", 0, 360.0).save(str(edited))          # 0 deg -> 360 deg
ep, ef = reopen(edited)
order = [list(GRID["azimuths_deg"]).index(a % 360.0) for a in np.asarray(ep["azimuths"], float)]
R["axis_edit_equivalent_relabel"] = dict(
    azimuths_after=np.asarray(ep["azimuths"]).tolist(), samples_unchanged=rel(ef, field[order]),
    attitude_record=attitude_record(ep)[0],
    record_still_trusted=recorded_line_expansion_attitude(ep) is not None)
for label, kw in (("blank", {}), ("restated", ATT), ("contradicting", dict(axis_az_deg=10.0, axis_el_deg=0.0, roll_deg=0.0))):
    try:
        run = expand([section], output_grim=str(work/f"relabel-{label}.grim"), body_grim=str(edited), **kw)
        R["axis_edit_equivalent_relabel"][label] = dict(error_vs_2x=rel(reopen(run["output"])[1], 2*field[order]),
                                                         warnings=run["warnings"])
    except ValueError as exc:
        R["axis_edit_equivalent_relabel"][label] = dict(refused=str(exc)[:150])

shifted = work/"shifted.grim"
RcsGrid.load(str(base)).edit_axis_value("azimuth", 1, 95.0).save(str(shifted))          # 80 deg -> 95 deg: a real change
sp, sf = reopen(shifted)
run = expand([section], output_grim=str(work/"shifted-out.grim"), body_grim=str(shifted))
R["axis_edit_real_change"] = dict(azimuths_after=np.asarray(sp["azimuths"]).tolist(), warnings=run["warnings"],
                                  attitude_sources=attitude_record(reopen(run["output"])[0])[1])

text = json.dumps(R, indent=1, default=float)
Path(sys.argv[1] if len(sys.argv) > 1 else "grim_app_results.json").write_text(text + "\n"); print(text)
