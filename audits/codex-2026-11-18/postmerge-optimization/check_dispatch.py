"""Assert the final layout path is restricted to F matrices and <=16 RHS."""
import sys,pathlib,json,numpy as np
sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.execution.options import execution_scope
records=[];rng=np.random.default_rng(611)
with execution_scope(dict(factorization='dense',dense_residual_storage='memory',blas_threads=1,ram_budget_gib=4)):
 for order in ('C','F'):
  a=np.array(np.eye(32)*32+rng.normal(size=(32,32))+1j*rng.normal(size=(32,32)),order=order)
  factor=DenseFactor(a)
  for width in (1,16,17,180):
   rhs=rng.normal(size=(32,width))+1j*rng.normal(size=(32,width));saved=np.matmul;calls=[]
   def observe(*args,**kwargs):
    calls.append(dict(shape=kwargs['out'].shape,fortran=bool(kwargs['out'].flags.f_contiguous)))
    return saved(*args,**kwargs)
   try:np.matmul=observe;answer=factor.solve(rhs)
   finally:np.matmul=saved
   assert bool(calls)==(order=='F' and width<=16),(order,width,calls)
   assert all(x['fortran'] for x in calls)
   assert np.linalg.norm(a@answer-rhs)/np.linalg.norm(rhs)<1e-12
   records.append(dict(order=order,width=width,direct_output_calls=len(calls)))
  factor.close()
pathlib.Path(sys.argv[2]).write_text(json.dumps(records,indent=2));print('PASS 8 dispatch boundary checks')
