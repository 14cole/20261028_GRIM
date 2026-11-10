"""Default automatic profile on small problems just below/above the 256-unknown BLAS-thread threshold."""
import sys, os, time, json
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
from lib import *
from ghost_backend.twod import solver as S
from ghost_backend.execution.options import automatic_run
prof=automatic_run('monostatic')
for n in (240,300):
    g=circle_geo(0.1,n)
    for bt in ('auto',1):
        o=dict(prof['execution_options'],blas_threads=bt)
        c0=os.times(); t=time.time()
        r=S.solve_monostatic_rcs_2d(g,[1.0],list(np.linspace(0,360,721)),geometry_units='meters',solver_method='auto',execution_options=o)
        c1=os.times(); m=r['metadata']
        st=sorted(m['runtime_profile']['stage_seconds'].items(),key=lambda kv:-kv[1])[:4]
        print('N',m.get('dense_largest_system'),'blas',bt,'method',m.get('solver_method'),'wall',round(time.time()-t,2),'cpu',round(sum(c1[i]-c0[i] for i in range(4)),2),'la',[(e['matrix_size'],e['requested_threads']) for e in m.get('linear_algebra_execution',[])][:3],[(k,round(v,2)) for k,v in st])
