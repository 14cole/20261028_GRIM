"""Adversarial sampled-zero components under physical S/K/W length scaling."""
import os,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST');sys.path.insert(0,'fmm')
from safe_cross import scaled_components
from ghost_backend.compressed.hmatrix import HMatrixRejected
rng=np.random.default_rng(5);m,n=72,80
low=lambda rank:(rng.normal(size=(m,rank))+1j*rng.normal(size=(m,rank)))@(rng.normal(size=(rank,n))+1j*rng.normal(size=(rank,n)))
a=low(3);hidden=low(2);sample=np.unique(np.linspace(0,m-1,8,dtype=int));hidden[sample]=0;records=[]
for mode in ['common_amplitude','length_units']:
 for scale in [1e-6,1.,1e6]:
  factors=[scale]*3 if mode=='common_amplitude' else [scale**2,scale,1.]
  values=[a*factors[0],hidden*1e-12*factors[1],2*a*factors[2]]
  def fetch(rows=None,cols=None):
   r=np.arange(m) if rows is None else rows;c=np.arange(n) if cols is None else cols
   return [v[np.ix_(r,c)] for v in values]
  try:scaled_components(fetch,(m,n),1e-13,np.random.default_rng(8),36)
  except HMatrixRejected as e:
   assert 'Unseen component' in str(e)
   # HierarchicalNear's existing rejection handler fetches every coefficient.
   dense=fetch();assert all(np.array_equal(x,y) for x,y in zip(values,dense))
  else:raise AssertionError('Hidden component was accepted with a guessed scale')
  records.append(dict(mode=mode,scale=scale,exact_fallback=True,hidden_component_bitwise=True))
Path('results/unseen-policy.json').write_text(json.dumps(records,indent=2))
