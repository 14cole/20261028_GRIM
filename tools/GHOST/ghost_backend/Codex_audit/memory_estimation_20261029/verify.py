"""Verify audit conclusions and preserve evidence/source identities."""
import hashlib
import json
from pathlib import Path
import sys
from audit import HERE, ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


if '--freeze' in sys.argv:
    inputs=read(HERE/'input_hashes.json')
    reference=ROOT/read(HERE/'live_inlet15/result.json')['reference']
    inputs[str(reference.relative_to(ROOT))]=digest(reference)
    (HERE/'input_hashes.json').write_text(json.dumps(inputs,indent=2)+'\n')
    sources=['twod/solver.py','twod/assembly/session.py','twod/assembly/polynomial_pair.py',
        'twod/adaptivity.py','execution/angle_batch.py','execution/options.py','execution/cpu.py',
        'execution/memory.py','execution/metrics.py','execution/frequency_sweep.py',
        'execution/fresh_sweep.py','execution/policy.py','compressed/runtime.py',
        'compressed/memory.py','compressed/factor.py','compressed/inverse.py',
        'compressed/operator.py','compressed/hmatrix.py','compressed/hmatrix_factor.py',
        'compressed/polarization_cache.py','compressed/retained_storage.py',
        'compressed/tile_processes.py','compressed/worker_pool.py','linalg/residual_spool.py',
        'linalg/hierarchical.py','runs/local_twod_driver.py','hpc/twod_driver.py','hpc/scheduler.py']
    (HERE/'source_hashes.json').write_text(json.dumps({p:digest(ROOT/p) for p in sources},indent=2)+'\n')
    paths=[p for p in HERE.iterdir() if p.is_file() and p.name not in ('evidence_hashes.json','verification.json')]
    paths+=list((HERE/'live_inlet15').iterdir())
    (HERE/'evidence_hashes.json').write_text(json.dumps(
        {str(p.relative_to(HERE)):digest(p) for p in paths if p.is_file()},indent=2)+'\n')

inputs=read(HERE/'input_hashes.json')
sources=read(HERE/'source_hashes.json')
artifacts=read(HERE/'evidence_hashes.json')
for base,manifest in ((ROOT,inputs),(ROOT,sources),(HERE,artifacts)):
    for path,expected in manifest.items():
        assert digest(base/path)==expected,path
evidence=read(HERE/'evidence.json');r=evidence['reproductions']
assert abs(r['initial_24_gib_available']['solve_limit_gib']-21.6)<1e-9
for key in ('CompressedFactor','HMatrixFactor'):
    assert r['resident_10_gib'][key]['error']=='No compressed inverse storage remains.'
    assert abs(r['resident_8_gib'][key]['inverse_budget_gib']-.64)<1e-8
assert r['known_zero_available_with_explicit_12_gib_cap']==12
assert r['local_driver_actual_zero_probe']['detected_available_gib'] is None
assert r['local_driver_actual_zero_probe']['budget_gib']==24
spool=evidence['spool_accounting']
assert spool['partner_payload_arrays_resident']==0 and spool['reload_numerically_verified']
assert spool['partner_charged_bytes']>spool['partner_spooled_payload_bytes']>0
summary=read(HERE/'live_summary.json')
assert summary['result']['status']=='passed'
assert summary['result']['quality_passed'] and summary['result']['mesh_certified']
assert max(summary['result']['relative_max_field_differences'].values())==0
assert read(HERE/'live_inlet15/monitor.json')['stop_reason'] is None
tests=read(HERE/'validation_results.json')
assert len(tests)==66 and all(t['outcome']=='passed' for t in tests)
assert (HERE/'validation_exit_code.txt').read_text()=='0'
result=dict(status='passed',historical_input_files_unchanged=len(inputs),
    audited_source_files=len(sources),audit_artifacts_verified=len(artifacts),
    existing_tests_passed=len(tests),live_solve='quality and mesh certified, unchanged fields',
    production_changes='none in this audit',
    near_90_percent_physical_ram_validation='not performed')
(HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
