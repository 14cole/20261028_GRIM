"""Deterministic admission probe; no numerical allocation or production edit."""
import sys,json,threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(sys.argv[1])/'tools/GHOST'))
from ghost_backend.execution.options import execution_scope
from ghost_backend.execution import memory_budget as M
from ghost_backend.execution.policy import rank_candidates
rows=[]
def peer():
    with execution_scope(dict(factorization='compressed',ram_budget_gib=.45)),M.scope() as ledger:
        budget=ledger.limit()
        outcome='admitted'
        try:rank_candidates({'dense':dict(peak_gb=.52,cost=1.),'compressed':dict(peak_gb=.29,cost=2.)},budget)
        except MemoryError as exc:outcome=str(exc)
        rows.append(dict(peer_budget=budget,outcome=outcome,ledger=ledger.last))
with patch('ghost_backend.twod.solver._detect_available_gb',return_value=1./.9):
    with execution_scope(dict(factorization='dense',ram_budget_gib=.99)),M.scope() as owner:
        assert abs(owner.limit()-.99)<1e-12
        t=threading.Thread(target=peer);t.start();t.join(timeout=5)
        assert not t.is_alive(), 'Unexpected wait for a partial reservation'
    peer()
assert rows[0]['peer_budget']<.02 and 'No compatible backend' in rows[0]['outcome']
assert abs(rows[1]['peer_budget']-.45)<1e-12 and rows[1]['outcome']=='admitted'
print(json.dumps(rows,indent=2))
