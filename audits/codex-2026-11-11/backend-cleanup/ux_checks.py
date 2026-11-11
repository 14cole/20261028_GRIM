import json, math, sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from ghost_backend.ui.app import GhostMainWindow
import ghost_backend.ui.app as gui_module
from ghost_backend.ui.solver import _SolveWorker
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot

app=QApplication([]);w=GhostMainWindow();w.show();app.processEvents();s=w.solver_tab;g=w.geometry_tab
checks=[]
def check(name, value):
 assert value, name
 checks.append(name);print('PASS',name,flush=True)
def mode(value):
 s.cmb_mesh_workflow.setCurrentIndex(s.cmb_mesh_workflow.findData(value));app.processEvents()
def select(combo,value):
 combo.setCurrentIndex(combo.findData(value));app.processEvents()
check('startup preserves automatic checked compressed policy',s._mesh_check_enabled() and s.twod_options_widget.value()==dict(factorization='compressed',mesh_strategy='adaptive',basis_order=1,mesh_grading=True))
mode('single');select(s.twod_options_widget.factorization,'dense');select(s.twod_options_widget.mesh,'local');select(s.twod_options_widget.order,2);s.twod_options_widget.grading.setChecked(False)
manual=s.twod_options_widget.value()
mode('check');checked=s._capture_run_setup()
check('check preserves all specified settings',s.twod_options_widget.value()==manual and checked['mesh_certification'])
mode('automatic');auto=s._capture_run_setup()
check('automatic preserves backend and grading',auto['execution_options']['factorization']=='dense' and not auto['execution_options']['mesh_grading'])
mode('single');single=s._capture_run_setup()
check('return from automatic restores manual order and sizing',s.twod_options_widget.value()==manual and not single['mesh_certification'])
check('single and check share method and backend',single['solver_method']==checked['solver_method'] and single['execution_options']==checked['execution_options'])
check('single hides irrelevant comparison target',s.cmb_accuracy_target.isHidden())
select(s.cmb_solver_kind,'bor');check('BOR defaults to checked mesh without automatic option',s.cmb_mesh_workflow.currentData()=='check' and not s.cmb_mesh_workflow.model().item(2).isEnabled())
mode('single');check('BOR single request disables only mesh comparison',not s._capture_run_setup()['mesh_certification'])
select(s.cmb_solver_kind,'2d');check('2D settings survive BOR mode',s.cmb_mesh_workflow.currentData()=='single' and s.twod_options_widget.value()==manual)
select(s.cmb_scatter_mode,'bistatic');check('bistatic request retains dense path',s._capture_run_setup()['execution_options']['factorization'] in ('dense','auto') and s.cmb_mesh_workflow.currentData()=='check')
select(s.cmb_scatter_mode,'monostatic');check('monostatic choice survives bistatic mode',s.cmb_mesh_workflow.currentData()=='single' and s.twod_options_widget.value()==manual)
s._is_solving=True;s._apply_job_state();check('workflow and advanced controls locked while running',not s.cmb_mesh_workflow.isEnabled() and not s.twod_options_widget.isEnabled());s._is_solving=False;s._apply_job_state()

# Exercise the existing geometry handlers through their new menu actions.
geo=str(Path(gui_module.__file__).resolve().parents[2] / 'ghost_backend/airfoil.geo')
with patch.object(QFileDialog,'getOpenFileName',return_value=(geo,'')), patch.object(QMessageBox,'information',return_value=QMessageBox.Ok):
 check('bundled geometry loads',g.load_geo())
original=[list(x.properties) for x in g.segments]
g.action_find_refinement.trigger();check('find action selects without changing mesh',bool(g.table.selectedIndexes()) and original==[list(x.properties) for x in g.segments])
g.action_ibc_add.trigger();g.table_ibc.selectRow(0);g.table.selectRow(0);app.processEvents()
check('assignment available for conductor and impedance',g.btn_assign_material.isEnabled())
g.action_apply_conductor_ibc.trigger();check('assignment action changes selected conductor flag',g.segments[0].properties[2]=='1')
g.table.selectRow(1);check('assignment disabled on dielectric boundary',not g.btn_assign_material.isEnabled())
g.table.selectRow(0)
with patch('ghost_backend.ui.geometry.choose_thin_layer',return_value=['thin_dielectric','0.001','1']):
 g.action_thin_layer_add.trigger()
check('thin layer action creates material definition',any(row[1]=='thin_dielectric' for row in g._read_small_table(g.table_ibc)))
g.table_ibc.selectRow(g.table_ibc.rowCount()-1);check('thin dielectric cannot be assigned as conductor impedance',not g.btn_assign_material.isEnabled())
select(g.cmb_geometry_mode,'bor');check('thin layer creation disabled for BOR',not g.action_thin_layer_add.isEnabled());select(g.cmb_geometry_mode,'2d')
g.table_ibc.clearSelection();check('remove action needs explicit material selection',not g.btn_ibc_remove.isEnabled())

# Real worker-path solves, keeping the same mesh and physical request.
count=48;radius=.1;points=[(radius*math.cos(-2*math.pi*i/count),radius*math.sin(-2*math.pi*i/count)) for i in range(count)];points.append(points[0])
text='Title: UX smoke\nSegment: circle\nproperties: 2 1 0 0 0\n'+'\n'.join(' '.join(str(v) for v in (*a,*b)) for a,b in zip(points,points[1:]))+'\nIBCS_Resistances:\nDielectrics:\n'
snapshot=build_geometry_snapshot(*parse_geometry(text))
s.cmb_units.setCurrentText('meters');s.cmb_freq_mode.setCurrentIndex(0);s.edit_freq_list.setText('0.3');s.cmb_elev_mode.setCurrentIndex(0);s.edit_elev_list.setText('0, 90');select(s.cmb_scatter_mode,'monostatic')
select(s.twod_options_widget.mesh,'global');select(s.twod_options_widget.order,1);s.twod_options_widget.grading.setChecked(False)
results=[]
for backend in ('dense','compressed'):
 select(s.twod_options_widget.factorization,backend)
 for workflow in ('single','check','automatic'):
  mode(workflow);request=s._capture_run_setup()
  worker=_SolveWorker(snapshot=snapshot,source_path='',base_dir='/tmp',frequencies=[.3],elevations=[0,90],units='meters',quality_thresholds=dict(residual_norm_max=1e-6,condition_est_max=1e6,warnings_max=10),mesh_certification=request['mesh_certification'],solver_method=request['solver_method'],execution_options=request['execution_options'],accuracy_target='standard',preflight_setup=request)
  completed=[];errors=[]
  worker.finished.connect(lambda result, _path: completed.append(result))
  worker.error.connect(errors.append)
  worker.run()
  assert completed, errors
  result=completed[0]
  meta=result['metadata'];cert=meta.get('mesh_convergence_certified',False)
  check(f'{backend}/{workflow} real solve returns correct certification state',bool(cert)==(workflow!='single') and len(result['samples'])==4)
  effective=meta.get('execution_options',{}).get('factorization')
  # Merged results retain per-channel metadata on some paths.
  channels=meta.get('channel_metadata',{})
  records=[meta]+list(channels.values())
  recorded=[m.get('execution_options',{}).get('factorization') for m in records if m.get('execution_options',{}).get('factorization')]
  check(f'{backend}/{workflow} keeps selected backend',bool(recorded) and all(x==backend for x in recorded))
  results.append(dict(backend=backend,workflow=workflow,certified=cert,recorded_backends=recorded,panels=meta.get('panel_count')))
Path(__file__).with_name('ux-check-results.json').write_text(json.dumps(dict(checks=checks,solves=results),indent=2))
print(json.dumps(dict(passed=len(checks),solves=results),indent=2))
