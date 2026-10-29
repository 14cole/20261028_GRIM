"""Reproduce the default-path admission gap without allocating large matrices."""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT / 'tests')]
os.environ.update(OPENBLAS_NUM_THREADS='2', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
from ghost_backend.execution.options import current_options
from ghost_backend.execution.cpu import configured_batch_size
from ghost_backend.twod import solver
from ghost_backend.compressed import worker_pool
from general_fixtures import fixture
from test_experimental_cpu import fields
import numpy as np


def main():
    arguments = (fixture('rectangle', 24), [1.], list(range(361)))
    reports, results = {}, {}
    for name, options in (
        ('default_compressed', {}),
        ('manual_compressed_batch64', dict(factorization='compressed', angle_batch_size=64)),
        ('legacy_automatic', dict(factorization='adaptive')),
    ):
        estimates = []
        def estimate(*args, **kwargs):
            mode = current_options()['factorization']
            batch = configured_batch_size()
            # Deterministic admission pressure; actual solves remain tiny.
            value = .1 + .01*batch if mode == 'compressed' else 4.
            estimates.append(dict(mode=mode, batch=batch, n_rhs=kwargs.get('n_rhs'), estimated_gib=value))
            return value
        started = time.perf_counter()
        with patch.object(solver, '_estimate_memory_gb', side_effect=estimate), \
             patch.object(solver, '_solve_memory_limit_gb', return_value=1.), \
             patch.object(worker_pool, 'release_idle', wraps=worker_pool.release_idle) as release, \
             patch('ghost_backend.execution.timing_history.read', return_value={}), \
             patch('ghost_backend.execution.timing_history.record'):
            try:
                result = solver.solve_monostatic_rcs_2d(*arguments, geometry_units='meters',
                    execution_options=dict(assembly_threads=2, blas_threads=2, **options))
            except MemoryError as exc:
                report = dict(status='memory_rejected', message=str(exc))
            else:
                results[name] = result
                meta = result['metadata']
                report = dict(status='solved', factorization=meta['execution_options']['factorization'],
                    batch=meta['execution_options']['angle_batch_size'],
                    sample_counts={pol: len(result['co_solved_samples'][pol]) for pol in ('VV', 'HH')},
                    adjustment=meta.get('backend_selection', {}).get('resource_adjustment'))
            report.update(seconds=time.perf_counter()-started, idle_release_calls=release.call_count,
                          estimates=estimates)
        reports[name] = report
        assert current_options() is None
    assert reports['default_compressed']['status'] == 'memory_rejected'
    assert reports['default_compressed']['idle_release_calls'] == 0
    for name in ('manual_compressed_batch64', 'legacy_automatic'):
        assert reports[name]['status'] == 'solved'
        assert reports[name]['factorization'] == 'compressed'
        assert reports[name]['batch'] == 64
        assert reports[name]['sample_counts'] == dict(VV=361, HH=361)
    assert reports['legacy_automatic']['idle_release_calls'] > 0
    differences = {}
    for pol in ('VV', 'HH'):
        a, b = fields(results['manual_compressed_batch64'], pol), fields(results['legacy_automatic'], pol)
        np.testing.assert_allclose(a, b, rtol=1e-10, atol=1e-12)
        differences[pol] = float(np.max(abs(a-b)))
    diagnostic = ROOT / 'Codex_audit/automatic_selection_20261029/runs/coated3_condition_diagnostic'
    saved_result = json.loads((diagnostic/'result.json').read_text())
    metadata = json.loads((diagnostic/'metadata.json').read_text())
    output = dict(
        scope='Controlled forecast injection, 1 GiB admission budget, real small-geometry numerical solves. Not a capacity benchmark.',
        reports=reports, maximum_absolute_field_difference=differences,
        diagnostic_artifact=dict(result_status=saved_result.get('status'),
            result_uncertified=saved_result.get('uncertified'),
            metadata_quality_gate_passed=metadata.get('quality_gate', {}).get('passed'),
            metadata_mesh_certified=metadata.get('mesh_convergence_certified')),
        assertions_passed=True)
    (HERE/'verification.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(dict(assertions_passed=True, reports={k: {a:b for a,b in v.items() if a!='estimates'}
        for k,v in reports.items()}, diagnostic_artifact=output['diagnostic_artifact']), indent=2))


if __name__ == '__main__':
    main()
