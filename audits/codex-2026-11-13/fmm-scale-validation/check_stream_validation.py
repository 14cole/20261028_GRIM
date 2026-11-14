import os,sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,os.environ['GRIM_ROOT']+'/tools/GHOST');sys.path.insert(0,'fmm')
from exact_validation import validate_rows
rng=np.random.default_rng(773);n=2000;r=np.array([0,77,81,1901,1999]);a=rng.normal(size=(len(r),n))+1j*rng.normal(size=(len(r),n));x=rng.normal(size=(n,3))+1j*rng.normal(size=(n,3));b=np.zeros_like(x);b[r]=a@x+1e-8
class Oracle:
 def get(self,rows,cols):return a[np.ix_(np.searchsorted(r,rows),cols)]
res=a@x-b[r];norm=np.sum(abs(a),axis=1);error=np.max(abs(res)/(norm[:,None]*np.max(abs(x),axis=0)+abs(b[r])),axis=0)
records=[]
for cap in [300,4000,699050]:
 got,rr,nn,meta=validate_rows(Oracle(),r,n,x,b,entries=cap)
 assert meta['max_query_entries']<=cap
 assert np.allclose(norm,nn,rtol=5e-16)
 assert np.max(abs(rr-res))<1e-12
 assert np.max(abs(got-error))<1e-15
 records.append(dict(cap=cap,max_residual_roundoff=float(abs(rr-res).max()),max_backward_error_delta=float(abs(got-error).max()),**meta))
Path('results/stream-validation.json').write_text(json.dumps(records,indent=2))
