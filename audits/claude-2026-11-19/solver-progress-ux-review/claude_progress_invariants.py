"""Reviewer T1: randomized lifecycle test of the progress display on the real SolverTab (Qt offscreen).
The widget's own slots are driven directly; one real solve supplies a genuine result object.
argv: work dir, out json"""
import os,sys,pathlib,json,math,time,copy,threading,random,traceback
work=pathlib.Path(sys.argv[1]);work.mkdir(parents=True,exist_ok=True)
repo=pathlib.Path(os.environ['GRIM_ROOT']);sys.path[:0]=[str(repo),str(repo/'tools/GHOST')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');os.environ.setdefault('MPLCONFIGDIR',str(work/'mpl'));os.environ.setdefault('XDG_CACHE_HOME',str(work/'cache'))
from PySide6.QtWidgets import QApplication,QMessageBox
from ghost_backend.ui.solver import SolverTab
app=QApplication([]);dialogs=[]
QMessageBox.critical=lambda *a,**k:dialogs.append('critical');QMessageBox.warning=lambda *a,**k:dialogs.append('warning')
QMessageBox.information=lambda *a,**k:dialogs.append('information')
tab=SolverTab();tab.resize(1200,900);tab.show();app.processEvents()
p=[(.05*math.cos(-2*math.pi*i/64),.05*math.sin(-2*math.pi*i/64)) for i in range(64)];p.append(p[0])
geo=work/'c.geo';geo.write_text('Title: reviewer\nSegment: body 2\nproperties: 2 1 0 0 0\n'+'\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(p[:-1],p[1:]))+'\n')
tab.edit_geo_path.setText(str(geo));tab.cmb_units.setCurrentText('meters');tab.cmb_freq_mode.setCurrentIndex(0);tab.edit_freq_list.setText('1')
tab.cmb_elev_mode.setCurrentIndex(0);tab.edit_elev_list.setText(','.join(map(str,range(-90,90,10))));tab.chk_export_after_solve.setChecked(False)
tab.twod_options_widget.factorization.setCurrentIndex(tab.twod_options_widget.factorization.findData('dense'));tab.cmb_mesh_workflow.setCurrentIndex(tab.cmb_mesh_workflow.findData('single'))
tab._run_solver()
while tab._job_is_active():app.processEvents();time.sleep(.002)
real_result=copy.deepcopy(tab.last_result);real_context=copy.deepcopy(tab.last_solve_context);real_source=tab.last_source_path;assert real_result is not None
rng=random.Random(20261119);violations=[];counts={}
def snap():return dict(value=tab.progress.value(),minimum=tab.progress.minimum(),maximum=tab.progress.maximum(),fmt=tab.progress.format(),caption=tab.lbl_progress.isVisible(),status=tab.lbl_status.text())
def fail(trial,step,what,**extra):violations.append(dict(trial=trial,step=step,what=what,**extra))
def begin(cert,kind):
    tab._start_solver_progress(cert,kind);tab._set_solving_state(True);tab._abort_event=threading.Event();tab._pending_solve_context=copy.deepcopy(real_context)
terminals=['error','cancel','finished','finished_after_abort','cancel_then_late_finished','finished_export_ok','finished_export_raises']
for trial in range(400):
    cert=rng.random()<.4;kind=rng.choice(['2d','2d','bor']);begin(cert,kind);expect_activity=bool(cert or kind=='bor');s=snap();last=0
    if s['fmt']!='%p%' or (not expect_activity and (s['value']!=0 or s['maximum']!=100)) or (expect_activity and s['maximum']!=0):fail(trial,'start','start state wrong',snap=s)
    if expect_activity!=s['caption']:fail(trial,'start','caption visibility wrong at start',snap=s)
    for i in range(rng.randint(0,40)):
        r=rng.random()
        if r<.15:tab._on_execution_progress(dict(elapsed_seconds=rng.random()*500,stage=rng.choice(['assembly','factorization','solve']),rss_bytes=rng.randint(1,10**10)))
        else:
            pct=rng.choice([-1,-5,0,1,rng.randint(0,100),rng.randint(0,100),100,100,150,rng.randint(0,30)]);tab._on_solver_progress(pct,rng.choice(['','stage text','pass %d'%i]))
            if pct<0:expect_activity=True
        s=snap()
        if expect_activity:
            if s['maximum']!=0 or not s['caption']:fail(trial,i,'activity mode not shown while active',snap=s)
        else:
            if s['maximum']!=100:fail(trial,i,'determinate range lost',snap=s)
            if s['value']<last:fail(trial,i,'bar moved backwards',before=last,snap=s)
            if s['value']>=100:fail(trial,i,'bar at 100 before the job ended',snap=s)
            last=s['value']
    t=rng.choice(terminals);counts[t]=counts.get(t,0)+1;dialogs.clear();err=None
    try:
        if t=='error':tab._on_solver_error('simulated failure')
        elif t=='cancel':tab._abort_event.set();tab._on_solver_canceled('Solve canceled by user.')
        elif t=='finished':tab.chk_export_after_solve.setChecked(False);tab._on_solver_finished(copy.deepcopy(real_result),real_source)
        elif t=='finished_after_abort':tab._abort_event.set();tab._on_solver_finished(copy.deepcopy(real_result),real_source)
        elif t=='cancel_then_late_finished':
            tab._abort_event.set();tab._on_solver_canceled('Solve canceled by user.');tab._on_solver_finished(copy.deepcopy(real_result),real_source)
        else:
            tab.chk_export_after_solve.setChecked(True);orig=tab._export_result_files
            if t=='finished_export_ok':tab._export_result_files=lambda *a,**k:[]
            else:
                def boom(*a,**k):raise OSError('simulated export failure')
                tab._export_result_files=boom
            try:tab._on_solver_finished(copy.deepcopy(real_result),real_source)
            finally:tab._export_result_files=orig;tab.chk_export_after_solve.setChecked(False)
    except Exception as e:err=traceback.format_exc()[-600:]
    s=snap();expected_fmt={'error':'Failed','cancel':'Canceled','finished_after_abort':'Canceled','cancel_then_late_finished':'Canceled'}.get(t,'%p%')
    if err:fail(trial,'terminal','handler raised',terminal=t,error=err)
    if s['maximum']!=100 or s['minimum']!=0:fail(trial,'terminal','bar left in activity mode after the job ended',terminal=t,snap=s)
    if s['caption']:fail(trial,'terminal','caption left visible after the job ended',terminal=t,snap=s)
    if tab._is_solving:fail(trial,'terminal','still marked as solving',terminal=t)
    if s['fmt']!=expected_fmt:fail(trial,'terminal','unexpected bar text',terminal=t,snap=s,expected=expected_fmt)
    if t in('finished','finished_export_ok','finished_export_raises') and s['value']!=100:fail(trial,'terminal','successful solve did not end at 100',terminal=t,snap=s)
    if t in('error','cancel','finished_after_abort','cancel_then_late_finished') and s['value']>=100:fail(trial,'terminal','failed or cancelled job shows 100',terminal=t,snap=s)
    before=snap()
    for i in range(rng.randint(1,6)):
        if rng.random()<.5:tab._on_solver_progress(rng.choice([-1,0,50,100]),'late message')
        else:tab._on_execution_progress(dict(elapsed_seconds=999,stage='solve',rss_bytes=1))
    if snap()!=before:fail(trial,'late','late event changed the display',terminal=t,before=before,after=snap())
    tab._abort_event=None
# shared bar: density start after a failed job must clear the label
begin(False,'2d');tab._on_solver_error('x');tab._stop_solver_progress(0);s=snap()
if s['fmt']!='%p%' or s['value']!=0:fail(-1,'density','label leaked into the next use of the bar',snap=s)
# invalid setup after a completed job
tab._abort_event=None;tab.edit_freq_list.setText('not a number');tab._run_solver();s=snap();tab.edit_freq_list.setText('1')
invalid=dict(snap=s,job_active=tab._job_is_active())
out=dict(trials=400,terminal_counts=counts,violations=len(violations),first_violations=violations[:12],invalid_setup=invalid)
json.dump(out,open(sys.argv[2],'w'),indent=1);print(json.dumps({k:v for k,v in out.items() if k!='first_violations'}))
from collections import Counter
print(Counter((v['what'],v.get('terminal')) for v in violations).most_common(12))
for v in violations[:3]:print(json.dumps(v)[:700])
