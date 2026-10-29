"""Read-only evidence analysis and allocation-free budget reproductions.

No production policy is changed. Large byte counts below are synthetic metadata,
not large allocations. Historical process peaks are observations, not hard bounds.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT.parent))
GIB = 1024**3


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def historical():
    records, hashes = [], {}
    for study in ('solver_studies_20261029', 'automatic_selection_20261029'):
        for path in sorted((HERE.parent / study / 'runs').glob('*/metadata.json')):
            monitor = path.with_name('monitor.json')
            result = path.with_name('result.json')
            if not monitor.exists() or not result.exists():
                continue
            metadata, measured, outcome = [json.loads(p.read_text()) for p in (path, monitor, result)]
            plans = [v for v in walk(metadata) if 'phase_bytes' in v and 'peak_bytes' in v]
            if not plans:
                continue
            for p in (path, monitor, result):
                hashes[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
            peak = max(p['peak_bytes'] for p in plans)
            rss = measured.get('peak_rss_bytes', 0)
            private = measured.get('peak_private_bytes', 0)
            fixed_compressed = outcome.get('case', {}).get('mode') == 'compressed'
            records.append(dict(study=study, run=path.parent.name,
                status=outcome.get('status'), case=outcome.get('case'),
                comparable_fixed_compressed=fixed_compressed,
                comparison_warning=None if fixed_compressed else 'Candidate compressed forecasts may describe an unexecuted backend; do not use this ratio to calibrate execution.',
                forecast_peak_gib=peak/GIB, observed_tree_rss_gib=rss/GIB,
                observed_tree_private_commit_gib=private/GIB,
                forecast_over_observed_rss=peak/rss if rss else None,
                observed_private_over_forecast=private/peak,
                maximum_phase_gib={phase:max(p['phase_bytes'].get(phase,0) for p in plans)/GIB
                                   for phase in ('assembly','factorization','solve')},
                models=sorted(set(p.get('model','') for p in plans)),
                available_start_gib=measured.get('host_available_start_bytes',0)/GIB,
                available_minimum_gib=measured.get('host_available_minimum_bytes',0)/GIB,
                monitor_stop_reason=measured.get('stop_reason')))
    return records, hashes


def reproductions():
    import numpy as np
    from ghost_backend.twod import solver
    from ghost_backend.compressed import runtime
    from ghost_backend.compressed.factor import CompressedFactor
    from ghost_backend.compressed.hmatrix_factor import HMatrixFactor
    from ghost_backend.execution.options import execution_scope
    from ghost_backend.hpc import scheduler
    values = {}
    options = dict(factorization='compressed', compressed_storage_mib=0)
    with execution_scope(options), patch.object(solver, '_detect_available_gb', return_value=24.):
        initial_limit = solver._solve_memory_limit_gb()
        initial_storage = runtime.storage_budget()
    values['initial_24_gib_available'] = dict(solve_limit_gib=initial_limit,
                                            storage_limit_gib=initial_storage/GIB)
    for resident in (4, 8, 10):
        # Model no external memory pressure, only this operator becoming resident.
        # _fresh_build is disabled to inspect allocation accounting, not numerics.
        operator = SimpleNamespace(bytes=resident*GIB, row_norm=np.ones(1), row_error=np.zeros(1),
                                   n=1, evidence={}, checkpoint=lambda:None)
        record = dict(resident_operator_gib=resident, available_gib=24-resident,
                      fixed_initial_storage_inverse_room_gib=initial_storage/GIB-resident)
        with execution_scope(options), patch.object(solver, '_detect_available_gb', return_value=24-resident):
            record['live_solve_limit_without_credit_gib'] = solver._solve_memory_limit_gb()
            record['live_solve_limit_with_credit_gib'] = solver._solve_memory_limit_gb(resident)
            record['storage_limit_gib'] = runtime.storage_budget()/GIB
            for kind in (CompressedFactor, HMatrixFactor):
                try:
                    with patch.object(kind, '_fresh_build', return_value=None):
                        factor = kind(operator, check_precision=False)
                    record[kind.__name__] = dict(inverse_budget_gib=factor.budget/GIB)
                except MemoryError as exc:
                    record[kind.__name__] = dict(error=str(exc))
        values['resident_{}_gib'.format(resident)] = record
    values['readmission_example'] = dict(total_predicted_peak_gib=18, already_resident_gib=8,
        remaining_available_gib=16, current_limit_gib=14.4, additional_needed_gib=10,
        initial_budget_gib=21.6, current_total_peak_comparison='reject',
        proposed_incremental_comparison='admit: 10 <= 14.4 and 18 <= 21.6',
        note='Arithmetic reproduction of gate semantics; not a full solver reproduction.')
    with execution_scope(dict(options, ram_budget_gib=12)), \
         patch.object(solver, '_detect_available_gb', return_value=0.):
        values['known_zero_available_with_explicit_12_gib_cap'] = solver._solve_memory_limit_gb()
    for available in (31., 24., .25, 0.):
        with patch.object(scheduler, 'detect_memory_gb', return_value=32.), \
             patch.object(scheduler, 'detect_available_memory_gb', return_value=available):
            values['local_driver_32_installed_{}_available'.format(available)] = dict(
                budget_gib=scheduler.local_memory_budget_gb(.75)[0], target_gib=.9*available)
    import psutil
    with patch.object(psutil,'virtual_memory',return_value=SimpleNamespace(available=0)), \
         patch.object(scheduler,'detect_memory_gb',return_value=32.):
        values['local_driver_actual_zero_probe'] = dict(
            detected_available_gib=scheduler.detect_available_memory_gb(),
            budget_gib=scheduler.local_memory_budget_gb(.75)[0],
            note='The current scheduler maps a successful zero reading to unknown, bypassing the live availability clamp.')
    return values


def spool_accounting():
    import numpy as np
    from ghost_backend.compressed.polarization_cache import build_pair
    from ghost_backend.compressed.factor import CompressedFactor
    from ghost_backend.execution.options import execution_scope
    class Exact:
        dropped_routes=0
        def __init__(self):
            self.n=64;self.calls=self.entries=0
            rng=np.random.RandomState(42)
            self.a=10*np.eye(self.n,dtype=complex)+rng.normal(size=(self.n,self.n))
        def get_with_error(self,rows,cols):
            value=self.a[np.ix_(rows,cols)].copy()
            self.calls+=1;self.entries+=value.size
            return value,np.zeros(value.shape)
    source=Exact()
    class Pair:
        oracles=(source,source)
        def get_with_error(self,rows,cols):
            return [source.get_with_error(rows,cols) for _ in range(2)]
    scratch=HERE/'scratch';scratch.mkdir(exist_ok=True)
    with execution_scope(dict(factorization='compressed',assembly_threads=1,blas_threads=1)), \
         tempfile.TemporaryDirectory(dir=scratch) as directory:
        first,partner=build_pair(Pair(),np.arange(64)[:,None],tile=16,budget=1024**2,spool_directory=directory)
        try:
            first.reserved_partner_bytes=partner.bytes  # same assignment as runtime.regional
            with patch.object(CompressedFactor,'_fresh_build',return_value=None):
                factor=CompressedFactor(first,storage_budget_bytes=1024**2,check_precision=False)
            assert all(value is None for value in partner.tiles.values())
            assert partner.spool_bytes>0 and not partner.loaded
            result=dict(operator_bytes=first.bytes,partner_charged_bytes=partner.bytes,
                partner_spooled_payload_bytes=partner.spool_bytes,
                partner_numeric_metadata_bytes=partner.bytes-partner.spool_bytes,
                partner_payload_arrays_resident=0,
                factor_inverse_allowance_bytes=factor.budget,
                note='The retained-storage cap charges disk payload too. This is a conservative policy, not an RSS measurement. Reload must be readmitted before removing this charge.')
            partner.load()
            np.testing.assert_allclose(partner.matmul(np.eye(64)),source.a,rtol=1e-12,atol=1e-12)
            result['reload_numerically_verified']=True
            return result
        finally:
            partner.close()


if __name__ == '__main__':
    records, hashes = historical()
    output = dict(reproductions=reproductions(), spool_accounting=spool_accounting(), historical=records,
        limitations=['Synthetic budget probes allocate no large arrays and do not establish numerical feasibility.',
                    'Historical maximum forecast and whole-run RSS peak need not occur in the same phase.',
                    'RSS and Windows private commit are different quantities; neither ratio is an error bound.',
                    'No 90%-RAM stress run or new large-geometry solve was performed by this script.'])
    (HERE/'evidence.json').write_text(json.dumps(output, indent=2)+'\n')
    (HERE/'input_hashes.json').write_text(json.dumps(hashes, indent=2)+'\n')
    print(json.dumps(output['reproductions'], indent=2))
    print('Historical records:',len(records))
    for r in records:
        if r['status']=='passed' and r['comparable_fixed_compressed']:
            print(r['study'],r['run'],'forecast/RSS/private GiB:',
                  *(round(r[k],3) for k in ('forecast_peak_gib','observed_tree_rss_gib','observed_tree_private_commit_gib')))
