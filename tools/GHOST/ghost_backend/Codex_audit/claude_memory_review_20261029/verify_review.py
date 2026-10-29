"""Check Claude's additions without changing production code or old evidence."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT.parent))
GIB=1024**3
from ghost_backend.execution import angle_batch
from ghost_backend.execution.cpu import configured_batch_size
from ghost_backend.execution.options import execution_scope
from ghost_backend.compressed import runtime, worker_pool
from ghost_backend.compressed.hmatrix_factor import HMatrixFactor

summary=json.loads((HERE.parent/'memory_estimation_20261029/live_summary.json').read_text())
p=summary['peak_forecast_components']
base=p['process_geometry_bytes']-p['retained_worker_allowance_bytes']
components=dict(process_geometry_excluding_workers=base,
    retained_workers=p['retained_worker_allowance_bytes'],
    resident_operators=p['resident_operator_bytes'],retained_inverse=p['inverse_ceiling_bytes'],
    angle_batch_workspace=p['rhs_workspace_bytes'],gmres_workspace=p['gmres_workspace_bytes'],
    projection_cache=p['projection_cache_bytes'])
assert sum(components.values())==p['phase_bytes']['solve']==p['peak_bytes']

# _refresh_inverse_budget uses the allowance saved at construction; it does
# not fetch current availability or an automatic allowance a second time.
factor=HMatrixFactor.__new__(HMatrixFactor)
factor.storage_allowance=1000
factor.a=SimpleNamespace(bytes=100,reserved_partner_bytes=50)
with patch.object(runtime,'hmatrix_storage_budget',side_effect=AssertionError('unexpected re-query')), \
     patch('ghost_backend.twod.assembly.polynomial_pair.retained_bytes',return_value=25):
    factor._refresh_inverse_budget()
assert factor.budget==825

# Recovery remains conservative across later systems in one public request.
with execution_scope(dict(factorization='compressed',angle_batch_size=256)), angle_batch.scope(), \
     patch.object(worker_pool,'release_idle',return_value=0):
    estimate=lambda:.1+.01*configured_batch_size()
    angle_batch.recover(estimate(),1.,estimate,lambda:1.,lambda:None,361)
    reduced=configured_batch_size()
    angle_batch.recover(estimate(),32.,estimate,lambda:32.,lambda:None,361)
    later=configured_batch_size()
assert reduced==later==64
with execution_scope(dict(factorization='compressed',angle_batch_size=256)), angle_batch.scope():
    fresh=configured_batch_size()
assert fresh==256

paths=['Claude_audit/review_of_codex_recovery_and_memory_audit.md',
    'compressed/memory.py','compressed/hmatrix_factor.py','compressed/worker_pool.py',
    'execution/angle_batch.py','execution/options.py','twod/solver.py',
    'Codex_audit/memory_estimation_20261029/live_summary.json']
output=dict(status='passed',peak_phase_components_gib={k:v/GIB for k,v in components.items()},
    total_peak_gib=sum(components.values())/GIB,
    process_geometry_including_workers_gib=p['process_geometry_bytes']/GIB,
    hmatrix_refresh_requeries_storage_allowance=False,
    batch_recovery=dict(reduced=reduced,later_ample_budget=later,fresh_request=fresh),
    limitations=['Controlled accounting checks; no new timing, full solve or 90%-RAM stress trial.',
                'Forecast components alone do not measure actual per-component peak residency.'],
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths})
(HERE/'verification.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({k:v for k,v in output.items() if k!='hashes'},indent=2))
