import sys, warnings
sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np
from ghost_backend.linalg.dense import DenseFactor
rng=np.random.default_rng(0)
n=200
def trial(name,A,b):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        try:
            f=DenseFactor(A.copy(),None,'t')
            x=f.solve(b)
            print(name,'-> ACCEPTED; nonfinite entries in x:',int((~np.isfinite(x)).sum()),'of',x.size,
                  'event max_backward_error',f.event['max_backward_error'],'max_relative_residual',f.event['max_relative_residual'],
                  'relative_residual', f.relative_residual[:3], 'warnings',[str(i.message)[:60] for i in w][:2])
        except Exception as e:
            print(name,'-> raised',type(e).__name__,str(e)[:100])
A=rng.standard_normal((n,n))+1j*rng.standard_normal((n,n))
b=rng.standard_normal((n,3))+0j
A1=A.copy(); A1[:,7]=0            # zero column: exactly singular
trial('zero column',A1,b)
A2=A.copy(); A2[5]=A2[9]          # duplicate rows
trial('duplicate rows',A2,b)
A3=A.copy(); A3[:,3]=A3[:,4]      # duplicate columns
trial('duplicate columns',A3,b)
A4=np.zeros((n,n),complex); trial('zero matrix',A4,b)
A5=np.diag(np.r_[np.ones(n-1),0]).astype(complex); trial('diag with zero',A5,b)
# the metric in isolation
ri=np.array([np.nan]); den=np.array([np.nan])
e=np.divide(ri,den,out=np.zeros_like(ri),where=den>0); print('metric for NaN residual ->',e, 'python max(0.,nan)=',max(0.,float('nan')))
