"""Targeted checks for Claude's distribution review; run with GHOST on PYTHONPATH."""
import json
from pathlib import Path
from PySide6.QtCore import QEvent
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QToolTip
from ghost_backend.ui.app import GhostMainWindow
from ghost_backend.runs.controls import run_control_summary
import ghost_backend.ui.app as gui_module

app=QApplication([]);w=GhostMainWindow();w.show();g=w.geometry_tab;s=w.solver_tab
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name);print('PASS',name,flush=True)
def choose(combo,value):
    combo.setCurrentIndex(combo.findData(value));app.processEvents()
for name in ('btn_segment_tools','btn_assign_material','btn_add_surface_material'):
    check(name+' enables menu tooltips',getattr(g,name).menu().toolTipsVisible())
check('refinement help explains automatic N', '40 panels' in g.action_refine_selected.toolTip())
check('CSV help includes column names and units','frequency_hz,resistance_ohm,reactance_ohm' in g.action_ibc_add_csv.toolTip())
menu=g.btn_segment_tools.menu();menu.popup(g.btn_segment_tools.mapToGlobal(g.btn_segment_tools.rect().bottomLeft()));app.processEvents()
action=g.action_find_refinement;point=menu.actionGeometry(action).center()
app.sendEvent(menu,QHelpEvent(QEvent.ToolTip,point,menu.mapToGlobal(point)));app.processEvents()
check('Qt actually displays the action help',QToolTip.isVisible() and QToolTip.text()==action.toolTip())
QToolTip.hideText();menu.close()
for table,add,remove,button in ((g.table_ibc,g._ibc_add_row,g._ibc_remove_row,g.btn_ibc_remove),
                               (g.table_diel,g._diel_add_row,g._diel_remove_row,g.btn_diel_remove)):
    add();add();table.clearSelection();app.processEvents()
    check(button.text()+' disabled without selection',not button.isEnabled())
    remove();check('no-selection removal is a no-op',table.rowCount()==2)
    table.selectRow(0);app.processEvents();check('selection enables removal',button.isEnabled())
    button.click();check('removes only selected material',table.rowCount()==1 and table.item(0,0).text()=='2')
w.tabs.setCurrentWidget(s);s.btn_tools.setChecked(True)
choose(s.cmb_mesh_workflow,'single');choose(s.twod_options_widget.factorization,'dense')
for mode in ('single','check','automatic'):
    choose(s.cmb_mesh_workflow,mode)
    check(mode+' policy uses the workflow label',s.cmb_mesh_workflow.currentText() in s.lbl_run_policy.text())
    check(mode+' policy drops old checkbox wording', 'Mesh certification:' not in s.lbl_run_policy.text() and 'Survey' not in s.lbl_run_policy.text())
check('Dense label is a direct choice',s.twod_options_widget.factorization.currentText()=='Dense')
choose(s.cmb_solver_kind,'bor');check('BoR has no stale 2D policy',s.lbl_run_policy.isHidden() and not s.lbl_run_policy.text())
check('BoR identifies its solver','BoR modal solver' in s.lbl_linear_solver.text())
choose(s.cmb_solver_kind,'2d');check('2D policy restored on return',bool(s.lbl_run_policy.text()) and s.twod_options_widget.factorization.currentData()=='dense')
root=Path(gui_module.__file__).resolve().parents[2];guide=' '.join((root/'GEOMETRY_INPUT_CHEATSHEET.md').read_text().split())
check('guide has no removed control labels',all(x not in guide for x in ('**Certify mesh convergence**','**Find corners/junctions**','**Reverse selected**','**+ Thin layer**')))
check('guide describes selection-only corner action','without changing the mesh' in guide)
Path(__file__).with_name('review-check-results.json').write_text(json.dumps(dict(passed=len(checks),checks=checks),indent=2))
print('Passed:',len(checks))
