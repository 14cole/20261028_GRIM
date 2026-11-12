import json
from pathlib import Path
import numpy as np
from fourier_factor import SectorFourierFactor
rng=np.random.default_rng(448);records=[]
for m,q in [(3,5),(7,8)]:
 blocks=rng.normal(size=(m,q,q))+1j*rng.normal(size=(m,q,q));blocks[0]+=10*np.eye(q)
 a=np.block([[blocks[(r-c)%m] for c in range(m)] for r in range(m)])
 f=SectorFourierFactor(a,m);b=rng.normal(size=(m*q,3))+1j*rng.normal(size=(m*q,3))
 for t in [0,1,2]:
  op=a if t==0 else a.T if t==1 else a.conj().T;x=f.solve(b,t);error=np.max(abs(op@x-b))/np.max(abs(b));assert error<1e-12
  records.append(dict(sectors=m,trans=t,relative_residual=float(error)))
a[0,10]+=1e-3
try:SectorFourierFactor(a,m)
except ValueError:records.append(dict(control='asymmetric',rejected=True))
else:raise AssertionError('Asymmetric accepted')
Path(__file__).with_name('SECTOR_CONTROLS.json').write_text(json.dumps(records,indent=2)+'\n');print('Passed sector controls')
