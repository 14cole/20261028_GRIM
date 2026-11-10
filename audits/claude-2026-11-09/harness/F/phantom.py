"""Frequency-sweep planner prices tile-worker processes that frequency workers never start (GHOST_TILE_PROCESSES=0 is set only inside workers)."""
import sys, os, json
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
from ghost_backend.execution.options import automatic_run, execution_scope, blas_core_budget
from ghost_backend.execution import frequency_sweep as FS
from ghost_backend.twod.preparation import preparation_scope
opts=automatic_run('monostatic')['execution_options']
g=circle_geo(1.0,256,props='2 0 0 0 0'); freqs=[12.0,12.1]
kw=dict(geometry_snapshot=g,frequencies_ghz=freqs,elevations_deg=list(np.linspace(0,180,181)),geometry_units='meters',solver_method='auto',max_panels=100000)
for env in (None,'0'):
    if env is None: os.environ.pop('GHOST_TILE_PROCESSES',None)
    else: os.environ['GHOST_TILE_PROCESSES']=env
    with execution_scope(opts), preparation_scope():
        recs=FS._plan(kw, opts, False, freqs, 2, 8.0, blas_core_budget())
    r=recs[0]; print('parent GHOST_TILE_PROCESSES=',env,'-> worker reservation GiB',round(r['memory_gib'],3),'cpus',r['cpus'])
