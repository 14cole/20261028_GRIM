"""Kill one frequency worker mid-sweep (simulates the Linux OOM killer): does the sweep recover like it does for MemoryError?"""
import sys, os, time, threading, signal
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
import psutil
if __name__=='__main__':
    from ghost_backend.twod import solver as S
    from ghost_backend.execution.options import automatic_run, execution_scope
    from ghost_backend.execution.fresh_sweep import run_fresh
    prof=automatic_run('monostatic'); opts=prof['execution_options']
    g=circle_geo(0.5,256,props='2 0 0 0 0'); freqs=[6.0,6.06,6.12,6.18]
    kw=dict(geometry_snapshot=g,frequencies_ghz=freqs,elevations_deg=list(np.linspace(0,180,19)),geometry_units='meters',solver_method=prof['solver_method'],max_panels=100000)
    me=psutil.Process(); killed=[]
    def killer():
        while not killed:
          try:
            kids=[c for c in me.children(recursive=True) if 'multiprocessing' in ' '.join(c.cmdline()) and 'spawn_main' in ' '.join(c.cmdline())]
            busy=[c for c in kids if c.cpu_times().user>2.5]   # imported and computing
            if busy:
                os.kill(busy[0].pid, signal.SIGKILL); killed.append(busy[0].pid); print('killed worker',busy[0].pid,flush=True)
          except Exception: pass
          time.sleep(0.1)
    threading.Thread(target=killer,daemon=True).start()
    t=time.time()
    try:
        with execution_scope(opts, limit_blas=True):
            r=run_fresh(S.solve_monostatic_rcs_2d_survey, kw, opts, 'double', False, frequency_workers=2)
        print('RESULT ok', r['metadata']['frequency_execution'], 'samples', len(r['samples']), 'wall', round(time.time()-t,1))
    except BaseException as e:
        print('RESULT sweep failed:', type(e).__name__, str(e)[:300], 'wall', round(time.time()-t,1))
