"""Drive the real Line Expansion tab (offscreen) at ed90b65.

Covers what a GUI user sees for: default body shadowing on a BoR-profile base,
a radian base, the fields the tab offers for body attitude, Cancel during a
section solve, and an overflowing sweep. Usage: python gui_checks.py [out.json]
"""
import json, os, sys, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import numpy as np
from common import *
from common import _save_grim_npz
from PySide6.QtWidgets import QApplication, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox
from ghost_backend.ui.line_expansion import LineExpansionTab

app = QApplication.instance() or QApplication([])
work = Path(tempfile.mkdtemp(prefix="le-gui-"))
section = write_section(work)
R = {}

def make_tab(sec=section, **grid):
    tab = LineExpansionTab()
    tab.coordinate_units.setCurrentIndex(tab.coordinate_units.findData("meters"))
    tab.geometry_units.setCurrentIndex(tab.geometry_units.findData("meters"))
    tab._append_row([sec["geometry"], *map(str, sec["root"]), *map(str, sec["tip"]), *(repr(float(v)) for v in sec["normal"]), "", "", ""])
    tab.angle_step.setValue(2.0)
    for key, text in grid.items():
        tab.grid_fields[key].setText(text)
    return tab

def run(tab, cancel_after=None, timeout=600):
    seen = []
    tab.status_label_texts = seen
    start = time.time(); tab.run_button.click()
    started = tab.job_is_running(); cancel_at = None; idle_at = None
    while tab.job_is_running() and time.time()-start < timeout:
        app.processEvents(); time.sleep(0.005)
        if cancel_after is not None and cancel_at is None and time.time()-start >= cancel_after:
            tab.cancel_button.click(); cancel_at = time.time()-start
    idle_at = time.time()-start
    app.processEvents()
    return dict(started=started, status=tab.status_label.text(), seconds_to_idle=round(idle_at, 2),
                cancel_clicked_at=None if cancel_at is None else round(cancel_at, 2))

GRID = dict(frequencies_ghz="1, 1.6", azimuths_deg="0, 40, 95, 200, 310", elevations_deg="-15, 25")

# 1. plain sections-only run through the tab
tab = make_tab(**GRID); tab.output_edit.setText(str(work/"gui-ref.grim"))
R["sections_only"] = run(tab)
ref_payload, ref = reopen(work/"gui-ref.grim")

# 2. which inputs does the tab offer? (is there any way to state body attitude?)
names = sorted(k for k, v in vars(tab).items() if isinstance(v, (QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox)))
R["tab_inputs"] = dict(named_inputs=names, grid_fields=sorted(tab.grid_fields),
                       shadow_checked_by_default=tab.shadow.isChecked(),
                       any_attitude_input=any(s in n for n in names for s in ("axis", "roll", "attitude")))

def base(name, **changes):
    out = {k: v for k, v in ref_payload.items()}
    out.update(changes); _save_grim_npz(out, str(work/name)); return str(work/name)

# 3. default settings on a base that carries a BoR profile (0.15 m sphere)
theta = np.linspace(0, np.pi, 25)
sphere = base("sphere.grim", body_profile_rho_m=0.15*np.sin(theta).clip(0), body_profile_z_m=-0.15*np.cos(theta),
              body_profile_kind=np.asarray("outer_boundary"))
for label, checked in (("default_shadow_on", True), ("shadow_off", False)):
    tab = make_tab(); tab.body_edit.setText(sphere); tab.output_edit.setText(str(work/f"gui-{label}.grim"))
    tab.shadow.setChecked(checked)
    R[f"bor_profile_base_{label}"] = dict(run(tab), output_written=(work/f"gui-{label}.grim").exists())

# 4. radian base through the tab
units = json.loads(scalar(ref_payload, "units")); units.update(azimuth="rad", elevation="rad")
rad = base("rad.grim", azimuths=np.radians(ref_payload["azimuths"]), elevations=np.radians(ref_payload["elevations"]),
           units=np.asarray(json.dumps(units)))
tab = make_tab(); tab.body_edit.setText(rad); tab.output_edit.setText(str(work/"gui-rad.grim"))
R["radian_base"] = run(tab)
R["radian_base"]["output_written"] = (work/"gui-rad.grim").exists()
if R["radian_base"]["output_written"]:
    R["radian_base"]["error_vs_2x_reference"] = rel(reopen(work/"gui-rad.grim")[1], 2*ref)

# 5. Cancel during a long section solve (same wedge, 25x larger, 3 GHz)
big = work/"big.geo"
big.write_text("\n".join(
    " ".join(str(25*float(x)) for x in line.split()) if len(line.split()) == 4 and line[0] in "-0123456789" else line
    for line in SECTION_GEO.splitlines()) + "\n")
big_section = dict(section, geometry=str(big))
grid1 = dict(frequencies_ghz="3", azimuths_deg="0", elevations_deg="0")
tab = make_tab(big_section, **grid1); tab.angle_step.setValue(0.5); tab.output_edit.setText(str(work/"gui-big.grim"))
full = run(tab)
tab = make_tab(big_section, **grid1); tab.angle_step.setValue(0.5); tab.output_edit.setText(str(work/"gui-big-cancel.grim"))
canceled = run(tab, cancel_after=0.5)
R["cancel_during_section_solve"] = dict(uncanceled=full, canceled=canceled,
                                        output_written_after_cancel=(work/"gui-big-cancel.grim").exists())

# 6. overflowing sweep text: does the tab report it, or does the exception escape?
tab = make_tab(frequencies_ghz="1", azimuths_deg="0:1e308:1e-308", elevations_deg="0"); tab.output_edit.setText(str(work/"gui-ovf.grim"))
try:
    tab.expand_and_save(); R["overflow_sweep"] = dict(escaped=False, status=tab.status_label.text())
except Exception as exc:
    R["overflow_sweep"] = dict(escaped=True, exception=f"{type(exc).__name__}: {exc}", status=tab.status_label.text(),
                               job_started=tab.job_is_running())

text = json.dumps(R, indent=1, default=float)
Path(sys.argv[1] if len(sys.argv) > 1 else "gui_results.json").write_text(text + "\n"); print(text)
