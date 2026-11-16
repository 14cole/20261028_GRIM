"""Reviewer star-harness runner: builder/audit hooks plus an explicit factor storage budget."""
import os,sys,json,runpy,traceback
from pathlib import Path
sys.path[:0]=[os.environ['MONOSTATIC_AUDIT'],str(Path(os.environ['GRIM_ROOT'])/'tools/GHOST')]
import claude_audit
spec=json.loads(sys.argv[1]);claude_audit.install(spec)
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
if 'factor_storage_mib' in spec:
    init0=HMatrixFactor.__init__
    def init(self,*a,**k):
        k['storage_budget_bytes']=int(spec['factor_storage_mib'])*2**20;return init0(self,*a,**k)
    HMatrixFactor.__init__=init
# own per-call GMRES / upgrade observation: snapshot of the factor event after each inverse call
calls=claude_audit.RECORD.setdefault('event_after_calls',[])
inv0=HMatrixFactor.inverse
def inverse(self,*a,**k):
    try:return inv0(self,*a,**k)
    finally:calls.append({key:self.event.get(key) for key in ('gmres_columns','refinement_steps','max_refinements','factorizations')}|{'preconditioners':[(p.get('bytes'),p.get('tolerance')) for p in self.event.get('preconditioners',[])],'upgrades':[{kk:vv for kk,vv in u.items() if not isinstance(vv,(dict,list))} for u in self.event.get('preconditioner_upgrades',[])] if isinstance(self.event.get('preconditioner_upgrades'),list) else self.event.get('preconditioner_upgrades')})
HMatrixFactor.inverse=inverse
sys.argv=['monostatic.py',json.dumps(spec)];failure=None
try:runpy.run_path(str(Path(os.environ['MONOSTATIC_AUDIT'])/'monostatic.py'),run_name='__main__')
except BaseException as e:failure=traceback.format_exc();raise
finally:Path(spec['out']+'.hooks.json').write_text(json.dumps(dict(claude_audit.RECORD,failure=failure,final_memory=claude_audit.memory()),indent=2,default=str))
