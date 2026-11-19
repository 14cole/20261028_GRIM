"""Independent Qt mouse-click regression with clean thread/event teardown."""
import os,sys,pathlib,time,json
r=pathlib.Path(__file__).resolve().parent
repo=pathlib.Path(os.environ.get('GRIM_ROOT',r/'candidate'))
sys.path[:0]=[str(repo),str(repo/'tools/GHOST')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('MPLCONFIGDIR',str(r/'mpl-cache'))
os.environ.setdefault('XDG_CACHE_HOME',str(r/'cache'))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from ghost_backend.ui.solver import SolverTab
app=QApplication([]);tab=SolverTab();tab.resize(1250,950);tab.show();app.processEvents()
errors=[];records=[];events=[]
QMessageBox.critical=lambda *a,**k:errors.append(str(a[-1]))
QMessageBox.warning=lambda *a,**k:errors.append(str(a[-1]))
def drain_until_done():
    deadline=time.monotonic()+90
    while tab._job_is_active() or tab._solve_thread is not None:
        app.processEvents();time.sleep(.003)
        assert time.monotonic()<deadline,'worker did not finish'
    for _ in range(10):app.processEvents();time.sleep(.003)
    assert tab._abort_event is None and tab._active_solve_run_id is None
    assert not tab.btn_cancel.isEnabled() and tab.btn_run.isEnabled()
def setup(mode,frequencies):
    drain_until_done()
    tab.edit_geo_path.setText(str(r/'circle.geo'));tab.cmb_units.setCurrentText('meters')
    tab.cmb_freq_mode.setCurrentIndex(0);tab.edit_freq_list.setText(frequencies)
    tab.cmb_elev_mode.setCurrentIndex(0);tab.edit_elev_list.setText(','.join(map(str,range(-90,90))))
    tab.chk_export_after_solve.setChecked(False)
    tab.twod_options_widget.factorization.setCurrentIndex(tab.twod_options_widget.factorization.findData('dense'))
    tab.cmb_mesh_workflow.setCurrentIndex(tab.cmb_mesh_workflow.findData(mode))
def begin():
    assert tab._abort_event is None
    tab._run_solver()
    assert tab._is_solving and tab.btn_cancel.isEnabled()
    event=tab._abort_event;assert event is not None and not event.is_set()
    assert all(event is not old for old in events)
    events.append(event);return event
setup('single','1');begin();drain_until_done()
assert not errors and tab.last_result is not None and tab.progress.value()==100
prior=tab.last_result
assert prior['metadata']['quality_gate']['passed']
records.append(dict(case='initial_success',progress=100,quality_gate=True))
for mode in ('single','check','automatic'):
    setup(mode,'1,2,3');event=begin();started=time.monotonic()
    while time.monotonic()-started<.4:
        app.processEvents();time.sleep(.003)
    assert tab._is_solving and tab.btn_cancel.isEnabled() and tab.btn_cancel.isVisible()
    # QTest sends actual mouse press/release events; it does not call the handler.
    QTest.mouseClick(tab.btn_cancel,Qt.LeftButton)
    assert event.is_set() and not tab.btn_cancel.isEnabled()
    assert 'Canceling' in tab.lbl_status.text()
    drain_until_done()
    assert tab.last_result is prior,'canceled solve replaced the previous result'
    assert tab.progress.maximum()==100 and tab.progress.value()<100 and tab.progress.format()=='Canceled'
    assert not errors,errors
    records.append(dict(case='mouse_cancel_'+mode,enabled_at_click=True,abort_set=True,
                        prior_result_preserved=True,clean_teardown=True,status=tab.lbl_status.text()))
    print('PASS real mouse cancellation:',mode,flush=True)
setup('single','1');event=begin();drain_until_done()
assert not errors and tab.last_result is not prior and tab.progress.value()==100 and tab.progress.format()=='%p%'
assert tab.last_result['metadata']['quality_gate']['passed'] and not event.is_set()
records.append(dict(case='success_after_cancellations',progress=100,quality_gate=True,fresh_event=True))
(r/'cancel-regression.json').write_text(json.dumps(dict(cases=records,errors=errors,qt='PySide6 offscreen',angles=180,all_pass=True),indent=2)+'\n')
tab.close();app.processEvents();print('PASS five real GUI jobs: two completions and three mouse cancellations',flush=True)
