"""Declared coverage, sequential fresh processes, bounded wall time/RSS watchdog.

Imported by experiments.py and followups.py; their catalogs define this study.
Existing results are skipped.
Delete a case's result files explicitly before an intentional rerun.
"""
import json,os,signal,subprocess,sys,time
from pathlib import Path
import psutil
P=Path(__file__).resolve().parent

def run(root,spec):
    spec=dict(spec,out=str(P/'results'/spec['case']))
    out=Path(spec['out'])
    if Path(str(out)+'.json').exists():return
    env={k:v for k,v in os.environ.items() if not k.startswith('GHOST_')}
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    env.update(spec.get('env',{}))
    started=time.monotonic();peak=0;peak_parent=0;max_children=0;reason=None;seen_children={}
    with open(str(out)+'.stdout','w') as stdout,open(str(out)+'.stderr','w') as stderr:
        child=subprocess.Popen([sys.executable,str(P/'run_case.py'),str(root),json.dumps(spec)],
            stdout=stdout,stderr=stderr,env=env,start_new_session=True)
        p=psutil.Process(child.pid);timeline=[];next_message=started+45
        while child.poll() is None:
            now=time.monotonic()
            try:
                children=p.children(recursive=True);rss=p.memory_info().rss;tree=rss
                for c in children:
                    if c.pid not in seen_children:
                        try:seen_children[c.pid]=dict(pid=c.pid,first_seconds=now-started,name=c.name(),command=c.cmdline())
                        except psutil.Error:seen_children[c.pid]=dict(pid=c.pid,first_seconds=now-started,unavailable=True)
                    try:tree+=c.memory_info().rss
                    except psutil.Error:pass
                peak=max(peak,tree);peak_parent=max(peak_parent,rss);max_children=max(max_children,len(children))
                timeline.append((now-started,rss,tree,len(children)))
                if tree>10*1024**3:reason='watchdog_process_tree_rss_10GiB'
            except psutil.Error:pass
            if now-started>spec.get('timeout',180):reason='watchdog_wall_timeout'
            if reason:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            if now>=next_message:
                print('RUNNING',spec['case'],round(now-started),round(peak/1024**3,3),flush=True);next_message=now+45
            time.sleep(.2)
    monitor=dict(wall=time.monotonic()-started,peak_tree_rss_gib=peak/1024**3,
        peak_parent_rss_gib=peak_parent/1024**3,max_children=max_children,children_seen=list(seen_children.values()),termination=reason,returncode=child.returncode)
    Path(str(out)+'.monitor.json').write_text(json.dumps(monitor,indent=2)+'\n')
    import numpy as np
    np.savez_compressed(str(out)+'.timeline.npz',timeline=np.array(timeline))
    if not Path(str(out)+'.json').exists():
        Path(str(out)+'.json').write_text(json.dumps(dict(spec=spec,error=reason or 'process_exit_without_summary',
            wall_seconds=monitor['wall'],monitor=monitor),indent=2)+'\n')
    d=json.loads(Path(str(out)+'.json').read_text())
    print('DONE',spec['case'],round(d['wall_seconds'],2),'treeGiB',round(monitor['peak_tree_rss_gib'],3),
        'N',d.get('actual_unknowns'),d['error'],flush=True)

