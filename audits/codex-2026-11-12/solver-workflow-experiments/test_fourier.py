import json
from pathlib import Path
import numpy as np
from scipy.linalg import circulant
from fourier_factor import FourierFactor
rng=np.random.default_rng(43);records=[]
for p in [1,2,3]:
 m=31;a=np.block([[circulant(rng.normal(size=m)+1j*rng.normal(size=m)) for c in range(p)] for r in range(p)])+20*np.eye(m*p)
 f=FourierFactor(a,p);b=rng.normal(size=(m*p,4))+1j*rng.normal(size=(m*p,4))
 for t in [0,1,2]:
  op=a if t==0 else a.T if t==1 else a.conj().T;x=f.solve(b,t);error=np.max(abs(op@x-b))/np.max(abs(b));assert error<1e-12
  records.append(dict(parts=p,trans=t,relative_residual=float(error)))
a[0,5]+=1e-3
try:FourierFactor(a,p)
except ValueError:records.append(dict(control='broken_symmetry',rejected=True))
else:raise AssertionError('Asymmetry accepted')
Path(__file__).with_name('FOURIER_CONTROLS.json').write_text(json.dumps(records,indent=2)+'\n');print('Passed',len(records),'Fourier controls')
