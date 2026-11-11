import sys, os
os.environ['QT_QPA_PLATFORM']='offscreen'
root=sys.argv[1]; sys.path.insert(0,root)
from GRIM_Backend.execution import diagnostics as D
res=D.collect_diagnostics()
bad=[r for r in res if getattr(r,'status','')!='PASS']
print(os.path.basename(root),'| results',len(res),'| startup exit code',D.startup_exit_code(res))
for r in res:
    s=getattr(r,'status','')
    if s!='PASS' and getattr(r,'required',False): print('  REQUIRED',s,'|',r.key if hasattr(r,'key') else '',r.label if hasattr(r,'label') else '','|',str(getattr(r,'detail',''))[:330])
