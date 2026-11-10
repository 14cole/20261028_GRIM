import sys, time, os, cProfile, pstats, tracemalloc
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from geos import *
from ghost_backend.twod import solver as S
g = make('pec')
na = int(sys.argv[1])
ang = list(np.linspace(0, 360, na, endpoint=False))
def rss():
    with open('/proc/self/statm') as fh: return int(fh.read().split()[1])*4096
r0 = rss()
pr = cProfile.Profile(); pr.enable()
t = time.time(); r = S.solve_bistatic_rcs_2d(g, [1.5], ang, ang, geometry_units='meters'); dt = time.time()-t
pr.disable()
m = r['metadata']
print('bistatic', na, 'x', na, 'N=', m['panel_count'], 'time %.1fs' % dt, 'samples', len(r['samples']), 'rss growth MiB %.0f' % ((rss()-r0)/2**20), 'bytes/sample-pol %.0f' % ((rss()-r0)/len(r['samples'])))
print({k: round(v, 2) for k, v in m['runtime_profile']['stage_seconds'].items()})
pstats.Stats(pr).sort_stats('tottime').print_stats(14)
from ghost_backend.twod.samples import compact_samples
with compact_samples():
    r1 = rss(); t = time.time(); rc = S.solve_bistatic_rcs_2d(g, [1.5], ang, ang, geometry_units='meters'); print('compact_samples(): time %.1fs' % (time.time()-t), 'rss growth MiB %.0f' % ((rss()-r1)/2**20), type(rc['samples']).__name__)
