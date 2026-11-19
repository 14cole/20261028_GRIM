"""Reviewer test: real mouse clicks on Cancel at random times during real GUI solves. argv: geometry, out json"""
import os,sys,pathlib,time,json,random,copy
repo=pathlib.Path(os.environ['GRIM_ROOT']);sys.path[:0]=[str(repo),str(repo/'tools/GHOST')];os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from ghost_backend.ui.solver import SolverTab
app=QApplication([]);dialogs=[];QMessageBox.critical=lambda *a,**k:dialogs.append('critical');QMessageBox.warning=lambda *a,**k:dialogs.append('warning')
tab=SolverTab();tab.resize(1200,900);tab.show();app.processEvents();rng=random.Random(1119);out=dict(trials=[],problems=[])
def drain(s=0.3):
    t=time.monotonic()
    while time.monotonic()-t<s:app.processEvents();time.sleep(.003)
def setup(workflow,freqs='1,1.5,2,2.5,3'):
    tab.edit_geo_path.setText(str(pathlib.Path(sys.argv[1]).resolve()));tab.cmb_units.setCurrentText('meters');tab.cmb_freq_mode.setCurrentIndex(0);tab.edit_freq_list.setText(freqs)
    tab.cmb_elev_mode.setCurrentIndex(0);tab.edit_elev_list.setText(','.join(map(str,range(-90,90))));tab.chk_export_after_solve.setChecked(False)
    tab.twod_options_widget.factorization.setCurrentIndex(tab.twod_options_widget.factorization.findData('dense'));tab.cmb_mesh_workflow.setCurrentIndex(tab.cmb_mesh_workflow.findData(workflow))
def click():QTest.mouseClick(tab.btn_cancel,Qt.LeftButton)
def run(label,workflow,click_at,do_drain=True,double=False):
    if do_drain:drain()
    setup(workflow);marker=object();tab.last_result=marker;dialogs.clear();tab._run_solver();t0=time.monotonic()
    rec=dict(label=label,workflow=workflow,click_at=click_at,drained=do_drain,enabled_at_start=bool(tab.btn_cancel.isEnabled()),clicked=False);enabled=[]
    if click_at is not None and click_at<=0:
        rec['enabled_when_clicked']=bool(tab.btn_cancel.isEnabled());click();rec['clicked']=True
        if double:click()
    while tab._job_is_active():
        app.processEvents();time.sleep(.002);enabled.append(tab.btn_cancel.isEnabled())
        if click_at is not None and not rec['clicked'] and time.monotonic()-t0>=click_at:
            rec['enabled_when_clicked']=bool(tab.btn_cancel.isEnabled());rec['maximum_when_clicked']=tab.progress.maximum();click();rec['clicked']=True;rec['enabled_after_click']=bool(tab.btn_cancel.isEnabled())
            if double:click()
        if time.monotonic()-t0>300:out['problems'].append(dict(label=label,what='hang'));break
    drain(0.15)
    published=tab.last_result is not marker and tab.last_result is not None
    rec.update(seconds=time.monotonic()-t0,published=published,bar_value=tab.progress.value(),bar_maximum=tab.progress.maximum(),bar_text=tab.progress.format(),caption_visible=tab.lbl_progress.isVisible(),
        cancel_enabled_after=bool(tab.btn_cancel.isEnabled()),run_enabled_after=bool(tab.btn_run.isEnabled()),still_solving=bool(tab._is_solving),status=tab.lbl_status.text()[:70],dialogs=list(dialogs),
        fraction_of_samples_enabled=(sum(enabled)/len(enabled) if enabled else None),abort_event_after=tab._abort_event is not None,thread_after=tab._solve_thread is not None)
    ok_cancel=(not published and rec['bar_text']=='Canceled' and rec['bar_value']<100)
    ok_done=(published and rec['bar_text']=='%p%' and rec['bar_value']==100)
    rec['outcome']='cancelled' if ok_cancel else 'completed' if ok_done else 'INCONSISTENT'
    for cond,what in ((rec['bar_maximum']!=100,'bar left in activity mode'),(rec['caption_visible'],'caption left visible'),(rec['still_solving'],'still marked solving'),(rec['cancel_enabled_after'],'Cancel enabled after the job ended'),
                      (not rec['run_enabled_after'],'Run not re-enabled'),(rec['outcome']=='INCONSISTENT','inconsistent end state'),(not rec['enabled_at_start'],'Cancel not enabled at start'),(bool(dialogs),'unexpected dialog')):
        if cond:out['problems'].append(dict(label=label,what=what,rec={k:v for k,v in rec.items() if k!='status'}))
    if tab.last_result is marker:tab.last_result=None
    out['trials'].append(rec);print(label,rec['outcome'],'click_at',click_at,'enabled_at_start',rec['enabled_at_start'],'clicked-enabled',rec.get('enabled_when_clicked'),'t=%.2f'%rec['seconds'],rec['bar_text'],rec['bar_value'],flush=True);return rec
base=run('reference undisturbed','single',None);T=base['seconds']
run('first click at 0.5 s','single',0.5);run('after cleanup, click at 0.5 s','single',0.5)
run('click immediately after start','single',0.0);run('double click immediately','single',0.0,double=True)
for i in range(24):run(f'random single {i}','single',rng.random()*T*1.05)
for i in range(8):run(f'near the end {i}','single',T*(0.93+0.07*rng.random()))
for i in range(6):run(f'random check-mesh {i}','check',rng.random()*T*1.6)
for i in range(4):run(f'random automatic {i}','automatic',rng.random()*T*1.6)
run('no drain before start, click at 0.4 s','single',0.4,do_drain=False);run('no drain again, undisturbed','single',None,do_drain=False)
run('double click mid-run','single',T*0.4,double=True)
drain();click();app.processEvents();out['click_when_idle_harmless']=dict(solving=bool(tab._is_solving),run_enabled=bool(tab.btn_run.isEnabled()))
final=run('final undisturbed restart','single',None)
from collections import Counter
out['summary']=dict(outcomes=dict(Counter(t['outcome'] for t in out['trials'])),clicked=sum(t['clicked'] for t in out['trials']),clicked_while_enabled=sum(bool(t.get('enabled_when_clicked')) for t in out['trials']),problems=len(out['problems']),reference_seconds=T,final_outcome=final['outcome'])
json.dump(out,open(sys.argv[2],'w'),indent=1);print(json.dumps(out['summary']));[print(json.dumps(p)[:500]) for p in out['problems'][:6]]
