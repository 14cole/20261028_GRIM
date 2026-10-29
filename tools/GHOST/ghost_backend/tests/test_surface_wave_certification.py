"""Bound surface wavelengths must be sampled before mesh deltas certify them."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.execution.options import execution_scope
from ghost_backend.runs.quality import solver_report_text
from ghost_backend.twod import geometry as g, solver as td


OPTIONS = dict(factorization='dense', mesh_strategy='global', assembly_threads=2, blas_threads=2)
ANGLES = [0., 15., 37., 60., 90.]


def square(reactance=-30., n=0, side=.3):
    points = [(0., 0.), (0., side), (side, side), (side, 0.), (0., 0.)]
    return dict(segments=[dict(name='square', seg_type=2,
        properties=['2', str(n), '1', '0', '0'],
        point_pairs=[dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1])
                     for a, b in zip(points[:-1], points[1:])])],
        ibcs=[['1', 'constant', '0', str(reactance), '0', '0']], dielectrics=[])


def certify(shape, **kwargs):
    with execution_scope(OPTIONS):
        return td.solve_monostatic_rcs_2d_certified_single_polarization(
            shape, [1.], ANGLES, 'TM', geometry_units='meters', **kwargs)


def field(result):
    return np.array([complex(row['rcs_amp_real'], row['rcs_amp_imag']) for row in result['samples']])


def test_reactive_square_certifies_a_resolved_field_instead_of_the_early_plateau():
    # Independently refined P1 reference from the 2026-10-20 audit, 2596 panels
    # (640 free-space PPW). Its change from 1316 panels was 0.3913%; the old
    # certified 96/136-panel plateau was 6.485% away from these complex fields.
    reference = np.array([
        .21329007914263476 + 13.018228332439206j,
        -7.366706486165401 + 1.6484361678444461j,
        2.7387536455804398 - 2.4832241515136135j,
        .7740025258593075 - 2.2180176980801907j,
        .21329007914249967 + 13.01822833243923j,
    ])
    result = certify(square())
    metadata = result['metadata']
    assert metadata['mesh_convergence_certified']
    assert metadata['mesh_convergence']['surface_wave_sampling_checked']
    assert metadata['mesh_convergence']['base_panel_count'] > 900
    assert metadata['panel_count'] < 1700
    evidence = metadata['surface_wave_sampling'][0]
    assert evidence['resolved']
    assert evidence['segments'][0]['samples_per_wavelength'] >= 20.
    assert np.max(abs(field(result) - reference)) / np.max(abs(reference)) < .01
    assert 'Bound surface-wave sampling: resolved' in solver_report_text(metadata)


def test_sparse_explicit_mesh_cannot_pass_a_two_mesh_plateau(monkeypatch):
    calls = []
    original = td.solve_monostatic_rcs_2d_single_polarization
    def record(**kwargs):
        calls.append(kwargs['geometry_snapshot'])
        return original(**kwargs)
    monkeypatch.setattr(td, 'solve_monostatic_rcs_2d_single_polarization', record)
    with pytest.raises(ValueError, match='unresolved bound surface-wave sampling.*base mesh'):
        certify(square(n=20))
    assert len(calls) == 1  # reject before paying for an uninformative fine solve


def test_density_cap_remains_finite_and_survey_reports_unresolved_waves():
    shape = square(reactance=-1., side=.003)
    materials = g.MaterialLibrary.from_entries(shape['ibcs'], [], '.')
    wavelength = g.C0 / 1.e9
    assert g._surface_wave_mesh_wavelength(wavelength, materials, 2, 1, 0, [1.]) == pytest.approx(
        wavelength / g.SURFACE_WAVE_MAX_DENSITY_FACTOR)
    result = td.solve_monostatic_rcs_2d_single_polarization(
        shape, [1.], [0.], 'TM', geometry_units='meters', execution_options=OPTIONS)
    metadata = result['metadata']
    evidence = metadata['surface_wave_sampling'][0]
    assert not evidence['resolved']
    assert evidence['segments'][0]['phase_index'] > 300.
    assert metadata['panel_count'] < 100
    assert any('Bound surface waves remain' in warning for warning in metadata['warnings'])
    assert 'Bound surface-wave sampling: unresolved' in solver_report_text(metadata)
    with pytest.raises(ValueError, match='Automatic density is capped'):
        certify(shape)


def test_sampling_evidence_uses_active_polarization_and_bistatic_path():
    shape = square(n=20)
    for pol, expected in [('TM', True), ('TE', False)]:
        result = td.solve_bistatic_rcs_2d_single_polarization(
            shape, [1.], [0.], [0., 90.], pol,
            geometry_units='meters', execution_options=OPTIONS)
        assert bool(result['metadata']['surface_wave_sampling']) is expected
        if expected:
            assert not result['metadata']['surface_wave_sampling'][0]['resolved']
    assert g._bound_surface_wave_index(-30j, polarization='TE') == 0.
    assert g._bound_surface_wave_index(-30j, polarization='TM') > 12.


def test_panel_admission_still_precedes_a_reactive_field_solve():
    with pytest.raises(ValueError, match='panel limit|limit is'):
        certify(square(), max_panels=100)


def test_unresolved_evidence_survives_channel_and_frequency_merges():
    shape = square(n=20)
    result = td.solve_monostatic_rcs_2d(
        shape, [.75, 1.], [0.], geometry_units='meters', execution_options=OPTIONS)
    records = result['metadata']['surface_wave_sampling']
    assert {(row['frequency_ghz'], row['polarization']) for row in records} == {
        (.75, 'TM'), (1., 'TM')}
    assert all(not row['resolved'] for row in records)
    with pytest.raises(ValueError, match='unresolved bound surface-wave sampling.*TM at 0.75'):
        td.solve_monostatic_rcs_2d_certified(
            shape, [.75, 1.], [0.], geometry_units='meters', execution_options=OPTIONS)


def test_sampling_prerequisite_honors_normal_panel_rounding_allowance():
    # One panel can be up to 5% longer than the nominal target. A regular
    # polygon just 0.2% over that target should not suddenly double its mesh
    # or be rejected merely because its actual sampling is just below 20.
    shape = square()
    wave = g.C0 / 1.e9 / g._bound_surface_wave_index(-30j, polarization='TM')
    count = 64
    radius = (wave / 20. * 1.002) / (2. * np.sin(np.pi/count))
    theta = np.linspace(0., -2.*np.pi, count+1)
    points = np.column_stack([radius*np.cos(theta), radius*np.sin(theta)])
    shape['segments'][0]['point_pairs'] = [dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1])
                                         for a, b in zip(points[:-1], points[1:])]
    materials = g.MaterialLibrary.from_entries(shape['ibcs'], [], '.')
    panels = g._build_panels(shape, 1., g.C0/1.e9, materials=materials, frequencies_ghz=[1.])
    assert len(panels) == count
    mesh = g._build_linear_mesh(panels)
    record = g._surface_wave_sampling(mesh, materials, 1., 'TM')['segments'][0]
    assert record['samples_per_wavelength'] == pytest.approx(20./1.002)
    assert record['resolved']


def test_checkpoint_frequency_merge_retains_sampling_records(tmp_path):
    from ghost_backend.twod.checkpoints import FrequencyCheckpoints
    frequencies = [.75, 1.]
    store = FrequencyCheckpoints(tmp_path, 'surface-wave-regression', certified=False)
    for frequency in frequencies:
        result = td.solve_monostatic_rcs_2d(
            square(reactance=-1., side=.003), [frequency], [0.],
            geometry_units='meters', execution_options=OPTIONS)
        store.save(frequency, result)
    # This is the same consuming merge used after checkpointed fresh, resumed,
    # and parallel sweeps. Lists must retain each frequency's own evidence.
    merged = td._merge_frequency_results((store.load(f) for f in frequencies), frequencies)
    records = merged['metadata']['surface_wave_sampling']
    assert {(row['frequency_ghz'], row['polarization']) for row in records} == {
        (.75, 'TM'), (1., 'TM')}
    assert all(not row['resolved'] for row in records)
    assert 'Bound surface-wave sampling: unresolved' in solver_report_text(merged['metadata'])
