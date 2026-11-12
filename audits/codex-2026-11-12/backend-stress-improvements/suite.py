"""Declared coverage, sequential fresh processes, bounded wall time/RSS watchdog.

Usage: python suite.py ROOT [group-or-case ...]. Existing results are skipped.
Delete a case's result files explicitly before an intentional rerun.
"""
import json,os,signal,subprocess,sys,time
from pathlib import Path
import psutil
from geometry_cases import C0
P=Path(__file__).resolve().parent

def catalog():
    cases=[]
    def pair(name,group='control',**kw):
        for backend in ('dense','compressed'):
            row=dict(case=name+'-'+backend,geometry_id=name,group=group,backend=backend,
                material='pec',shape='circle',length_m=.1,frequency_ghz=2.)
            row.update(kw);cases.append(row)
    pair('small-pec');pair('small-dielectric',material='diel')
    pair('small-coated',material='coated');pair('small-thin-coated',material='coated',inner_ratio=.99)
    pair('small-high-eps',material='diel',eps=[16.,-.01])
    pair('small-multilayer',material='multilayer')
    pair('small-star-pec',shape='star',length_m=.3,frequency_ghz=3.)
    pair('small-star-coated',shape='star',material='coated',length_m=.3,frequency_ghz=3.,inner_ratio=.93)
    pair('small-cavity',shape='cavity',length_m=.5,frequency_ghz=2.)
    pair('small-comb',shape='comb',length_m=.5,frequency_ghz=2.,teeth=16)
    # Electrical-size ladder at fixed 20-foot diameter and ~20 samples per
    # shortest-medium wavelength. n sets the actual circle endpoints.
    for material,counts in [('pec',[2000,8000,16000,24000]),('diel',[1000,4000,8000,12000]),('coated',[1000,3000,6000])]:
        for n in counts:
            index=1. if material=='pec' else abs(complex(4,-.2))**.5
            f=n*C0/(20*3.141592653589793*6.096*index)/1e9
            pair(f'ladder-{material}-{n}','scaling',material=material,n=n,length_m=6.096,
                frequency_ghz=f,timeout=240)
    # User's physical envelope. Every limit/refusal remains part of the suite.
    for f in (2.,10.,15.,18.):
        for material in ('pec','diel','coated'):
            pair(f'20ft-{material}-{f:g}GHz','physical',material=material,length_m=6.096,
                frequency_ghz=f,timeout=240)
    # Geometric and material stresses at dimensions that permit direct comparisons.
    pair('large-star-coated','geometry',shape='star',material='coated',length_m=2.,frequency_ghz=2.,inner_ratio=.98)
    pair('large-ellipse-dielectric','geometry',shape='ellipse',material='diel',length_m=6.096,frequency_ghz=2.,aspect=.03)
    pair('large-cavity','geometry',shape='cavity',length_m=6.096,frequency_ghz=2.)
    pair('large-comb','geometry',shape='comb',length_m=2.,frequency_ghz=2.,teeth=24)
    pair('large-multilayer','geometry',material='multilayer',length_m=1.,frequency_ghz=2.)
    for label,eps in [('lossless',[4.,0.]),('moderate-loss',[4.,-.2]),('high-loss',[4.,-4.])]:
        pair('material-'+label,'geometry',material='diel',n=4200,length_m=6.096,frequency_ghz=1.5,eps=eps)
    # Accuracy/representation controls, not claimed as large-model qualification.
    for material in ('pec','diel','coated'):
        pair('certified-'+material,'accuracy',material=material,certified=True,length_m=.3,frequency_ghz=2.,timeout=240)
    pair('certified-cavity','accuracy',shape='cavity',certified=True,mesh_strategy='adaptive',length_m=.5,frequency_ghz=2.,timeout=240)
    for degree in (2,3):
        pair('polynomial-'+str(degree),'accuracy',material='coated',length_m=.3,frequency_ghz=2.,degree=degree)
    pair('fallback-small','accuracy',material='diel',length_m=.3,frequency_ghz=2.,fallback=True)
    for cap in (.5,1.,2.):
        pair('pressure-'+str(cap),'pressure',material='diel',n=4000,length_m=6.096,frequency_ghz=1.5,cap=cap)
    return cases

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

if __name__=='__main__':
    (P/'results').mkdir(exist_ok=True);(P/'geometries').mkdir(exist_ok=True)
    root=Path(sys.argv[1]).resolve();cases=catalog()
    (P/'catalog.json').write_text(json.dumps(cases,indent=2)+'\n')
    for spec in cases:
        if len(sys.argv)>2 and spec['group'] not in sys.argv[2:] and spec['case'] not in sys.argv[2:]:continue
        run(root,spec)
