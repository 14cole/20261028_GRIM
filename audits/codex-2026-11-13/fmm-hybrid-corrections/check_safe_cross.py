"""Regression for zero/tiny components and a production-call-site control."""
import os,sys,json,warnings
import numpy as np
sys.path.insert(0,os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup')+'/tools/GHOST')
from ghost_backend.compressed.hmatrix import cross_approximation
from safe_cross import scaled_components
from ghost_backend.compressed.hmatrix import HMatrixRejected

rng=np.random.default_rng(123);m,n=72,80
u=rng.normal(size=(m,3))+1j*rng.normal(size=(m,3))
v=rng.normal(size=(3,n))+1j*rng.normal(size=(3,n))
a=u@v
results=[]
for label,values in [('zero',[a,np.zeros_like(a),2*a]),('tiny',[a,a*1e-300,2*a]),('all_zero',[np.zeros_like(a)]*3)]:
 def fetch(rows=None,cols=None):
  r=np.arange(m) if rows is None else rows;c=np.arange(n) if cols is None else cols
  return [z[np.ix_(r,c)] for z in values]
 factors,estimate=scaled_components(fetch,(m,n),1e-13,np.random.default_rng(8),36)
 errors=[]
 for exact,(u1,v1) in zip(values,factors):
  scale=np.max(abs(exact))
  error=float(np.max(abs((u1@v1).real-exact.real))/scale+np.max(abs((u1@v1).imag-exact.imag))/scale) if scale else float(np.max(abs(u1@v1)))
  assert error<1e-12,(label,error)
  errors.append(error)
 results.append(dict(case=label,errors=errors,ranks=[u.shape[1] for u,v in factors],estimate=estimate))
values=[a,np.zeros_like(a),2*a]
subnormal=[a,a*1e-320,2*a]
try:
 scaled_components(lambda r=None,c=None:[z[np.ix_(np.arange(m) if r is None else r,np.arange(n) if c is None else c)] for z in subnormal],(m,n),1e-13,np.random.default_rng(8),36)
 raise AssertionError('Subnormal output accuracy must not be assumed')
except HMatrixRejected:
 results.append(dict(case='nonzero_subnormal',rejected_to_exact_storage=True))
def rows(r):return [z[r] for z in values]
def cols(c):return [z[:,c] for z in values]
with warnings.catch_warnings(record=True) as caught:
 warnings.simplefilter('always')
 factors,estimate=cross_approximation(rows,cols,(m,n),[1e-11,1e-313,1e-11],8,np.random.default_rng(8),max_rank=36)
 results.append(dict(case='original_subnormal',ranks=[u.shape[1] for u,v in factors],warnings=[str(w.message) for w in caught],relative_S=float(np.linalg.norm(factors[0][0]@factors[0][1]-a)/np.linalg.norm(a))))
factors,estimate=cross_approximation(rows,cols,(m,n),[1e-11]*3,8,np.random.default_rng(8),max_rank=36)
err=float(np.linalg.norm(factors[0][0]@factors[0][1]-a)/np.linalg.norm(a));assert err<1e-12
results.append(dict(case='production_style_global_nonzero_tolerance',relative_S=err,ranks=[u.shape[1] for u,v in factors]))
print(json.dumps(results,indent=2))
