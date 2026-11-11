"""Compare explicit, inherited, environment and scheduler caps at the public wrapper."""
import sys,json,threading,time,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.execution.options import configured_execution,execution_scope
from ghost_backend.execution import memory_budget as M
from ghost_backend.execution.policy import rank_candidates
@configured_execution
def request(solver_method='direct',abort_event=None):
    cap=M.current().limit()
    rank_candidates({'dense':dict(peak_gb=.75,cost=1.)},cap)
    return dict(metadata={},admitted=cap)
rows=[]
def run(kind):
    result={}
    def peer():
        try:
            if kind=='explicit':r=request(execution_options=dict(factorization='dense',ram_budget_gib=.8))
            elif kind=='inherited':
                with execution_scope(dict(factorization='dense',ram_budget_gib=.8)):r=request()
            elif kind=='scheduler':
                with execution_scope(dict(factorization='dense'),memory_budget_gib=.8):r=request()
            else:r=request()
            result.update(status='passed',admitted=r['admitted'])
        except Exception as exc:result.update(status=type(exc).__name__,message=str(exc))
    env={'GHOST_MAX_SOLVE_GB':'.8'} if kind=='environment' else {}
    with patch.dict(os.environ,env),patch('ghost_backend.twod.solver._detect_available_gb',return_value=1./.9):
        with execution_scope(dict(factorization='dense',ram_budget_gib=.4)),M.scope() as owner:
            assert abs(owner.limit()-.4)<1e-12
            thread=threading.Thread(target=peer);thread.start();thread.join(.7)
            waited=thread.is_alive()
        thread.join(5);assert not thread.is_alive()
    rows.append(dict(source=kind,waited=waited,**result))
for kind in ('explicit','inherited','scheduler','environment'):run(kind)
assert rows[0]['waited'] and rows[0]['status']=='passed',rows
assert all(not x['waited'] and x['status']=='MemoryError' for x in rows[1:]),rows
print(json.dumps(rows,indent=2))
