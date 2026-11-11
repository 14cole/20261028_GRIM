"""Differential worker control-flow fixtures; solvers and artifact I/O are mocked.

Run against a full checkout. This tests adapter ordering, mapped solve arguments,
restart decisions, metadata and failure propagation independently of numerics.
"""
import contextlib
import copy
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'tools/GHOST'))
from ghost_backend.runs.quality import accuracy_target_policy
from ghost_backend.execution.options import validate_options
import ghost_backend.execution.provenance as provenance
import ghost_backend.io.grim as grim_io
import ghost_backend.twod.solver as twod
import ghost_backend.bor.dispatch as bor
import ghost_backend.hpc.scheduler as scheduler
try:
    pipeline = importlib.import_module('ghost_backend.runs.worker_pipeline')
except ModuleNotFoundError:
    pipeline = None

observed = []
for module_name in ('runs.local_twod_driver', 'hpc.twod_driver',
                    'runs.local_bor_driver', 'hpc.bor_driver'):
    driver = importlib.import_module('ghost_backend.' + module_name)
    driver.load_default_settings()
    is_bor = 'bor_driver' in module_name
    cases = ['fresh', 'certified', 'reuse', 'source_before', 'source_after',
             'input_after', 'bad_attestation', 'solver_failure']
    if is_bor:
        cases += ['partial', 'different_channel_digest', 'planned']
    for case in cases:
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            destination = Path(directory)
            events = []
            counts = dict(source=0, input=0)
            snapshot = dict(source_path='fixture.geo', segments=[])
            config = dict(mesh_certification=case == 'certified',
                          mesh_convergence_policy=accuracy_target_policy('standard'),
                          geometry_units='meters', max_panels=1000, cfie_alpha=0.5,
                          n_modes=3, mode_tol=1e-6, max_elements=200, workers_per_unit=1,
                          table_precision='double', assembly='streaming', stream_budget_gb=0.1,
                          bor_execution_options={}, expand_to_360=False)
            context = dict(config, azimuths_deg=[0.0, 90.0], aspects_deg=[0.0, 90.0],
                           execution_options=validate_options(dict(factorization='dense', mesh_strategy='global')),
                           solver_config=config, forecast_peak_gib=2.0)
            unit = dict(geometry='fixture.geo', geometry_stem='fixture', role='FRD',
                        frequency_ghz=1.0, polarization='VV', geometry_input_sha256='same')
            units = [dict(unit, polarization=p) for p in ('VV', 'HH')]
            if case == 'different_channel_digest':
                units[1]['geometry_input_sha256'] = 'different'
            pair = dict(unit, channel_units=units)
            if case == 'planned':
                pair['execution_plan'] = dict(workers=2, table_precision='double',
                                              assembly='streaming', bor_execution_options={})
            output_units = units if is_bor else [unit]
            for index, u in enumerate(output_units):
                if case in ('reuse', 'bad_attestation') or (case == 'partial' and index == 0):
                    path = driver._unit_output_path(destination, u)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'existing')

            def verify_source(_):
                counts['source'] += 1
                events.append(['source', counts['source']])
                if (case == 'source_before' and counts['source'] == 1
                        or case == 'source_after' and counts['source'] == 2):
                    raise RuntimeError('source changed')

            def verify_input(u, _):
                counts['input'] += 1
                events.append(['input', u['polarization'], u['geometry_input_sha256']])
                if case == 'input_after' and counts['source'] == 2:
                    raise RuntimeError('input changed')

            def attestation(_, u):
                return dict(frequency=u['frequency_ghz'], polarization=u['polarization'])

            def verify_attestation(path, expected):
                events.append(['reuse', str(Path(path).relative_to(destination)), expected])
                if case == 'bad_attestation':
                    raise ValueError('attestation mismatch')

            def embed(result, value):
                events.append(['embed', value])
                result['metadata']['attestation'] = value

            def solve(kind, **kwargs):
                events.append(['solve', kind, kwargs])
                if case == 'solver_failure':
                    raise RuntimeError('solver failed')
                return dict(samples=[dict(value=1)],
                            co_solved_samples={'VV': [dict(value=1)], 'HH': [dict(value=2)]},
                            polarizations=['VV', 'HH'], polarization_mapping={'VV': 'TE', 'HH': 'TM'},
                            metadata=dict(warnings=['fixture warning']))

            def export(result, path, **kwargs):
                events.append(['export', str(Path(path).relative_to(destination)), copy.deepcopy(result), kwargs])
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_bytes(b'new')
                return [path]

            stack.enter_context(patch.object(driver, '_verify_run_provenance', verify_source))
            stack.enter_context(patch.object(driver, '_verify_unit_input', verify_input))
            stack.enter_context(patch.object(driver, '_unit_attestation_fields', attestation))
            if hasattr(driver, '_load_snapshot'):
                stack.enter_context(patch.object(driver, '_load_snapshot', lambda _: (snapshot, 'materials')))
            if hasattr(driver, '_manifest_for'):
                stack.enter_context(patch.object(driver, '_manifest_for', lambda _: context))
            for owner in [driver, provenance] + ([pipeline] if pipeline else []):
                if hasattr(owner, 'verify_embedded_attestation'):
                    stack.enter_context(patch.object(owner, 'verify_embedded_attestation', verify_attestation))
                if hasattr(owner, 'embed_output_attestation'):
                    stack.enter_context(patch.object(owner, 'embed_output_attestation', embed))
            stack.enter_context(patch.object(grim_io, 'export_result_to_grim', export))
            stack.enter_context(patch.object(scheduler, 'reset_peak_rss', lambda: True))
            stack.enter_context(patch.object(scheduler, 'peak_rss_gib', lambda: 1.0))
            for owner, prefix in ((twod, 'solve_monostatic_rcs_2d_'), (bor, 'solve_monostatic_rcs_bor_')):
                for suffix in ('survey', 'certified'):
                    stack.enter_context(patch.object(owner, prefix + suffix,
                                                     lambda _kind=prefix+suffix, **kw: solve(_kind, **kw)))
            error = None
            returned = None
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    if module_name == 'hpc.bor_driver':
                        returned = driver._solve_and_export(pair, snapshot, 'materials', directory)
                    else:
                        returned = driver._solve_and_export(pair if is_bor else unit, context, directory)
                except Exception as exc:
                    error = [type(exc).__name__, str(exc)]
            expected_error = case in ('source_before', 'source_after', 'input_after', 'bad_attestation', 'solver_failure')
            assert bool(error) == expected_error, (module_name, case, error)
            if expected_error:
                assert not any(e[0] == 'export' for e in events), (module_name, case, events)
            elif case == 'reuse':
                assert returned[0] == 'skipped' and not any(e[0] == 'solve' for e in events)
            else:
                assert returned[0] == 'written'
            encoded = json.dumps(dict(driver=module_name, case=case, result=returned, error=error, events=events))
            observed.append(json.loads(encoded.replace(directory, '<destination>')))
print(json.dumps(observed, indent=2))
