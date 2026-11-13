"""Recompute comparisons from archived complete arrays and raw timings."""
from pathlib import Path
import json,numpy as np
R=Path('results')
comparisons=[]
def compare(a,b,keys=None):
 x=np.load(R/(a+'.npz'));y=np.load(R/(b+'.npz'))
 for key in (x.files if keys is None else keys):
  assert key in y.files,(b,key)
  if not x[key].size:err=0.
  else:err=float(np.max(abs(x[key]-y[key]))/max(float(np.max(abs(x[key]))),1e-300))
  comparisons.append(dict(reference=a,candidate=b,array=key,relative_max_error=err,bitwise=bool(np.array_equal(x[key],y[key]))))
for i in range(3):compare(f'physical-{i}-baseline',f'physical-{i}-candidate')
for threads in [1,4]:compare(f'hierarchical-baseline-{threads}',f'hierarchical-candidate-{threads}')
compare('hierarchical-candidate-1','hierarchical-candidate-4')
compare('dense-fallback-prior-4096','dense-production-4096',['field','density'])
for name in ['dense-simd','dense-unroll']:compare('dense-native',name,['density','field'])
for width in [2,64]:compare(f'product-baseline-{width}',f'product-candidate-{width}')
for body in ['pec','diel']:
 for mode in ['dense','compressed']:compare(f'public-{body}-{mode}-baseline',f'public-{body}-{mode}-candidate')
for i in range(2):compare(f'cluster-{i}-256',f'cluster-{i}-128',['field','density'])
for name in ['compressed-production-4096','leaf-128-4096','leaf-64-4096','eta-1.5-4096','eta-2.0-4096','quantized-inverse-4096','fmm-production-4096']:
 compare('dense-production-4096',name,['field','density'])
# All implementation checks must retain exact values in this environment.
implementation=[x for x in comparisons if any(w in x['candidate'] for w in ['physical-','hierarchical-','public-','product-candidate'])]
assert all(x['bitwise'] for x in implementation)
validation=json.loads((R/'full-validation.json').read_text());residuals=[]
for row in validation['cases']:
 z=np.load(R/('full-residual-'+row['case']+'.npz'));r=z['residual'];b=z['rhs'];x=z['density'];rows=z['row_scale'];cols=z['column_scale']
 p=np.max(abs(r),axis=0)/(z['matrix_inf']*np.max(abs(x),axis=0)+np.max(abs(b),axis=0))
 s=np.sum(abs(r)/rows[:,None],axis=0)/(z['scaled_norm_1']*np.sum(abs(x)*cols[:,None],axis=0)+np.sum(abs(b)/rows[:,None],axis=0))
 assert np.array_equal(p,row['physical']) and np.array_equal(s,row['scaled'])
 assert max(p.max(),s.max())<1e-12
 residuals.append(dict(case=row['case'],physical=float(p.max()),scaled=float(s.max())))
summary=dict(comparisons=comparisons,full_residuals=residuals,all_implementation_arrays_bitwise=True)
print(json.dumps(summary,indent=2))
