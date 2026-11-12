import json
from pathlib import Path
import numpy as np,scipy.linalg as la
from schur_factor import SchurFactor
rng=np.random.default_rng(332);n=35;a=rng.normal(size=(2*n,2*n))+1j*rng.normal(size=(2*n,2*n));a+=5*n*np.eye(2*n);b=rng.normal(size=(2*n,3))+1j*rng.normal(size=(2*n,3));cache={};records=[]
for i in range(2):
 if i:a[n:,n:]*=3.-.2j
 f=SchurFactor(a,cache);assert f.reused==bool(i)
 for t in [0,1,2]:
  op=a if t==0 else a.T if t==1 else a.conj().T;x=f.solve(b,t);error=np.max(abs(op@x-b))/np.max(abs(b));assert error<1e-12
  records.append(dict(polarization_step=i,trans=t,reused=f.reused,relative_residual=float(error)))
a[0,0]+=1;f=SchurFactor(a,cache);assert not f.reused;records.append(dict(control='changed_common_block',reused=False))
# An invertible system can have a singular leading block; the prototype must refuse.
a=np.block([[np.zeros((4,4)),np.eye(4)],[np.eye(4),np.eye(4)]]).astype(complex)
assert np.linalg.matrix_rank(a)==8
try:SchurFactor(a,{})
except la.LinAlgWarning:records.append(dict(control='invertible_but_singular_leading_block',rejected=True,needs_full_lu_fallback=True))
else:raise AssertionError('Expected block factor refusal')
Path(__file__).with_name('SCHUR_CONTROLS.json').write_text(json.dumps(records,indent=2)+'\n');print('Passed Schur controls')
