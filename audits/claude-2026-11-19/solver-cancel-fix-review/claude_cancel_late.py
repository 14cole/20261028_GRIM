"""Reviewer test: real mouse click on Cancel triggered by the bar value, to hit the end-of-run window. argv: geometry, out json"""
import os,sys,pathlib,time,json
repo=pathlib.Path(os.environ['GRIM_ROOT']);sys.path[:0]=[str(repo),str(repo/'tools/GHOST')];os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from ghost_backend.ui.solver import SolverTab
app=QApplication([]);dialogs=[];QMessageBox.critical=lambda *a,**k:dialogs.append('critical');QMessageBox.warning=lambda *a,**k:dialogs.append('warning')
tab=SolverTab();tab.resize(1200,900);tab.show();app.processEvents();out=[]
def drain(s=0.3):
    t=time.monotonic()
    while time.monotonic()-t<s:app.processEvents();time.sleep(.003)
for threshold in (90,95,97,98,99,99,99,99,99,99,99,99):
    drain();tab.edit_geo_path.setText(str(pathlib.Path(sys.argv[1]).resolve()));tab.cmb_units.setCurrentText('meters');tab.cmb_freq_mode.setCurrentIndex(0);tab.edit_freq_list.setText('1,1.5,2,2.5,3')
    tab.cmb_elev_mode.setCurrentIndex(0);tab.edit_elev_list.setText(','.join(map(str,range(-90,90))));tab.chk_export_after_solve.setChecked(False)
    tab.twod_options_widget.factorization.setCurrentIndex(tab.twod_options_widget.factorization.findData('dense'));tab.cmb_mesh_workflow.setCurrentIndex(tab.cmb_mesh_workflow.findData('single'))
    marker=object();tab.last_result=marker;dialogs.clear();tab._run_solver();t0=time.monotonic();rec=dict(threshold=threshold,clicked=False)
    while tab._job_is_active():
        app.processEvents()
        if not rec['clicked'] and tab.progress.value()>=threshold:
            rec.update(clicked=True,value_when_clicked=tab.progress.value(),enabled_when_clicked=bool(tab.btn_cancel.isEnabled()),finishing_when_clicked=bool(tab._solver_finishing),click_time=time.monotonic()-t0);QTest.mouseClick(tab.btn_cancel,Qt.LeftButton)
        assert time.monotonic()-t0<300
    drain(0.15);published=tab.last_result is not marker and tab.last_result is not None
    rec.update(seconds=time.monotonic()-t0,published=published,bar_value=tab.progress.value(),bar_maximum=tab.progress.maximum(),bar_text=tab.progress.format(),caption_visible=tab.lbl_progress.isVisible(),still_solving=bool(tab._is_solving),
        cancel_enabled_after=bool(tab.btn_cancel.isEnabled()),run_enabled_after=bool(tab.btn_run.isEnabled()),dialogs=list(dialogs),status=tab.lbl_status.text()[:60])
    rec['outcome']='cancelled' if (not published and rec['bar_text']=='Canceled' and rec['bar_value']<100) else 'completed' if (published and rec['bar_text']=='%p%' and rec['bar_value']==100) else 'INCONSISTENT'
    rec['clean']=bool(rec['outcome']!='INCONSISTENT' and rec['bar_maximum']==100 and not rec['caption_visible'] and not rec['still_solving'] and not rec['cancel_enabled_after'] and rec['run_enabled_after'] and not dialogs)
    if tab.last_result is marker:tab.last_result=None
    out.append(rec);print({k:rec[k] for k in ('threshold','value_when_clicked','enabled_when_clicked','finishing_when_clicked','outcome','clean','bar_value','bar_text')},flush=True)
json.dump(out,open(sys.argv[2],'w'),indent=1);print('all clean',all(r['clean'] for r in out),'outcomes',[r['outcome'] for r in out])
