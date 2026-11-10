import sys, os, time, json
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
from ghost_backend.execution.options import automatic_run, execution_scope, blas_core_budget
from ghost_backend.execution import frequency_sweep as FS
from ghost_backend.twod.preparation import preparation_scope
from ghost_backend.twod.solver import _solve_memory_limit_gb
prof=automatic_run('monostatic'); opts=prof['execution_options']
for a,f0 in ((0.5,6),(1.0,6),(1.0,12),(2.0,12),(4.0,12)):
    g=circle_geo(a,256,props='2 0 0 0 0')
    freqs=[round(f0*(1+0.01*i),4) for i in range(8)]
    kw=dict(geometry_snapshot=g,frequencies_ghz=freqs,elevations_deg=list(np.linspace(0,180,181)),geometry_units='meters',solver_method='auto',max_panels=100000)
    with execution_scope(opts), preparation_scope():
        t=time.time(); budget=_solve_memory_limit_gb()
        recs=FS._plan(kw, opts, False, freqs, 2, budget-1.0, blas_core_budget())
        dt=time.time()-t
    print(a,f0,'plan_s',round(dt,2),'budget',round(budget,2),[(r['frequency'],round(r['cost'],2),round(r['memory_gib'],2),r['cpus']) for r in recs[:2]], 'sumcost',round(sum(r['cost'] for r in recs),2), 'parallel_auto', sum(r['cost'] for r in recs)>=FS.AUTO_MIN_COST)
