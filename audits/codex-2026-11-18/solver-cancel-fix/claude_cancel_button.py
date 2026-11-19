"""Reviewer check: is the Cancel button enabled while a real solve runs? Run once per source tree (GRIM_ROOT).
argv: geometry file, out json"""
import os,sys,pathlib,time,json
from collections import Counter
repo=pathlib.Path(os.environ['GRIM_ROOT']);sys.path[:0]=[str(repo),str(repo/'tools/GHOST')];os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMessageBox
from ghost_backend.ui.solver import SolverTab
app=QApplication([]);QMessageBox.critical=lambda *a,**k:None;QMessageBox.warning=lambda *a,**k:None
tab=SolverTab();tab.show();app.processEvents();out={}
def drain(seconds=0.5):
    t=time.monotonic()
    while time.monotonic()-t<seconds:app.processEvents();time.sleep(.005)
def setup(workflow):
    drain()  # let the previous run's thread-finished signal be delivered, as it would be in interactive use
    tab.edit_geo_path.setText(str(pathlib.Path(sys.argv[1]).resolve()));tab.cmb_units.setCurrentText('meters');tab.cmb_freq_mode.setCurrentIndex(0);tab.edit_freq_list.setText('1,2,3')
    tab.cmb_elev_mode.setCurrentIndex(0);tab.edit_elev_list.setText(','.join(map(str,range(-90,90))));tab.chk_export_after_solve.setChecked(False)
    tab.twod_options_widget.factorization.setCurrentIndex(tab.twod_options_widget.factorization.findData('dense'));tab.cmb_mesh_workflow.setCurrentIndex(tab.cmb_mesh_workflow.findData(workflow))
# 1. observe the button during an undisturbed run
setup('single');tab._run_solver();seen=Counter()
while tab._job_is_active():
    app.processEvents();time.sleep(.002);seen[(tab.btn_cancel.isEnabled(),tab._is_solving,tab._abort_event is not None)]+=1
out['undisturbed_run_samples']={str(k):v for k,v in seen.items()};out['undisturbed_result_published']=tab.last_result is not None
# 2. press the button the way a user would, part-way through a run
tab.last_result=None;setup('single');tab._run_solver();t0=time.monotonic();clicked=False
while tab._job_is_active():
    app.processEvents();time.sleep(.002)
    if not clicked and time.monotonic()-t0>0.5:
        clicked=True;out['enabled_when_clicked']=bool(tab.btn_cancel.isEnabled());out['abort_event_exists_when_clicked']=tab._abort_event is not None;tab.btn_cancel.click()
out['click_cancelled_the_run']=tab.last_result is None;out['bar_text_after_click']=tab.progress.format() if hasattr(tab.progress,'format') else None;out['status_after_click']=tab.lbl_status.text()[:90]
# 3. the handler itself works if invoked directly
tab.last_result=None;setup('single');tab._run_solver();t0=time.monotonic();called=False
while tab._job_is_active():
    app.processEvents();time.sleep(.002)
    if not called and time.monotonic()-t0>0.5:called=True;tab._cancel_solver()
out['direct_handler_cancelled_the_run']=tab.last_result is None
json.dump(out,open(sys.argv[2],'w'),indent=1);print(repo.name,json.dumps(out))
