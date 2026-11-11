import sys, os
os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ.pop('GHOST_BACKEND_PATH',None)
root=os.path.abspath(sys.argv[1]); sys.path.insert(0,root)
from GRIM_Backend.integrations import ghost as G
from GRIM_Backend.execution import diagnostics as D
backend=G.discover_ghost_backend(None)
missing=[p for p in D.GHOST_SENTINELS if not (backend/p).is_file()]
loc_missing=[(k,v) for k,v in D.GHOST_MODULE_LOCATIONS.items() if not (backend/v).exists()]
ok=fail=0; fails=[]
for name in sorted(D.GHOST_MODULE_LOCATIONS):
    try: G.load_ghost_module(name); ok+=1
    except Exception as e: fail+=1; fails.append((name,type(e).__name__,str(e)[:90]))
print(os.path.basename(root),'| sentinels',len(D.GHOST_SENTINELS),'missing',missing,'| module map entries',len(D.GHOST_MODULE_LOCATIONS),'missing files',loc_missing,'| loaded',ok,'failed',fail,fails[:4])
insp=G.load_ghost_module('assembly_inspector'); print('   ContributionInspector constructed:', type(insp.ContributionInspector()).__name__)
