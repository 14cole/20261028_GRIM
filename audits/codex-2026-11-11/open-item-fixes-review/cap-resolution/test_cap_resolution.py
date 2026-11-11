"""Public admission tests: cap sources, precedence, lock order and cancellation."""
import json,os,sys,threading,time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.execution.options import configured_execution,execution_scope,_held_blas_lock
from ghost_backend.execution import memory_budget as M
from ghost_backend.execution.policy import rank_candidates

@configured_execution
def direct_request(solver_method='direct',abort_event=None,peak=.75):
    budget=M.current().limit()
    rank_candidates({'dense':dict(peak_gb=peak,cost=1.)},budget)
    return dict(metadata={},budget=budget,ledger=id(M.current()))

@configured_execution
def monostatic_request(solver_method='auto',abort_event=None,peak=.75):
    return direct_request(solver_method='experimental_cpu',abort_event=abort_event,peak=peak)

results=[]
def check(name,ok,detail=None):
    assert ok,(name,detail)
    results.append(dict(name=name,detail=detail));print('PASS',name,flush=True)

def trial(name,requested=None,inherited=None,scheduler=None,env=None,automatic=False,
          expected_wait=True,expected_budget=.8,peak=.75,expected_error=None,hold_blas=False,cancel=False):
    outcome={};entered=threading.Event();abort=threading.Event()
    def peer():
        try:
            with ExitStack() as scopes:
                if inherited is not None or scheduler is not None:
                    scopes.enter_context(execution_scope(inherited or {},memory_budget_gib=scheduler))
                if hold_blas:scopes.enter_context(_held_blas_lock())
                entered.set();start=time.perf_counter()
                kwargs=dict(abort_event=abort,peak=peak)
                if requested is not None:kwargs['execution_options']=requested
                r=(monostatic_request if automatic else direct_request)(**kwargs)
                outcome.update(status='ok',budget=r['budget'],elapsed=time.perf_counter()-start,
                               numerical_seconds=r['metadata'].get('execution_wall_seconds'))
        except Exception as exc:outcome.update(status=type(exc).__name__,message=str(exc))
    with patch.dict(os.environ,dict(env or {}),clear=False),patch('ghost_backend.twod.solver._detect_available_gb',return_value=1./.9):
        with execution_scope(dict(ram_budget_gib=.4)),M.scope() as owner:
            assert abs(owner.limit()-.4)<1e-12
            t=threading.Thread(target=peer);t.start();assert entered.wait(5)
            t.join(.5);waited=t.is_alive()
            if cancel:abort.set();t.join(3)
        t.join(5);assert not t.is_alive(),name
    check(name+' waiting',waited==expected_wait,outcome)
    check(name+' result',outcome['status']==(expected_error or 'ok'),outcome)
    if expected_error is None:
        check(name+' cap',abs(outcome['budget']-expected_budget)<1e-9,outcome)
        if expected_wait and outcome['numerical_seconds'] is not None:
            check(name+' queue excluded from solver timing',outcome['elapsed']-outcome['numerical_seconds']>.35,outcome)

for key in ('GHOST_MAX_SOLVE_GB','GHOST_CPU_FACTORIZATION'):
    os.environ.pop(key,None)
trial('direct cap',requested=dict(ram_budget_gib=.8))
trial('inherited cap',inherited=dict(ram_budget_gib=.8))
trial('scheduler cap',scheduler=.8)
trial('legacy environment cap',env={'GHOST_MAX_SOLVE_GB':'.8'})
trial('automatic environment cap',env={'GHOST_MAX_SOLVE_GB':'.8'},automatic=True,requested=dict(factorization='dense'))
trial('scheduler tighter',requested=dict(ram_budget_gib=.8),scheduler=.5,expected_wait=False,expected_budget=.5,peak=.45,
      inherited=dict(ram_budget_gib=.8))
trial('profile tighter',inherited=dict(ram_budget_gib=.45),scheduler=.8,expected_wait=False,expected_budget=.45,peak=.4)
trial('inherited null masks environment',inherited=dict(ram_budget_gib=None),env={'GHOST_MAX_SOLVE_GB':'.8'},expected_wait=False,expected_budget=.6,peak=.5)
trial('explicit null masks automatic environment',requested=dict(factorization='dense',ram_budget_gib=None),env={'GHOST_MAX_SOLVE_GB':'.8'},automatic=True,expected_wait=False,expected_budget=.6,peak=.5)
trial('direct partial profile masks environment',requested=dict(factorization='dense'),env={'GHOST_MAX_SOLVE_GB':'.8'},expected_wait=False,expected_budget=.6,peak=.5)
trial('null still bounded by scheduler',requested=dict(ram_budget_gib=None),inherited={},scheduler=.5,env={'GHOST_MAX_SOLVE_GB':'.8'},expected_wait=False,expected_budget=.5,peak=.45)
trial('inherited cancellation',inherited=dict(ram_budget_gib=.8),cancel=True,expected_error='InterruptedError')
trial('BLAS holder refuses without waiting',inherited=dict(ram_budget_gib=.8),hold_blas=True,expected_wait=False,expected_error='MemoryError')
trial('conflicting inherited profile rejects before wait',requested=dict(ram_budget_gib=.9),inherited=dict(ram_budget_gib=.8),expected_wait=False,expected_error='ValueError')
for value in (0.,-1.,float('nan'),float('inf'),True,'0.8'):
    trial('invalid cap '+str(value),requested=dict(ram_budget_gib=value),expected_wait=False,expected_error='ValueError')

@configured_execution
def nested_request(solver_method='direct'):
    ledger=M.current()
    r=direct_request(peak=.1)
    return dict(metadata={},same=ledger is M.current() and r['ledger']==id(ledger))
r=nested_request(execution_options=dict(ram_budget_gib=1.))
check('nested requests share one ledger',r['same'])
check('request ledger restored',M.current() is None)
Path(__file__).with_name('cap-resolution-results.json').write_text(json.dumps(dict(passed=len(results),checks=results),indent=2)+'\n')
print('PASS total',len(results))
