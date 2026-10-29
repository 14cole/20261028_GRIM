"""Exploratory mesh ownership, isolation from production, and real solver export."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.execution.options import execution_scope, validate_options
from ghost_backend.runs.exploratory import select_exploratory_mesh
from ghost_backend.twod import geometry as g


def square(n=1):
    points = [(0., 0.), (0., .3), (.3, .3), (.3, 0.), (0., 0.)]
    return dict(title='exploratory square', ibcs=[], dielectrics=[], segments=[dict(
        name='square', seg_type=2, properties=['2', str(n), '0', '0', '0'],
        point_pairs=[dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1])
                     for a, b in zip(points, points[1:])])])


def panels(snapshot, options=None):
    with execution_scope(validate_options(options or {})):
        return g._build_panels(snapshot, 1., g.C0 / 1e9)


def test_fixed_count_bypasses_floor_only_in_exploratory_scope():
    source = square()
    before = deepcopy(source)
    with pytest.raises(ValueError, match='under-resolves'):
        panels(source)
    mesh, options, record = select_exploratory_mesh(
        source, 1., mesh_mode='geometry', mesh_grading=False)
    actual = panels(mesh, options)
    assert len(actual) == 4
    assert all(p.length == pytest.approx(.3) for p in actual)
    assert source == before
    assert record['convergence_owner'] == 'user'
    with pytest.raises(ValueError, match='under-resolves'):
        panels(source)


def test_density_and_order_preserve_primitives_without_adaptation():
    source = square()
    source['_2d_hp_coarsening'] = 8.
    source['_2d_certification_refinement_factor'] = 2.
    for mode in ('global',):
        with patch('ghost_backend.twod.adaptive_geometry.candidate_meshes', side_effect=AssertionError):
            mesh, options, record = select_exploratory_mesh(
                source, 1., mesh_mode=mode, panels_per_wavelength=2,
                basis_order=3, mesh_grading=False)
        assert '_2d_hp_coarsening' not in mesh
        assert '_2d_certification_refinement_factor' not in mesh
        assert options['basis_order'] == 3
        assert options['mesh_strategy'] == mode
        assert record['geometry_n'] == ['-2']
        assert mesh['segments'][0]['point_pairs'] == source['segments'][0]['point_pairs']
        assert source['segments'][0]['properties'][1] == '1'
        assert len(panels(mesh, options)) == 8


def test_grading_is_explicit_and_defaults_stay_enabled():
    mesh, options, _ = select_exploratory_mesh(
        square(8), 1., mesh_mode='geometry', mesh_grading=False)
    uniform = panels(mesh, options)
    graded = panels(mesh, dict(options, mesh_grading=True))
    assert len(uniform) == 32
    assert len(graded) > len(uniform)
    assert validate_options({})['mesh_grading'] is True
    assert validate_options({})['enforce_mesh_density'] is True


@pytest.mark.parametrize('kwargs', [
    dict(mesh_mode='global', panels_per_wavelength=0),
    dict(mesh_mode='global', panels_per_wavelength=2.5),
    dict(mesh_mode='local'),
    dict(mesh_mode='fixed'),
    dict(mesh_mode='geometry', basis_order=4),
    dict(mesh_mode='geometry', mesh_grading='off'),
    dict(mesh_mode='geometry', execution_overrides={'mesh_strategy': 'adaptive'}),
    dict(mesh_mode='certification_base', basis_order=2),
])
def test_invalid_controls_are_not_silently_ignored(kwargs):
    with pytest.raises(ValueError):
        select_exploratory_mesh(square(), 1., **kwargs)


@pytest.mark.parametrize('mode', ['geometry', 'certification_base', 'certification_fine'])
def test_legacy_modes_still_select_one_candidate(mode):
    mesh, options, record = select_exploratory_mesh(square(-10), 1., mesh_mode=mode)
    assert options['mesh_strategy'] != 'adaptive'
    assert not record['certification_performed']
    assert mesh['segments']


def test_high_order_presets_keep_their_order_without_forced_grading():
    from ghost_backend.execution.options import execution_scope
    for mode, order in [('certification_base', 2), ('certification_fine', 3)]:
        mesh, options, record = select_exploratory_mesh(
            square(-20), 10., mesh_mode=mode, geometry_units='meters', mesh_grading=False)
        assert record['basis_order'] == order
        assert record['higher_order_candidate']
        with execution_scope(options):
            actual = g._build_panels(mesh, 1., g.C0 / 10e9)
        lengths = [p.length for p in actual]
        assert max(lengths) == pytest.approx(min(lengths))


@pytest.mark.parametrize('factorization', ['dense', 'adaptive', 'compressed'])
def test_real_single_mesh_solve_keeps_deliberately_coarse_count(factorization):
    from ghost_backend.twod.solver import solve_monostatic_rcs_2d
    mesh, options, _ = select_exploratory_mesh(
        square(2), 1., mesh_mode='geometry',
        mesh_grading=False, basis_order=2, factorization=factorization,
        execution_overrides=dict(assembly_threads=1, blas_threads=1))
    result = solve_monostatic_rcs_2d(
        mesh, [1.], [0., 45., 90.], geometry_units='meters',
        strict_quality_gate=False, compute_condition_number=False,
        execution_options=options, solver_method='auto')
    assert result['metadata']['panel_count'] == 8
    assert result['metadata']['polynomial_degree'] == 2
    assert not result['metadata'].get('mesh_convergence_certified', False)
    assert len(result['samples']) == 6


def test_driver_exports_each_frequency_even_when_quality_gate_fails(tmp_path, monkeypatch):
    from ghost_backend import run_local_monostatic_exploratory as driver
    from ghost_backend.geometry.io import save_snapshot_geo
    from ghost_backend.twod import solver
    from ghost_backend.io.grim import export_result_to_grim
    geometry = tmp_path / 'square.geo'
    save_snapshot_geo(square(2), str(geometry))
    for key, value in dict(GEOMETRY_FILE=str(geometry), OUTPUT_DIR=str(tmp_path / 'results'),
                           GEOMETRY_UNITS='meters', FREQUENCIES_GHZ=list(np.arange(1., 1.1+1e-6, .1)),
                           AZIMUTHS_DEG=list(np.arange(0., 360.+1e-6, 1.)), MESH_MODE='geometry',
                           MESH_GRADING=False, FACTORIZATION='dense').items():
        monkeypatch.setattr(driver, key, value)
    with patch.object(solver, 'evaluate_quality_gate', return_value=dict(passed=False, reason='test failure')), \
         patch('ghost_backend.io.grim.export_result_to_grim', wraps=export_result_to_grim) as export:
        folder = driver.main()
    assert len(list(folder.glob('*.grim'))) == 2
    settings = json.loads((folder / 'requested_settings.json').read_text())
    assert settings['MESH_GRADING'] is False
    assert settings['AZIMUTHS_DEG'] == list(range(361))
    assert not {'RAM_BUDGET_GIB', 'ASSEMBLY_THREADS', 'BLAS_THREADS',
                'RHS_COMPRESSION', 'COMPRESSED_STORAGE_MIB'} & settings.keys()
    assert export.call_count == 2
    for call in export.call_args_list:
        result = call.args[0]
        assert not result['metadata']['quality_gate']['passed']
        assert result['metadata']['convergence_owner'] == 'user'
        assert result['metadata']['panel_count'] == 8
        assert len(result['samples']) == 722
