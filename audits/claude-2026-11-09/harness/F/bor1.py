import sys, os, time
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
t0=time.time()
from lib import *
from ghost_backend.bor import dispatch as D
print('import',round(time.time()-t0,2))
g=bor_sphere(0.1,40)
for i in range(3):
    c=time.process_time(); t=time.time(); r=D.solve_monostatic_rcs_bor(g,[1.0],[0.0,60.0],geometry_units='meters'); print('tiny bor wall',round(time.time()-t,3),'cpu',round(time.process_time()-c,3))
m=r['metadata']; print({k:m[k] for k in m if k in ('workers','n_modes','modes_used','assembly','n_unknowns','bor_execution_options')})
print(sorted(m.keys())[:80])
import cProfile, pstats
p=cProfile.Profile(); p.enable(); r=D.solve_monostatic_rcs_bor(g,[1.0],[0.0,60.0],geometry_units='meters'); p.disable()
pstats.Stats(p).sort_stats('cumulative').print_stats(40)
