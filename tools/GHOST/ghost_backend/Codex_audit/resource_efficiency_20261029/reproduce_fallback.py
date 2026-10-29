"""Synthetic admission counterexample; no large arrays are allocated."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT/'tests')]
import numpy as np
from ghost_backend.compressed import runtime,memory
from ghost_backend.twod import solver
from test_request_memory_budget import simulated,GIB
sample=dict(operator_bytes=2*GIB,operator_allowance_bytes=2*GIB,method='reproduction',samples=1,sampled=True,groups=16)
with simulated(cap=6.) as (_,ledger),patch('ghost_backend.compressed.worker_pool.forecast_bytes',return_value=2*GIB):
    plan=runtime.planned_forecast(4000,8000,361,256,4,{'compressed_storage':sample,'basis_width':4})
    resident=plan['process_geometry_bytes']+GIB
    source=SimpleNamespace(n=8000,mesh=SimpleNamespace(nodes=range(4000)))
    with patch.object(memory,'sample_operator',return_value=sample),patch.object(solver,'_process_rss_bytes',return_value=resident),patch.object(solver,'_solve_memory_limit_gb',return_value=6.),patch('ghost_backend.compressed.worker_pool.retained_bytes',return_value=0),patch('ghost_backend.compressed.worker_pool.release_idle',return_value=0),patch('ghost_backend.twod.operators.get_assembly_threads',return_value=4):
        try:
            result=runtime.admit_tile_fallback(source,np.empty((0,2)),'audit rank rejection')
            record=dict(status='admitted',plan=result['forecasts'][0],active_plan=ledger.plan)
        except MemoryError as exc:record=dict(status='refused',error=str(exc))
    record.update(reservation_gib=6.,unadjusted_payload_gib=plan['storage_limit_bytes']/GIB,extra_resident_gib=1.,
        scope='Synthetic sampled-storage forecast, not proof that an arbitrary numerical factor will fit the reduced cap.')
print(json.dumps(record,indent=2))
