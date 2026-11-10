"""Cost of the availability probe with and without SLURM variables; number of probes per compressed solve."""
import sys, os, time
sys.path.insert(0,'..'); os.environ['TMPDIR']=os.path.join(os.getcwd(),'tmp')
if len(sys.argv)>1 and sys.argv[1]=='slurm':
    os.environ.update(SLURM_JOB_ID='123', SLURM_MEM_PER_NODE='12000', SLURM_CPUS_PER_TASK='4')
from lib import *
import psutil
from ghost_backend.twod import solver as S
n=200; t=time.perf_counter(); c=time.process_time()
for _ in range(n): S._detect_available_gb()
print('env', sys.argv[1:], 'pids on host', len(psutil.pids()), 'probe ms wall', round(1e3*(time.perf_counter()-t)/n,3), 'cpu ms', round(1e3*(time.process_time()-c)/n,3))
calls=[0]; spent=[0.]; orig=S._detect_available_gb
def counted():
    a=time.process_time(); 
    try: return orig()
    finally: calls[0]+=1; spent[0]+=time.process_time()-a
S._detect_available_gb=counted
g=circle_geo(0.5,256,props='2 0 0 0 0')
c=time.process_time(); t=time.perf_counter()
r=S.solve_monostatic_rcs_2d(g,[6.0],list(np.linspace(0,180,181)),geometry_units='meters',solver_method='auto',execution_options=dict(factorization='compressed',mesh_strategy='global',assembly_threads=1,blas_threads=1))
print('solve cpu', round(time.process_time()-c,2),'wall',round(time.perf_counter()-t,2),'probe calls',calls[0],'probe cpu s',round(spent[0],3),'checks',r['metadata']['memory_accounting']['total_checks'])
