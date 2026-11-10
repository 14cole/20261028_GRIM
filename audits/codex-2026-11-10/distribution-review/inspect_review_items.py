import json,sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from ghost_backend.ui.app import GhostMainWindow
app=QApplication([]);w=GhostMainWindow();w.show();s=w.solver_tab;g=w.geometry_tab
w.tabs.setCurrentWidget(s);s.btn_tools.setChecked(True)
def choose(combo,value):
 combo.setCurrentIndex(combo.findData(value));app.processEvents()
choose(s.cmb_mesh_workflow,'single');choose(s.twod_options_widget.factorization,'dense');choose(s.twod_options_widget.mesh,'local');choose(s.twod_options_widget.order,2);s.twod_options_widget.grading.setChecked(False)
choose(s.cmb_solver_kind,'bor');app.processEvents()
s.controls_scroll.verticalScrollBar().setValue(s.controls_scroll.verticalScrollBar().maximum());app.processEvents()
r={'bor_policy':{'text':s.lbl_run_policy.text(),'isVisible':s.lbl_run_policy.isVisible(),'isHidden':s.lbl_run_policy.isHidden()},'bor_linear_solver':s.lbl_linear_solver.text(),'menus':{}}
for name in ('btn_segment_tools','btn_assign_material','btn_add_surface_material'):
 menu=getattr(g,name).menu();r['menus'][name]={'toolTipsVisible':menu.toolTipsVisible(),'actions':[{ 'text':a.text(),'tooltip':a.toolTip()} for a in menu.actions()]}
choose(s.cmb_solver_kind,'2d');r['single_policy']=s.lbl_run_policy.text();choose(s.cmb_mesh_workflow,'check');r['check_policy']=s.lbl_run_policy.text()
g._diel_add_row();g._diel_add_row();g.table_diel.clearSelection();r['dielectric_remove']={'before':g.table_diel.rowCount(),'button_enabled':g.btn_diel_remove.isEnabled()};g.btn_diel_remove.click();r['dielectric_remove']['after']=g.table_diel.rowCount()
Path(sys.argv[1]).write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
