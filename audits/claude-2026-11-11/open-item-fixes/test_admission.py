"""Deterministic checks of same-process memory admission. No numerical allocation.

usage: python test_admission.py <checkout root>
Cohort capacity is mocked to 1 GiB. Exits non-zero on any failure.
"""
import sys, threading, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.execution.options import execution_scope, _held_blas_lock
from ghost_backend.execution import memory_budget as M
from ghost_backend.execution.policy import rank_candidates

CANDIDATES = {'dense': dict(peak_gb=.52, cost=1.), 'compressed': dict(peak_gb=.29, cost=2.)}
checks = []
def check(name, ok, detail=''):
    ok = bool(ok); checks.append(ok); print(('ok   ' if ok else 'FAIL ') + name + (' ' + str(detail) if detail else ''), flush=True)

def peer(rows, cap=.45, wanted=.45, abort=None, hold_blas=False):
    def body():
        try:
            options = dict(factorization='compressed') if cap is None else dict(factorization='compressed', ram_budget_gib=cap)
            with execution_scope(options), M.scope(abort, wanted_gib=wanted) as ledger:
                budget = ledger.limit(); outcome = 'admitted'
                try: rank_candidates(CANDIDATES, budget)
                except MemoryError as exc: outcome = 'MemoryError'
                rows.append(dict(budget=budget, outcome=outcome, at=time.monotonic()))
        except InterruptedError: rows.append(dict(outcome='interrupted', at=time.monotonic()))
    if hold_blas:
        with _held_blas_lock(): body()
    else: body()

with patch('ghost_backend.twod.solver._detect_available_gb', return_value=1./.9):
    # 1. A request alone is admitted at once with its cap.
    rows = []; t = threading.Thread(target=peer, args=(rows,)); t.start(); t.join(5)
    check('alone: admitted immediately with its cap', not t.is_alive() and rows and abs(rows[0]['budget']-.45) < 1e-9 and rows[0]['outcome'] == 'admitted', rows)

    # 2. Remainder .01 GiB beside a .99 GiB holder: the capped peer waits, then gets .45 GiB.
    rows = []
    with execution_scope(dict(factorization='dense', ram_budget_gib=.99)), M.scope() as owner:
        assert abs(owner.limit()-.99) < 1e-9
        t = threading.Thread(target=peer, args=(rows,)); t.start(); t.join(1.0)
        check('insufficient remainder: capped peer waits', t.is_alive() and not rows)
        released = time.monotonic()
    t.join(5)
    check('insufficient remainder: admitted with full cap after release',
          not t.is_alive() and rows and rows[0]['outcome'] == 'admitted' and abs(rows[0]['budget']-.45) < 1e-9 and rows[0]['at'] >= released, rows)

    # 3. Same, uncapped peer: waits for the minimum shared reservation, then gets the capacity.
    rows = []
    with execution_scope(dict(factorization='dense', ram_budget_gib=.99)), M.scope() as owner:
        owner.limit()
        t = threading.Thread(target=peer, args=(rows,), kwargs=dict(cap=None, wanted=None)); t.start(); t.join(1.0)
        check('insufficient remainder: uncapped peer waits', t.is_alive() and not rows)
    t.join(5)
    check('uncapped peer admitted after release', not t.is_alive() and rows and rows[0]['outcome'] == 'admitted' and rows[0]['budget'] > .9, rows)

    # 4. Enough remainder: peers overlap without waiting (no new serialisation).
    rows = []
    with execution_scope(dict(factorization='dense', ram_budget_gib=.5)), M.scope() as owner:
        owner.limit()
        t = threading.Thread(target=peer, args=(rows,)); t.start(); t.join(5)
        check('sufficient remainder: capped peer overlaps', not t.is_alive() and rows and rows[0]['outcome'] == 'admitted' and abs(rows[0]['budget']-.45) < 1e-9, rows)

    # 5. A waiting request honours its abort event.
    rows = []; abort = threading.Event()
    with execution_scope(dict(factorization='dense', ram_budget_gib=.99)), M.scope() as owner:
        owner.limit()
        t = threading.Thread(target=peer, args=(rows,), kwargs=dict(abort=abort)); t.start(); t.join(.5)
        abort.set(); t.join(5)
        check('waiting peer is interruptible', not t.is_alive() and rows and rows[0]['outcome'] == 'interrupted', rows)

    # 6. A thread that holds the BLAS lock never waits (lock-order rule): immediate, conservative refusal.
    rows = []
    with execution_scope(dict(factorization='dense', ram_budget_gib=.99)), M.scope() as owner:
        owner.limit()
        t = threading.Thread(target=peer, args=(rows,), kwargs=dict(hold_blas=True)); t.start(); t.join(5)
        check('BLAS-lock holder does not wait', not t.is_alive() and rows and rows[0]['outcome'] == 'MemoryError', rows)

    # 7. A cap above the capacity cannot wait for ever: alone it is admitted with the capacity.
    rows = []; t = threading.Thread(target=peer, args=(rows,), kwargs=dict(cap=4., wanted=4.)); t.start(); t.join(5)
    check('cap above capacity: admitted alone', not t.is_alive() and rows and rows[0]['outcome'] == 'admitted', rows)

print('%d passed, %d failed' % (sum(checks), len(checks)-sum(checks))); sys.exit(0 if all(checks) else 1)
