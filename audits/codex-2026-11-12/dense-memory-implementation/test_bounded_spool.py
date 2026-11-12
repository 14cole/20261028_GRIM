"""Targeted safety checks for the production reusable residual buffer."""
import sys,tempfile,runpy
from pathlib import Path
import numpy as np
root=sys.argv[1];sys.path.insert(0,str(Path(root)/'tools/GHOST'))
from ghost_backend.linalg.residual_spool import ResidualSpool
rng=np.random.default_rng(42);a=np.asarray(rng.normal(size=(521,521))+1j*rng.normal(size=(521,521)),complex,order='F');b=rng.normal(size=(521,7))+1j*rng.normal(size=(521,7))
results=[]
def passed(name):results.append(name);print('PASS',name)
with tempfile.TemporaryDirectory() as temp:
 spool=ResidualSpool(a,temp,lambda:None)
 assert np.allclose(spool@b,a@b,rtol=1e-12,atol=1e-12);passed('all rows, matrix RHS and partial final block')
 assert np.allclose(spool@b[:,0],a@b[:,0],rtol=1e-12,atol=1e-12);passed('vector RHS')
 assert np.array_equal(spool@b,spool@b);passed('repeated reads rewind')
 restored=np.empty_like(a);spool.restore_into(restored);assert np.array_equal(restored,a);passed('exact restoration after products')
 try:spool@b[:-1]
 except ValueError:passed('invalid shape rejects')
 else:raise AssertionError('shape')
 class ShortReads:
  def __init__(self,file):self.file=file
  def seek(self,*args):return self.file.seek(*args)
  def readinto(self,v):return self.file.readinto(v[:min(len(v),4096)])
 original=spool.file;spool.file=ShortReads(original)
 assert np.allclose(spool@b,a@b,rtol=1e-12,atol=1e-12);passed('partial readinto completes correctly')
 spool.file=original
 def cancel():raise InterruptedError('test cancellation')
 spool.checkpoint=cancel
 try:spool@b
 except InterruptedError:passed('cancellation propagated')
 else:raise AssertionError('cancellation')
 spool.checkpoint=lambda:None;spool.file.truncate(a.nbytes-16)
 try:spool@b
 except OSError:passed('truncated file rejects')
 else:raise AssertionError('truncation')
 spool.close();assert original.closed;passed('close cleans backing file')
((Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).parent)/'bounded-spool-checks.json').write_text(__import__('json').dumps(results,indent=2)+'\n')
