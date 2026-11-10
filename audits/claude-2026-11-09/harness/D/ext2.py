from dlib import *
import traceback, sys
P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
g=geo([('b',2,'2 0 0 0 0',rows(P))]); asp2=[0,10,30,60,90,120,150,170,180]
for nm in (31,):
    try:
        r=run(g,3.0,asp2,n_modes=nm,mode_tol=1e-13); print('explicit',nm,'OK modes',r['metadata']['per_frequency'][0]['modes_used'],flush=True)
    except Exception as e: print('explicit',nm,'FAIL',type(e).__name__,str(e)[:200],flush=True)
try:
    r=run(g,3.0,asp2,mode_tol=1e-13); print('auto OK', r['metadata']['per_frequency'][0]['modes_used'])
except Exception as e:
    tb=traceback.format_exc(); print(tb[-6000:])
