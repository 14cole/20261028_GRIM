"""Controlled leaf admission on the real builder, Construction, and RAM ledger.

Synthetic leaf inputs and injected compression rejection isolate the guard.
The probe oracle raises before allocating a query result. This is not an OS
pressure test or proof that a baseline full solve fits the probe reservation.
"""
import json, os, sys
from pathlib import Path
import numpy as np

variant = sys.argv[1]
root = Path(os.environ['GRIM_ROOT' if variant == 'candidate' else 'BASE_GRIM_ROOT'])
sys.path.insert(0, str(root/'tools/GHOST'))
from ghost_backend.compressed.hmatrix_factor import HMatrixSystem
from ghost_backend.compressed.construction import Construction
from ghost_backend.execution import memory_budget as mb
from ghost_backend.execution.options import execution_scope
from ghost_backend.linalg.hierarchical import HierarchicalRejected
from ghost_backend.twod import solver  # warm imports before taking an RSS baseline

MIB = 1024**2
class QueryReached(Exception):
    pass

class Access:
    def __init__(self, matrix, probe):
        self.matrix, self.probe, self.calls = matrix, probe, 0
    def get(self, rows, columns):
        self.calls += 1
        if self.probe:
            raise QueryReached('Probe reached the query without allocating it')
        return self.matrix[np.ix_(rows, columns)]

def run(n, probe):
    q = 16*n*n
    cap = (3*q + MIB/2) if probe else 256*MIB
    matrix = np.diag(np.linspace(1., 2., n).astype(complex))
    rhs = np.column_stack([np.ones(n), np.arange(n)/n]).astype(complex)
    expected = rhs/np.diag(matrix)[:, None]
    access = Access(matrix, probe)
    # Bypass operator assembly to isolate the actual leaf/fallback build branch.
    owner = HMatrixSystem.__new__(HMatrixSystem)
    owner.bytes = 0
    owner.budget = 1024*MIB
    owner.leaf = 256
    owner.leaves = owner.dense_fallbacks = owner.largest_dense_fallback = 0
    owner.inverse_only = True
    owner.checkpoint = lambda: None
    def reject(*args):
        raise HierarchicalRejected('Injected compression rejection for fallback query')
    owner.compress_block = reject
    owner.construction = Construction(owner)
    status, error, node = None, None, None
    with execution_scope({'assembly_threads':1, 'blas_threads':1, 'ram_budget_gib':cap/mb.GIB}):
        with mb.scope(wanted_gib=cap/mb.GIB) as ledger:
            try:
                with owner.construction.track():
                    node = owner.build(access, np.arange(n))
                status = 'built'
            except QueryReached:
                status = 'query_reached'
            except MemoryError as exc:
                status, error = 'memory_rejected', str(exc)
            events = list(ledger.events)
            assert ledger.pending_construction_bytes == 0
            assert not ledger.objects
            assert owner.construction.bytes == 0
            errors = []
            if node is not None:
                for trans in (0, 1, 2):
                    result = node.solve(rhs, trans=trans)
                    errors.append(float(np.max(abs(result-expected))))
                assert max(errors) < 1e-14
    if probe:
        assert status == ('query_reached' if variant == 'baseline' else 'memory_rejected')
        assert access.calls == (1 if variant == 'baseline' else 0)
        if variant == 'candidate':
            assert events[-1]['context'] == 'Compressed inverse leaf coefficients'
            assert events[-1]['binding_constraint'] == 'stable_reservation'
    else:
        assert status == 'built' and access.calls == 1
    return dict(variant=variant,side=n,query_bytes=q,probe=probe,reservation_bytes=cap,
                status=status,error=error,query_calls=access.calls,events=events,
                pending_after=ledger.pending_construction_bytes,registered_after=len(ledger.objects),
                construction_bytes_after=owner.construction.bytes,dense_fallbacks=owner.dense_fallbacks,
                construction=owner.construction.evidence,solve_max_abs_errors=errors)

records = [run(n, probe) for n in (256, 512, 1024) for probe in (True, False)]
out = Path(__file__).resolve().parent/'fresh'/('headroom-'+variant+'.json')
out.write_text(json.dumps(records, indent=2))
print(json.dumps([{k:r[k] for k in ('variant','side','probe','status','query_calls','pending_after')} for r in records], indent=2))
