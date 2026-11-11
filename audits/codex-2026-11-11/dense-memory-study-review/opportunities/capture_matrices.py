"""Capture public synthetic fixtures for isolated factor research, not publication."""
import sys,json,runpy
from pathlib import Path
import numpy as np
root,profiler,spec=sys.argv[1:4];s=json.loads(spec)
sys.path.insert(0,str(Path(root)/'tools/GHOST'))
from ghost_backend.linalg.dense import DenseFactor
old=DenseFactor.__init__;oldsolve=DenseFactor.solve;records=[]
def init(self,a,*args,**kwargs):
 index=len(records);prefix=Path(s['capture_directory'])/(s['case']+'-'+str(index))
 with open(str(prefix)+'-matrix.raw','wb') as file:
  for start in range(0,len(a),64):file.write(np.ascontiguousarray(a[start:start+64]).tobytes())
 Path(str(prefix)+'-info.json').write_text(json.dumps(dict(n=len(a))))
 norm=float(np.max(abs(a)));asym=herm=0.
 for start in range(0,len(a),64):
  b=a[start:start+64];at=a[:,start:start+64].T
  asym=max(asym,float(np.max(abs(b-at))));herm=max(herm,float(np.max(abs(b-at.conj()))))
 record=dict(case=s['case'],index=index,n=len(a),matrix_bytes=a.nbytes,transpose_asymmetry=asym/norm,hermitian_asymmetry=herm/norm,prefix=str(prefix),label=kwargs.get('label',str(args[1]) if len(args)>1 else ''))
 records.append(record);self._research_prefix=str(prefix)
 return old(self,a,*args,**kwargs)
def solve(self,b):
 if not Path(self._research_prefix+'-rhs.npy').exists():np.save(self._research_prefix+'-rhs.npy',b)
 return oldsolve(self,b)
DenseFactor.__init__=init;DenseFactor.solve=solve
sys.argv=[profiler,root,spec];runpy.run_path(profiler,run_name='__main__')
Path(s['capture_directory'],s['case']+'-capture.json').write_text(json.dumps(records,indent=2)+'\n')
