import concurrent.futures,json,os,subprocess,sys
from pathlib import Path
here=Path(__file__).resolve().parent
roots=sys.argv[1:] or ['/workspace/backend-simplification','/workspace/backend-performance',
                      '/workspace/performance-fallback-base','/workspace/performance-fallback-new']
assert len(roots)==4, 'Provide BASE NEW BASE_NATIVE_FREE NEW_NATIVE_FREE'
jobs=list(zip(('base-native','new-native','base-fallback','new-fallback'),roots))
def run(item):
 name,root=item
 with (here/(name+'.log')).open('w') as log:
  p=subprocess.run([sys.executable,str(here/'regression/golden.py'),root,str(here/(name+'.npz'))],
      env=dict(os.environ,GHOST_AUDIT_ROOT=root,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),stdout=log,stderr=subprocess.STDOUT,timeout=1200)
 return dict(case=name,rc=p.returncode)
with concurrent.futures.ThreadPoolExecutor(2) as pool:rows=list(pool.map(run,jobs))
(here/'field-run-status.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows),flush=True)
assert all(r['rc']==0 for r in rows)
import numpy as np
comp=[]
for mode in ('native','fallback'):
 with np.load(here/('base-'+mode+'.npz')) as a,np.load(here/('new-'+mode+'.npz')) as b:
  assert set(a.files)==set(b.files)
  for key in a.files:
   assert a[key].shape==b[key].shape and a[key].dtype==b[key].dtype
   equal=a[key].tobytes()==b[key].tobytes()
   relative=float(np.max(abs(a[key]-b[key]))/max(np.max(abs(a[key])),1e-300))
   comp.append(dict(mode=mode,case=key,bitwise_equal=equal,relative_error=relative))
   assert relative<1e-9,(mode,key,relative)
(here/'field-comparisons.json').write_text(json.dumps(comp,indent=2)+'\n')
print('PASS',len(comp),'native/fallback fieldsets; bitwise',sum(r['bitwise_equal'] for r in comp))
