"""Qt integration checks: real solves plus progress/terminal/export regressions."""
import os,sys,pathlib,json,threading,math,copy,time
r=pathlib.Path(__file__).resolve().parent
repo=pathlib.Path(os.environ.get('GRIM_ROOT',r/'candidate'))
sys.path[:0]=[str(repo),str(repo/'tools/GHOST')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('MPLCONFIGDIR',str(r/'mpl-cache'))
os.environ.setdefault('XDG_CACHE_HOME',str(r/'cache'))
from PySide6.QtWidgets import QApplication,QMessageBox,QScrollArea
from ghost_backend.ui.solver import SolverTab,_SolveWorker
app=QApplication([]);messages=[]
QMessageBox.critical=lambda *a:messages.append(('critical',str(a[-1])))
QMessageBox.warning=lambda *a:messages.append(('warning',str(a[-1])))
class ObservedTab(SolverTab):
    def __init__(self):
        self.trace=[]
        super().__init__()
    def _on_solver_progress(self,pct,message):
        super()._on_solver_progress(pct,message)
        self.trace.append(dict(input=pct,value=self.progress.value(),maximum=self.progress.maximum(),message=message))
tab=ObservedTab();tab.resize(1250,900);tab.show();app.processEvents()
checks=[]
def record(name):checks.append(name)
def start(cert=False,kind='2d'):
    tab._abort_event=threading.Event();tab._is_solving=True
    tab._start_solver_progress(cert,kind);tab.trace=[]
start()
for p in (0,60,15,0,80,100):tab._on_solver_progress(p,'nested work')
assert [e['value'] for e in tab.trace]==[0,60,60,60,80,99]
record('fixed work never regresses and does not show premature 100')
tab._on_solver_canceled('Canceled by operator')
assert tab.progress.maximum()==100 and tab.progress.format()=='Canceled'
before=tab.lbl_status.text();tab._on_solver_progress(100,'late');tab._on_execution_progress(dict(stage='late',elapsed_seconds=2))
assert tab.lbl_status.text()==before and tab.progress.value()==99
record('cancellation stops activity and ignores queued progress/telemetry')
start(True)
for p in (0,90,100,0,25,100):tab._on_solver_progress(p,'Adaptive mesh: refinement')
assert all(e['maximum']==0 for e in tab.trace)
tab._on_execution_progress(dict(stage='Solving right-hand sides',phase='Refined mesh',elapsed_seconds=65,process_rss_bytes=2**30))
assert 'Refined mesh' in tab.lbl_status.text() and '1m 05s' in tab.lbl_status.text()
tab._abort_event.set();tab._cancel_solver();before=tab.lbl_status.text()
tab._on_execution_progress(dict(stage='late',elapsed_seconds=3));tab._on_solver_progress(0,'retry')
assert tab.lbl_status.text()==before
tab._on_solver_canceled('Canceled')
assert tab.progress.maximum()==100
record('convergence retries stay indeterminate; stage and cancellation status retained')
start(False,'bor');assert tab.progress.maximum()==0 and 'mode convergence' in tab.lbl_progress.text()
tab._on_solver_error('simulated failure');assert tab.progress.maximum()==100 and tab.progress.format()=='Failed'
record('BoR remains indeterminate and failure restores a stopped bar')
start();assert tab.progress.value()==0 and tab.progress.maximum()==100 and tab.progress.format()=='%p%'
tab._on_solver_progress(-1,'Unknown work');assert tab.progress.maximum()==0
tab._on_solver_progress(90,'local estimate');assert tab.progress.maximum()==0
tab._on_solver_canceled('Canceled')
record('restart resets old state; unknown totals latch activity mode')
class Emitter:
    def emit(self,*args):self.last=args
class WorkerStub:progress=Emitter()
w=WorkerStub();_SolveWorker._on_progress(w,3,0,'unknown');assert w.progress.last==(-1,'unknown')
_SolveWorker._on_progress(w,100,100,'done');assert w.progress.last==(100,'done')
record('worker distinguishes unknown denominator from zero-percent work')

# Tiny closed PEC contour, fixed positive panel counts; genuine public GUI runs.
geo=r/'pec-circle.geo';points=[(.05*math.cos(-2*math.pi*i/64),.05*math.sin(-2*math.pi*i/64)) for i in range(64)];points.append(points[0])
geo.write_text('Title: Progress integration PEC circle\nSegment: body 2\nproperties: 2 1 0 0 0\n'+'\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(points[:-1],points[1:]))+'\n')
tab.edit_geo_path.setText(str(geo));tab.cmb_units.setCurrentText('meters')
tab.cmb_freq_mode.setCurrentIndex(0);tab.edit_freq_list.setText('1')
tab.cmb_elev_mode.setCurrentIndex(0);tab.edit_elev_list.setText(','.join(map(str,range(-90,90))))
tab.chk_export_after_solve.setChecked(False)
tab.twod_options_widget.factorization.setCurrentIndex(tab.twod_options_widget.factorization.findData('dense'))
tab.twod_options_widget.grading.setChecked(False)
results={}
for mode in ('single','check','automatic'):
    tab.cmb_mesh_workflow.setCurrentIndex(tab.cmb_mesh_workflow.findData(mode));tab.trace=[];messages.clear()
    tab._run_solver();assert tab._solve_thread is not None,(mode,messages)
    assert tab.progress.maximum()==(100 if mode=='single' else 0)
    deadline=time.monotonic()+120
    while tab._job_is_active():
        app.processEvents();time.sleep(.005)
        if time.monotonic()>deadline:
            tab._cancel_solver();raise RuntimeError('Unexpected integration timeout')
    assert not messages,(mode,messages)
    assert tab.progress.maximum()==100 and tab.progress.value()==100
    result=copy.deepcopy(tab.last_result);assert result['metadata']['quality_gate']['passed']
    if mode!='single':assert result['metadata']['mesh_convergence_certified']
    if mode=='single':
        values=[e['value'] for e in tab.trace];assert values==sorted(values) and max(values)<=99
    else:assert tab.trace and all(e['maximum']==0 for e in tab.trace)
    results[mode]=dict(trace=tab.trace,metadata=result['metadata'],status=tab.lbl_status.text())
    if mode=='single':single_result=copy.deepcopy(result)
    (r/f'result-{mode}.json').write_text(json.dumps(result,indent=2,default=lambda value:value.tolist() if hasattr(value,'tolist') else list(value))+'\n')
    print('PASS actual GUI run',mode,len(tab.trace),'callbacks',flush=True)
record('three actual GUI worker solves: specified, checked, automatic; 180 monostatic angles')
tab.edit_freq_list.setText('invalid');messages.clear();tab._run_solver()
assert messages and tab.progress.value()==0 and tab.progress.format()=='Failed' and not tab._job_is_active()
tab.edit_freq_list.setText('1')
record('invalid new setup replaces the previous completed bar with Failed')

# Reuse an actual result to cover output dialogs and terminal paths without another numerical solve.
result=single_result
def ready_result():
    start();tab._pending_solve_context={};tab._on_solver_progress(100,'local completion')
tab.chk_export_after_solve.setChecked(True);tab.edit_output.setText(str(r/'test-output.grim'))
tab._confirm_export_replacements=lambda paths:True
tab._result_is_current_for_export=lambda *args:True
def export(*args,**kwargs):
    assert tab.progress.value()==99
    before=tab.lbl_status.text();tab._on_execution_progress(dict(stage='late',elapsed_seconds=10));tab._on_solver_progress(0,'late')
    assert tab.lbl_status.text()==before
    return []
tab._export_result_files=export
ready_result();tab._on_solver_finished(copy.deepcopy(result),str(geo));assert tab.progress.value()==100
record('100 only after export; queued events cannot overwrite finishing status')
tab._confirm_export_replacements=lambda paths:False
ready_result();tab._on_solver_finished(copy.deepcopy(result),str(geo));assert tab.progress.value()==100 and not tab._is_solving
record('declined automatic export completes result progress')
tab._confirm_export_replacements=lambda paths:True;tab._result_is_current_for_export=lambda *args:False
ready_result();tab._on_solver_finished(copy.deepcopy(result),str(geo));assert tab.progress.value()==100
record('stale export skip stops progress')
tab._result_is_current_for_export=lambda *args:True
def failed_export(*args,**kwargs):raise OSError('simulated export failure')
tab._export_result_files=failed_export
ready_result();tab._on_solver_finished(copy.deepcopy(result),str(geo));assert tab.progress.value()==100 and not tab._is_solving
record('export failure stops progress and retains completed solve')
tab.chk_export_after_solve.setChecked(False)
partial=copy.deepcopy(result);partial['metadata'].update(partial_result=True,frequency_checkpoints={'completed':1},requested_frequency_count=2)
ready_result();tab._on_solver_finished(partial,str(geo));assert tab.progress.value()==50 and 'Partial' in tab.progress.format()
record('partial result reports completed frequencies without 100')
start(True);tab._stop_solver_progress(0);tab._is_solving=False;tab._on_density_progress(45,'Density')
assert tab.progress.maximum()==100 and tab.progress.value()==45 and tab.progress.format()=='%p%'
record('density calculation can reuse progress bar after convergence')

# Visual evidence uses the real widget and a representative convergence notification.
start(True);tab._on_solver_progress(0,'Adaptive mesh: cubic accuracy check')
tab._on_execution_progress(dict(stage='Solving right-hand sides',phase='Refined mesh',elapsed_seconds=65,process_rss_bytes=2**30))
for scroll in tab.findChildren(QScrollArea):
    if scroll.widget() and scroll.widget().isAncestorOf(tab.progress):scroll.ensureWidgetVisible(tab.progress)
app.processEvents();assert tab.grab().save(str(r/'convergence-progress.png'))
tab._on_solver_canceled('Validation complete');tab.close();app.processEvents()
(r/'checks.json').write_text(json.dumps(dict(checks=checks,real_runs=results,qt_platform='offscreen'),indent=2,default=str)+'\n')
print('PASS',len(checks),'checks',flush=True)
