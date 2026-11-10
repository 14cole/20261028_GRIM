import sys, os, time, gc, tempfile
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, scipy.linalg as la
from ghost_backend.linalg.residual_spool import ResidualSpool
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.execution.options import execution_scope, validate_options, DEFAULTS
import psutil
proc=psutil.Process()
def nfd(): return proc.num_fds()
rng=np.random.default_rng(0)
n=1500
A=np.asfortranarray(rng.standard_normal((n,n))+1j*rng.standard_normal((n,n))+30*np.eye(n))
A0=A.copy()
d=tempfile.mkdtemp(dir='.')
# 1 round trip
f0=nfd()
sp=ResidualSpool(A,d,lambda:None)
lu,piv=la.lu_factor(A,overwrite_a=True,check_finite=False)
print('lu in place:',lu is A or np.shares_memory(lu,A), 'A destroyed:', not np.array_equal(A,A0))
x=rng.standard_normal((n,3))+0j
print('matmul rel err', np.abs(sp@x-A0@x).max()/np.abs(A0@x).max(), 'vector', np.abs(sp@x[:,0]-A0@x[:,0]).max())
sp.restore_into(A); print('restore bit-exact:', np.array_equal(A,A0))
sp.close(); print('fds after close', nfd()-f0, 'files left', os.listdir(d))
# 2 exception during write
calls=[0]
def cp():
    calls[0]+=1
    if calls[0]==3: raise KeyboardInterrupt('abort')
A=A0.copy(order='F')
try: ResidualSpool(A,d,cp)
except KeyboardInterrupt: print('abort during write: fds', nfd()-f0, 'files', os.listdir(d))
# 3 write failure (disk full simulated)
import builtins
class Boom:
    def __init__(s,f): s.f=f; s.n=0
    def write(s,b):
        s.n+=1
        if s.n==2: raise OSError(28,'No space left on device')
        return s.f.write(b)
    def __getattr__(s,k): return getattr(s.f,k)
orig=tempfile.TemporaryFile
tempfile.TemporaryFile=lambda **k: Boom(orig(**k))
try: ResidualSpool(A,d,lambda:None)
except OSError as e: print('ENOSPC ->',repr(e),'fds',nfd()-f0)
tempfile.TemporaryFile=orig
# 4 DenseFactor with disk policy
for policy in ('disk','memory'):
  for order in ('F','C'):
    A=np.array(A0,order=order)
    with execution_scope(dict(DEFAULTS,dense_residual_storage=policy)):
        diag={}
        ev=[]
        fac=DenseFactor(A,diag,'t',evidence=ev,owned_matrix=True)
        b=rng.standard_normal((n,5))+1j*rng.standard_normal((n,5))
        xs=fac.solve(b)
        print(policy,order,'storage',fac.event.get('residual_storage'),'spooled', fac._residual_spool is not None,'be',fac.event['max_backward_error'],
              'err', np.abs(A0@xs-b).max(), 'cond_est',diag.get('condition_est'),diag.get('condition_method'), 'A intact', np.array_equal(A,A0))
        fac.restore_original(); print('   after restore A intact', np.array_equal(A,A0))
        if fac._residual_spool is not None:
            # use after restore -> LU destroyed?
            try:
                x2=fac.solve(b); print('   solve after restore: err',np.abs(A0@x2-b).max())
            except Exception as e: print('   solve after restore raised', type(e).__name__, str(e)[:120])
        fac.close()
print('final fds', nfd()-f0, os.listdir(d))
# exact cond for comparison
r=np.abs(A0).max(1); B=A0/r[:,None]; c=np.abs(B).max(0); B=B/c
print('exact equilibrated cond1', np.linalg.cond(B,1))
