import numpy as np,json
from scipy.linalg import solve
from block_gmres import solve as block
rng=np.random.default_rng(773);n=70
q=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n));a=q*.01+np.diag(np.linspace(1,4,n));b=rng.normal(size=(n,8))+1j*rng.normal(size=(n,8));b[:,2]=b[:,1];b[:,3]=0
x,d=block(lambda x:a@x,lambda x:x/np.diag(a)[:,None],b,restart_blocks=10)
ref=solve(a,b);err=float(np.linalg.norm(x-ref)/np.linalg.norm(ref))
assert err<1e-11 and np.allclose(x[:,1],x[:,2],atol=1e-13,rtol=1e-12) and np.all(x[:,3]==0)
assert min(d['next_block_ranks'])<8
zero,zero_info=block(lambda x:a@x,lambda x:x/np.diag(a)[:,None],np.zeros((n,3),complex))
assert np.all(zero==0) and zero_info['max_scaled_relative_residual']==0
print(json.dumps(dict(relative_error=err,all_zero_rhs_passed=True,**d)))
