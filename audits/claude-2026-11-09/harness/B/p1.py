import sys, time, cProfile, pstats
from geos import *
from ghost_backend.twod import solver as S
name, method = sys.argv[1], sys.argv[2]
g = make(name)
pr = cProfile.Profile(); pr.enable()
t = time.time(); r = S.solve_monostatic_rcs_2d(g, [1.5], [0.0, 35.0], geometry_units='meters', solver_method=method); dt = time.time()-t
pr.disable()
print('time', dt, 'panels', r['metadata']['panel_count'])
print(r['metadata'].get('runtime_profile', {}).get('stage_seconds'))
pstats.Stats(pr).sort_stats('cumulative').print_stats(45)
