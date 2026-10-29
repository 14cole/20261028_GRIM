"""Check review claims without changing production code or admission policy."""
import json
import os
from pathlib import Path
import sys
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / 'Codex_audit/followups_20261029'
sys.path[:0] = [str(ROOT.parent), str(ROOT / 'tests')]
os.environ.update(OPENBLAS_NUM_THREADS='4', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4',
                  GHOST_TIMING_CACHE_DIR=str(HERE / 'timing_cache'))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def saved_evidence():
    rows = []
    for name in ('learned_hint', 'metal_inlet_15ghz_auto', 'narrow_inlet_15ghz_auto'):
        metadata = read(PRIOR / 'benchmarks' / name / 'metadata.json')
        result = read(PRIOR / 'benchmarks' / name / 'result.json')
        steps = metadata['adaptive_mesh']['steps']
        rows.append(dict(name=name, steps=[{k: s[k] for k in
            ('polynomial_degree', 'panels', 'nodes', 'seconds', 'backend')} for s in steps],
            first_two_step_seconds=sum(s['seconds'] for s in steps[:2]),
            solve_seconds=result['solve_seconds'],
            panel_growth=steps[-1]['panels'] / steps[0]['panels'],
            final_vs_initial_cubic_nodes=steps[-1]['nodes'] / steps[1]['nodes']))
    loss = read(PRIOR / 'loss_study_refined.json')
    return dict(adaptive_runs=rows, inverse_to_full_operator_rank=[dict(
        loss_multiplier=r['loss_multiplier'], polarization=r['polarization'],
        ratio=r['inverse_rank']/r['operator_rank']) for r in loss],
        triple_moderate_dielectric=dict(initial_unknowns=17424, scenario_unknowns=3*17424,
            one_complex128_dense_matrix_gib=16*(3*17424)**2/1024**3,
            scope='Arithmetic scenario only, not a refined mesh forecast or numerical solve.'))


def scope_probe(entry_name, mesh_strategy='global'):
    from test_experimental_cpu import fixture
    from ghost_backend.twod import solver
    from ghost_backend.compressed import preconditioner_hints as hints
    import ghost_backend.compressed.factor as factor_module
    from ghost_backend.execution.options import validate_options
    events = []
    original = hints.try_build

    def observe(factor):
        state = hints._CURRENT.get()
        row = dict(scope_identity=state['identity'].hex() if state else None,
                   enabled=bool(state and state['enabled']),
                   records_before=len(state['entries']) if state else 0,
                   polarization=getattr(factor.a.oracle, 'pol', None),
                   key=list(hints._key(factor) or ()), unknowns=factor.a.n,
                   frequency_ghz=round(float(factor.a.oracle.k0)*solver.C0/(2*3.141592653589793*1e9), 9))
        accepted = original(factor)
        row['accepted'] = accepted
        events.append(row)
        return accepted

    options = validate_options(dict(factorization='compressed', mesh_strategy=mesh_strategy, basis_order=1,
        assembly_threads=2, blas_threads=2, ram_budget_gib=8, rhs_compression='off'))
    # Force a qualifying starting tolerance solely to exercise hint reuse on a
    # small fixture. Accuracy gates stay unchanged; this is not a timing trial.
    with mock.patch.dict(os.environ, {'GHOST_HMATRIX_MIN_UNKNOWNS':'100'}), \
         mock.patch.object(factor_module, 'PRECONDITIONER_TOLERANCE', 1e-10), \
         mock.patch.object(hints, 'try_build', side_effect=observe):
        result = getattr(solver, entry_name)(geometry_snapshot=fixture('lossy', 192),
            frequencies_ghz=[.6, .8], elevations_deg=[0., 37., 90.], geometry_units='meters',
            solver_method='experimental_cpu', execution_options=options)
    identities = list(dict.fromkeys(e['scope_identity'] for e in events))
    assert len(identities) >= 2 and all(e['enabled'] for e in events), events
    frequency_scopes = {f: {e['scope_identity'] for e in events if e['frequency_ghz'] == f} for f in (.6,.8)}
    assert all(frequency_scopes.values()) and frequency_scopes[.6].isdisjoint(frequency_scopes[.8])
    for identity in identities:
        local = [e for e in events if e['scope_identity'] == identity]
        assert local[0]['records_before'] == 0 and not local[0]['accepted'], local
        assert any(e['accepted'] for e in local), local
    assert hints._CURRENT.get() is None
    assert result['metadata']['quality_gate']['passed']
    if entry_name.endswith('_certified'):
        assert result['metadata']['mesh_convergence_certified']
    return dict(entry=entry_name, mesh_strategy=mesh_strategy, status='passed', frequencies=[.6,.8],
        probe_only_starting_tolerance=1e-10, events=events, distinct_scope_identities=len(identities),
        request_state_discarded=True, quality_passed=result['metadata']['quality_gate']['passed'],
        mesh_certified=result['metadata'].get('mesh_convergence_certified', False))


if __name__ == '__main__':
    evidence = saved_evidence()
    evidence['direct_multifrequency_probes'] = []
    evidence['probe_development_note'] = ('The first probe incorrectly required exactly two scope identities '
        'for global certification. Global certification changes the physical snapshot on its reference '
        'refinement, so it correctly creates four independent enabled identities. The probe now checks '
        'frequency isolation and within-scope reuse, with separate adaptive certification coverage.')
    for name, strategy in (('solve_monostatic_rcs_2d', 'global'),
                           ('solve_monostatic_rcs_2d_certified', 'global'),
                           ('solve_monostatic_rcs_2d_certified', 'adaptive')):
        evidence['direct_multifrequency_probes'].append(scope_probe(name, strategy))
        (HERE / 'verification.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(name + ' (' + strategy + '): passed', flush=True)
