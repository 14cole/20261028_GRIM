from dlib import *
import copy, threading, glob, os, tempfile, sys
a=0.1; n=40; asp=[0,60,120]
which=sys.argv[1]
base=os.path.abspath('mats')
if which=='csv':
    g=geo([('b',2,'2 1 40 0 0',arc_rows(a,n))],ibc='40 zs.csv')
    fs=[1.1,0.85,1.0,1.2,0.8]
    r=run(g,fs,asp,material_base_dir=base)
    def zs_of(f): return np.interp(f,[0.8,1.0,1.2],[50,120,300])+1j*np.interp(f,[0.8,1.0,1.2],[-40,10,80])
    for f in fs:
        vv=np.array([s['rcs_linear'] for s in r['co_solved_samples']['VV'] if s['frequency_ghz']==f]); ex=SP.sigma_impedance_sphere(a,f*1e9,zs_of(f))
        r1=run(g,f,asp,material_base_dir=base); v1=chan(r1,'VV')[0]
        print(f'IBC csv f={f} multi-call err vs Mie(Zs interp)={np.max(np.abs(db(vv)-db(ex))):.4f} dB; single-call vs multi {np.max(np.abs(db(v1)-db(vv))):.2e}',flush=True)
    g=geo([('b',3,'3 1 0 50 0',arc_rows(a,n))],diel='50 eps.csv')
    fs=[1.2,0.8,1.0]
    r=run(g,fs,asp,material_base_dir=base)
    for f in fs:
        e=np.interp(f,[0.8,1.0,1.2],[2,4,6])+1j*np.interp(f,[0.8,1.0,1.2],[-0.1,-0.5,-1.0]); m=np.interp(f,[0.8,1.0,1.2],[1,1.2,1.5])+1j*np.interp(f,[0.8,1.0,1.2],[0,-0.1,-0.3])
        vv=np.array([s['rcs_linear'] for s in r['co_solved_samples']['VV'] if s['frequency_ghz']==f]); ex=SP.sigma_dielectric_sphere(a,e,m,f*1e9)
        print(f'diel csv f={f} err vs Mie={np.max(np.abs(db(vv)-db(ex))):.4f} dB',flush=True)
    try:
        run(g,[0.7],asp,material_base_dir=base); print('extrapolation NOT rejected')
    except Exception as e: print('extrapolation rejected:',type(e).__name__,str(e)[:120])
if which=='mut':
    g=sphere(a,n,'ibc',zs=100+50j); g0=copy.deepcopy(g)
    fl=[3.0,1.0]; al=[90,0,30]; fl0=list(fl); al0=list(al)
    r=run(g,fl,al); print('snapshot mutated by solve:', g!=g0, 'freq list mutated', fl!=fl0, 'aspects mutated', al!=al0)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        e=D.estimate_bor_resources(g,1.0,al,geometry_units='meters'); print('snapshot mutated by estimate:', g!=g0)
        r=D.solve_monostatic_rcs_bor_certified(g,[1.0],al,geometry_units='meters',workers=2); print('snapshot mutated by certified:', g!=g0, [k for k in g if k not in g0])
        r=D.solve_monostatic_rcs_bor_survey(g,[1.0],al,geometry_units='meters',workers=2); print('survey ok', r['metadata']['survey_mode'], 'mutated', g!=g0)
    # duplicates
    try:
        r=run(g,[1.0,1.0],[30,30,60]); print('duplicates plain: n samples VV', len(r['co_solved_samples']['VV']))
    except Exception as e: print('duplicates plain FAIL',type(e).__name__,str(e)[:200])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            r=D.solve_monostatic_rcs_bor_certified(g,[1.0],[30,30,60],geometry_units='meters',workers=2); print('duplicates certified ok')
    except Exception as e: print('duplicate aspects certified FAIL',type(e).__name__,str(e)[:200])
if which=='abort':
    P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
    g=geo([('b',2,'2 0 0 0 0',rows(P))])
    ev=threading.Event(); t0=time.time(); seen=[]
    def cb(i,ntot,msg):
        seen.append((time.time()-t0,msg))
        if len(seen)>=3: ev.set()
    nthr0=threading.active_count()
    tmp=tempfile.gettempdir(); before=set(os.listdir(tmp))
    threading.Timer(4.0, ev.set).start()
    try:
        r=run(g,[6.0,7.0],list(range(0,181,5)),abort_event=ev,progress_callback=cb); print('NOT aborted')
    except BaseException as e: print('abort ->',type(e).__name__,str(e)[:100],'after',round(time.time()-t0,1),'s; progress events',len(seen), seen[:4])
    time.sleep(3)
    print('threads before/after', nthr0, threading.active_count(), [t.name for t in threading.enumerate()][:10])
    print('new temp entries', sorted(set(os.listdir(tmp))-before)[:10])
    import multiprocessing; print('child procs', [p.name for p in multiprocessing.active_children()])
    # solve again after abort works?
    r=run(g,[1.0],[0,90]); print('solve after abort ok', np.round(db(chan(r,'VV')[0]),3))
