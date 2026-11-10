import sys, os, time
t0=time.time()
sys.path.insert(0,'..'); os.environ.setdefault('TMPDIR', os.getcwd())
from lib import *
from ghost_backend.twod import solver as S
t1=time.time(); print('import', t1-t0)
g = circle_geo(0.1, 40)
for i in range(3):
    t=time.time(); r = S.solve_monostatic_rcs_2d(g, [1.0], [0.0, 37.0], geometry_units='meters'); print('tiny default', time.time()-t)
for i in range(2):
    t=time.time(); r = S.solve_monostatic_rcs_2d(g, [1.0], [0.0, 37.0], geometry_units='meters', solver_method='auto'); print('tiny auto', time.time()-t)
m=r['metadata']; print(m.get('execution_options')); print(m.get('execution_threads')); print(m.get('solver_method'), m.get('memory_accounting',{}).get('total_checks'))
import cProfile, pstats
p=cProfile.Profile(); p.enable()
r = S.solve_monostatic_rcs_2d(g, [1.0], [0.0, 37.0], geometry_units='meters', solver_method='auto')
p.disable(); pstats.Stats(p).sort_stats('cumulative').print_stats(45)
