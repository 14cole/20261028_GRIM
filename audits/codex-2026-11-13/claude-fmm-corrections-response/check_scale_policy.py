"""Test common-amplitude and physical S/K/W length scaling of the proposed fallback."""
import os,sys,json
from pathlib import Path
import numpy as np
root=Path(os.environ.get('GRIM_ROOT','/workspace/grim-fmm-followup'))
prior=root/'audits/codex-2026-11-13/fmm-hybrid-corrections'
sys.path[:0]=[str(root/'tools/GHOST'),str(prior)]
from safe_cross import scaled_components
source=(prior/'safe_cross.py').read_text().replace('scale = 1.0','scale = None').replace('if not np.isfinite(scale) or scale <= 0:', 'if scale is not None and (not np.isfinite(scale) or scale <= 0):')
source=source.replace('    def query(rows=None, cols=None):','    partner = max((s for s in scales if s is not None), default=1.0)\n    scales = [partner if s is None else s for s in scales]\n\n    def query(rows=None, cols=None):')
scope={};exec(compile(source,'partner_policy_experiment','exec'),scope);partner_policy=scope['scaled_components']
rng=np.random.default_rng(5);m,n=72,80
low=lambda rank:(rng.normal(size=(m,rank))+1j*rng.normal(size=(m,rank)))@(rng.normal(size=(rank,n))+1j*rng.normal(size=(rank,n)))
a=low(3);hidden=low(2);sample=np.unique(np.linspace(0,m-1,8,dtype=int));hidden[sample]=0
out=[]
for mode in ['common_amplitude','length_units']:
 for scale in [1e-6,1.,1e6]:
  factors=[scale]*3 if mode=='common_amplitude' else [scale**2,scale,1.]
  values=[a*factors[0],hidden*1e-12*factors[1],2*a*factors[2]]
  def fetch(rows=None,cols=None):
   r=np.arange(m) if rows is None else rows;c=np.arange(n) if cols is None else cols
   return [v[np.ix_(r,c)] for v in values]
  for name,fun in [('original',scaled_components),('largest_partner',partner_policy)]:
   f,est=fun(fetch,(m,n),1e-13,np.random.default_rng(8),36)
   out.append(dict(mode=mode,scale=scale,policy=name,ranks=[u.shape[1] for u,v in f],relative_errors=[float(np.linalg.norm(u@v-z)/np.linalg.norm(z)) for (u,v),z in zip(f,values)],estimate=float(est)))
print(json.dumps(out,indent=2))
