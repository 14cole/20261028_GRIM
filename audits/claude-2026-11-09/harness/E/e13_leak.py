import sys, os, gc, time, warnings, threading
backend=sys.argv[1]; n=int(sys.argv[2])
opts=dict(mesh_strategy='global', assembly_threads=2, blas_threads=1)
if backend=='lu': opts['factorization']='dense'; os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='0'
elif backend=='hodlr': opts['factorization']='dense'; os.environ['GHOST_HIERARCHICAL_MIN_UNKNOWNS']='1'
elif backend=='tile': opts['factorization']='compressed'; os.environ['GHOST_HMATRIX_MIN_UNKNOWNS']='0'
elif backend=='hmat': opts['factorization']='compressed'; os.environ['GHOST_HMATRIX_MIN_UNKNOWNS']='1'
sys.path.insert(0,'..'); from lib import *
from ghost_backend.twod import solver as S
import psutil
p=psutil.Process()
g=snap(f"Title: t\nSegment: b 3\nproperties: 3 1 0 1 0\n{circle_rows(0.1,n)}\nIBCS_Resistances:\nDielectrics:\n1 4.0 -0.2 1 0\n")
print(backend,'start rss %.0f MB threads %d fds %d children %d'%(p.memory_info().rss/2**20,p.num_threads(),p.num_fds(),len(p.children(recursive=True))),flush=True)
for it,f in enumerate([9.0,10.0,11.0,9.5,10.5,9.0]):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        r=S.solve_monostatic_rcs_2d(g,[f],list(np.linspace(0,180,33)),geometry_units='meters',compute_condition_number=True,strict_quality_gate=False,execution_options=opts)
    del r; gc.collect()
    print(backend,'after solve',it,'f',f,'rss %.0f MB threads %d fds %d children %d tmpfiles %d'%(p.memory_info().rss/2**20,p.num_threads(),p.num_fds(),len(p.children(recursive=True)),
          len([x for x in os.listdir('/tmp') if x.startswith('ghost')])),flush=True)
# multi-frequency single call
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    r=S.solve_monostatic_rcs_2d(g,[9.0,10.0,11.0],[0.0,90.0],geometry_units='meters',strict_quality_gate=False,execution_options=opts)
del r; gc.collect()
print(backend,'after 3-freq call rss %.0f MB threads %d fds %d children %d'%(p.memory_info().rss/2**20,p.num_threads(),p.num_fds(),len(p.children(recursive=True))),flush=True)
