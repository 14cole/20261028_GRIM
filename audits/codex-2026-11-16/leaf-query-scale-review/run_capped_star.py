"""Unmodified star solve with an explicit research storage cap and hook records."""
import os,sys,json,runpy,traceback
from pathlib import Path
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
import claude_audit
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
spec=json.loads(sys.argv[1]);claude_audit.install(spec)
original=HMatrixFactor.__init__
def capped(self,*args,**kwargs):
    kwargs['storage_budget_bytes']=int(spec['storage_mib']*2**20)
    return original(self,*args,**kwargs)
HMatrixFactor.__init__=capped
sys.argv=['monostatic.py',json.dumps(spec)]
try:
    runpy.run_path(str(Path(os.environ['MONOSTATIC_AUDIT'])/'monostatic.py'),run_name='__main__')
except Exception:
    Path(spec['out']+'.failure.json').write_text(json.dumps(dict(traceback=traceback.format_exc()),indent=2))
    raise
finally:
    Path(spec['out']+'.hooks.json').write_text(json.dumps(dict(claude_audit.RECORD,final_memory=claude_audit.memory()),indent=2,default=str))
