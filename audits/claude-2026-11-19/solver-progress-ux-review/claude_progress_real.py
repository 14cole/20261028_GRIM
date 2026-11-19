"""Reviewer T2: real GUI solves on the real SolverTab (Qt offscreen), recording every progress event with a timestamp.
argv: work dir, out json"""
import os,sys,pathlib,json,math,time,copy
work=pathlib.Path(sys.argv[1]);work.mkdir(parents=True,exist_ok=True)
repo=pathlib.Path(os.environ['GRIM_ROOT']);sys.path[:0]=[str(repo),str(repo/'tools/GHOST')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');os.environ.setdefault('MPLCONFIGDIR',str(work/'mpl'));os.environ.setdefault('XDG_CACHE_HOME',str(work/'cache'))
from PySide6.QtWidgets import QApplication,QMessageBox
from ghost_backend.ui.solver import SolverTab
app=QApplication([]);messages=[]
QMessageBox.critical=lambda *a:messages.append(('critical',str(a[-1])));QMessageBox.warning=lambda *a:messages.append(('warning',str(a[-1])))
class Tab(SolverTab):
    def __init__(self):
        self.trace=[];self.t0=0.;super().__init__()
    def _on_solver_progress(self,pct,message):
        super()._on_solver_progress(pct,message)
        self.trace.append((time.monotonic()-self.t0,int(pct),self.progress.value(),self.progress.maximum(),message))
tab=Tab();tab.resize(1200,900);tab.show();app.processEvents()
def geometry(name,diameter,panels):
    p=[(.5*diameter*math.cos(-2*math.pi*i/panels),.5*diameter*math.sin(-2*math.pi*i/panels)) for i in range(panels)];p.append(p[0])
    f=work/(name+'.geo');f.write_text('Title: reviewer PEC circle\nSegment: body 2\nproperties: 2 1 0 0 0\n'+'\n'.join('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(p[:-1],p[1:]))+'\n');return f
def run(label,geo,freqs,workflow='single',angles=range(-90,90)):
    tab.edit_geo_path.setText(str(geo));tab.cmb_units.setCurrentText('meters');tab.cmb_freq_mode.setCurrentIndex(0);tab.edit_freq_list.setText(freqs)
    tab.cmb_elev_mode.setCurrentIndex(0);tab.edit_elev_list.setText(','.join(map(str,angles)));tab.chk_export_after_solve.setChecked(False)
    tab.twod_options_widget.factorization.setCurrentIndex(tab.twod_options_widget.factorization.findData('dense'));tab.twod_options_widget.grading.setChecked(False)
    tab.cmb_mesh_workflow.setCurrentIndex(tab.cmb_mesh_workflow.findData(workflow));tab.trace=[];messages.clear();tab.t0=time.monotonic()
    tab._run_solver();assert tab._solve_thread is not None,messages
    mode0=tab.progress.maximum()
    while tab._job_is_active():
        app.processEvents();time.sleep(.002)
        assert time.monotonic()-tab.t0<600
    total=time.monotonic()-tab.t0;tr=tab.trace;vals=[v for _,_,v,m,_ in tr if m==100]
    first99=next((t for t,_,v,m,_ in tr if m==100 and v>=99),None);resets=sum(1 for a,b in zip(tr,tr[1:]) if b[1]<a[1])
    rec=dict(label=label,frequencies=freqs,workflow=workflow,start_maximum=mode0,seconds=total,events=len(tr),emitted_min=min(e[1] for e in tr),emitted_max=max(e[1] for e in tr),emitted_resets=resets,
        bar_monotonic=vals==sorted(vals),bar_max_before_end=max(vals) if vals else None,first_99_at_seconds=first99,first_99_fraction_of_run=(first99/total if first99 else None),
        seconds_spent_at_99=(total-first99 if first99 else 0.),final_value=tab.progress.value(),final_maximum=tab.progress.maximum(),final_format=tab.progress.format(),caption_visible=tab.lbl_progress.isVisible(),messages=list(messages),
        quality_gate=bool((tab.last_result or {}).get('metadata',{}).get('quality_gate',{}).get('passed')),
        milestones=[(round(t,3),p,v) for t,p,v,m,msg in tr[::max(1,len(tr)//40)]],distinct_messages=sorted({msg.split(':')[0][:60] for *_,msg in tr})[:25])
    print(label,{k:rec[k] for k in ('seconds','events','emitted_resets','bar_monotonic','bar_max_before_end','first_99_fraction_of_run','seconds_spent_at_99','final_value','final_format','quality_gate')},flush=True);return rec
out=[]
g=geometry('pec-0p5m-400',0.5,400)
out.append(run('one frequency, fixed mesh',g,'1'))
out.append(run('five frequencies, fixed mesh',g,'1,1.5,2,2.5,3'))
out.append(run('ten frequencies, fixed mesh',g,','.join(str(1+.25*i) for i in range(10))))
out.append(run('five frequencies, check mesh',g,'1,1.5,2,2.5,3',workflow='check'))
json.dump(out,open(sys.argv[2],'w'),indent=1)
if tab.last_result is not None:
    json.dump(tab.last_result,open(str(work/'last_result.json'),'w'),default=lambda v:v.tolist() if hasattr(v,'tolist') else list(v))
