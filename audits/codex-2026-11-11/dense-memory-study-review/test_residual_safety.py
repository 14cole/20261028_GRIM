"""Full residuals, precision, I/O failure, cancellation and ownership eligibility."""
import sys,tempfile,json,os,gc
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.linalg.residual_spool import ResidualSpool,selected
from ghost_backend.linalg.dense import DenseFactor
from ghost_backend.execution.options import execution_scope
from ghost_backend.linalg import residual_spool as RS
results=[]
def check(name,ok,**details):
 assert ok,(name,details)
 results.append(dict(name=name,**details));print('PASS',name,flush=True)
rng=np.random.default_rng(143);n=513
a=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n));a+=n*np.eye(n)
a=np.array(a,order='F');b=rng.normal(size=(n,7))+1j*rng.normal(size=(n,7))
with tempfile.TemporaryDirectory() as directory:
 opts=dict(factorization='dense',dense_residual_storage='disk',assembly_threads=1,blas_threads=1,temporary_directory=directory)
 with execution_scope(opts,limit_blas=True):
  diagnostics={};factor=DenseFactor(a.copy(order='F'),owned_matrix=True,diagnostics=diagnostics)
  x=factor.solve(b);spool=factor._residual_spool
  check('owned double dense uses disk and every row',spool is not None and factor.event['residual_rows']=='all')
  residual=float(np.linalg.norm(a@x-b)/np.linalg.norm(b));check('disk solution full residual',residual<1e-12,error=residual)
  check('condition estimation preserved',np.isfinite(diagnostics['condition_est']),condition=diagnostics['condition_est'])
  restored=np.empty_like(a);spool.restore_into(restored);check('exact original restoration',np.array_equal(restored,a))
  factor.close();check('spool closes on explicit close',spool.file.closed)
  check('temporary directory clean',not list(Path(directory).iterdir()))
  check('unowned matrix is ineligible',not selected(a,False,'dense'))
  check('C-order matrix is ineligible',not selected(a.copy(order='C'),True,'dense'))
  check('matrix view is ineligible',not selected(a[:],True,'dense'))
  check('hierarchical factor mode is ineligible',not selected(a,True,'hierarchical'))
  calls=[];original=RS.tempfile.TemporaryFile
  def tracked(*args,**kwargs):
   f=original(*args,**kwargs);calls.append(f);return f
  with patch.object(RS.tempfile,'TemporaryFile',tracked),patch.object(ResidualSpool,'block_bytes',16*n*256):
   count=[0]
   def abort():
    count[0]+=1
    if count[0]>=2:raise InterruptedError('injected cancellation')
   try:ResidualSpool(a,directory,abort)
   except InterruptedError:pass
   else:raise AssertionError('not cancelled')
  check('cancelled write closes file',calls and all(f.closed for f in calls))
  with patch.object(RS.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
   try:DenseFactor(a.copy(order='F'),owned_matrix=True)
   except OSError:pass
   else:raise AssertionError('disk failure ignored')
  check('explicit disk refuses insufficient space',True)
  failed_files=[]
  class FailWrite:
   def __init__(self,f):self.wrapped=f;self.count=0
   def write(self,data):
    self.count+=1
    if self.count==2:raise OSError('injected full disk during write')
    return self.wrapped.write(data)
   def __getattr__(self,name):return getattr(self.wrapped,name)
  def failfile(*args,**kwargs):
   f=FailWrite(original(*args,**kwargs));failed_files.append(f);return f
  with patch.object(RS.tempfile,'TemporaryFile',failfile),patch.object(ResidualSpool,'block_bytes',16*n*256):
   try:ResidualSpool(a,directory,lambda:None)
   except OSError:pass
   else:raise AssertionError('write failure ignored')
  check('mid-write disk failure closes file',failed_files and all(f.closed for f in failed_files))
  from ghost_backend.twod import solver as S
  failed_lu=[]
  def lufile(*args,**kwargs):
   f=original(*args,**kwargs);failed_lu.append(f);return f
  with patch.object(RS.tempfile,'TemporaryFile',lufile),patch.object(S._SCIPY_LINALG,'lu_factor',side_effect=np.linalg.LinAlgError('injected LU failure')):
   try:DenseFactor(a.copy(order='F'),owned_matrix=True)
   except np.linalg.LinAlgError:pass
   else:raise AssertionError('LU failure ignored')
  check('LU failure closes original-matrix spool',failed_lu and all(f.closed for f in failed_lu))
  with execution_scope(dict(opts,dense_residual_storage='auto')):
   with patch.object(RS,'auto_spooled',return_value=True),patch.object(RS.shutil,'disk_usage',return_value=SimpleNamespace(free=0)),patch.object(RS,'copy_fits',return_value=False):
    try:DenseFactor(a.copy(order='F'),owned_matrix=True)
    except MemoryError:pass
    else:raise AssertionError('auto bypassed RAM gate')
   check('automatic disk failure cannot bypass RAM gate',True)
  s=ResidualSpool(a,directory,lambda:None);s.file.truncate(16)
  try:s@b
  except OSError:pass
  else:raise AssertionError('truncation ignored')
  s.close();check('truncated residual file rejected',True)
  x=np.linalg.solve(a,b)
  low=a.astype(np.complex64).astype(np.complex128)
  floor=float(np.max(abs(low@x-b))/(np.linalg.norm(a,np.inf)*np.max(abs(x))+np.max(abs(b))))
  check('single precision residual copy misses double gate',floor>1e-12,backward_error=floor)
((Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).parent)/'residual-safety-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(len(results),'passed')
