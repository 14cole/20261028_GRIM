"""Check sparse true-residual checks without changing final acceptance."""
import json,numpy as np
from scipy.linalg import solve
from block_gmres import solve as block
rng=np.random.default_rng(773);n=70
q=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))
a=q*.01+np.diag(np.linspace(1,4,n))
b=rng.normal(size=(n,8))+1j*rng.normal(size=(n,8));b[:,2]=b[:,1];b[:,3]=0
reference=solve(a,b);records=[]
for interval in (1,4):
    x,d=block(lambda x:a@x,lambda x:x/np.diag(a)[:,None],b,restart_blocks=10,check_every=interval)
    relative=float(np.linalg.norm(x-reference)/np.linalg.norm(reference))
    assert relative<1e-11 and np.all(x[:,3]==0) and np.allclose(x[:,1],x[:,2],atol=1e-13,rtol=1e-12)
    zero,z=block(lambda x:a@x,lambda x:x/np.diag(a)[:,None],np.zeros((n,3),complex),check_every=interval)
    assert np.all(zero==0) and z['max_scaled_relative_residual']==0
    records.append(dict(relative_error=relative,zero_rhs_passed=True,**d))
print(json.dumps(records,indent=2))
