import numpy as np,json
from scipy.linalg import solve
from batched_gmres import solve as batched
rng=np.random.default_rng(773);n=70
q=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n));a=q*.01+np.diag(np.linspace(1,4,n));b=rng.normal(size=(n,8))+1j*rng.normal(size=(n,8));b[:,2]=b[:,1];b[:,3]=0
x,d=batched(lambda x:a@x,lambda x:x/np.diag(a)[:,None],b,restart=30,check_every=4)
ref=solve(a,b);err=float(np.linalg.norm(x-ref)/np.linalg.norm(ref))
assert err<1e-11 and np.array_equal(x[:,1],x[:,2]) and np.all(x[:,3]==0)
print(json.dumps(dict(relative_error=err,**d)))
