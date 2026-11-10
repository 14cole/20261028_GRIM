import sys, os, time
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
from ghost_backend.twod import solver as S
from ghost_backend.execution.options import automatic_run, execution_scope
from ghost_backend.execution.fresh_sweep import run_fresh
from ghost_backend.execution.recovery import RecoveryRun
from ghost_backend.twod.samples import compact_samples
prof=automatic_run('monostatic'); opts=prof['execution_options']
g=circle_geo(0.1,300)
freqs=[1.0,1.01]
kw=dict(geometry_snapshot=g,frequencies_ghz=freqs,elevations_deg=list(np.linspace(0,360,721)),geometry_units='meters',solver_method=prof['solver_method'],max_panels=100000)
for rec in (False,True):
    recovery=RecoveryRun.create(os.path.join(os.getcwd(),'recov'),kw,opts,'double',False) if rec else None
    c=time.process_time(); t=time.time()
    with execution_scope(opts, limit_blas=True), compact_samples():
        r=run_fresh(S.solve_monostatic_rcs_2d_survey, kw, opts, 'double', False, frequency_workers=1, recovery=recovery)
    print('recovery' if rec else 'in-memory','cpu',round(time.process_time()-c,2),'wall',round(time.time()-t,2),'N',r['metadata'].get('frequency_metadata',[{}])[0].get('metadata',{}).get('dense_largest_system'))
    if rec:
        d=recovery.directory; print('run folder bytes', sum(p.stat().st_size for p in d.rglob('*') if p.is_file()), [ (p.name,p.stat().st_size) for p in sorted((d/'inputs').iterdir())])
        import cProfile,pstats
        res=recovery.load(freqs[0]); p=cProfile.Profile(); p.enable(); recovery.save(freqs[0],res); p.disable()
        st=pstats.Stats(p); st.sort_stats('cumulative').print_stats(14)
