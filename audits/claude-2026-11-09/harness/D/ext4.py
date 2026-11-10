from dlib import *
import sys
P=[(0,0.3),(0.1,0.1),(0.1,-0.1),(0,-0.1)]
g=geo([('b',2,'2 -8 0 0 0',rows(P))]); asp=[30,60,90,150]
for f in [float(x) for x in sys.argv[1:]]:
    t=time.time()
    try:
        r=run(g,f,asp); pf=r['metadata']['per_frequency'][0]
        print(f'f={f} n={pf["n_unknowns"]} tail={pf["mode_tail_start"]} cap={pf["mode_cap"]} used={pf["modes_used"]} margin={pf["mode_cap"]-pf["modes_used"]} t={time.time()-t:.0f}s',flush=True)
    except Exception as e: print(f'f={f} FAIL {type(e).__name__}: {str(e)[:260]}',flush=True)
