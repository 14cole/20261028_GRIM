"""Independent field and input regressions from the second GHOST audit."""
import copy
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.twod import geometry as g, solver as td


OPTIONS = dict(factorization='dense', mesh_strategy='global', assembly_threads=2, blas_threads=2)
ANGLES = [0., 15., 37., 60., 90.]


def sheet(z=-15j, n=0):
    return dict(segments=[dict(name='reactive_strip', seg_type=1,
        properties=['1', str(n), '1', '0', '0'],
        point_pairs=[dict(x1=-.15, y1=0., x2=.15, y2=0.)])], dielectrics=[],
        ibcs=[['1', 'constant', str(z.real), str(z.imag), '0', '0']])


def field(rows):
    return np.array([complex(r['rcs_amp_real'], r['rcs_amp_imag']) for r in rows])


@pytest.mark.parametrize('strategy,backend', [
    ('global', 'dense'), ('adaptive', 'dense'), ('global', 'compressed')])
def test_transmitting_sheet_certificate_matches_refined_field(strategy, backend, record_property):
    # Independently refined 1622-panel P1 fields from the audit. The change
    # from 819 panels was 0.00245% of peak; the old certificate was 34.65% off.
    reference = np.array([
        1.8185602175818805 - 1.5876788332086247j,
        1.3758120475446702 - 1.6182692911763545j,
        -.3427440007393547 - 1.126550678522996j,
        .039050426391313356 + 3.370814490634678j,
        1.1279865530045141 + 13.042433718751676j,
    ])
    result = td.solve_monostatic_rcs_2d_certified(
        sheet(), [1.], ANGLES, geometry_units='meters', max_panels=1600,
        execution_options=dict(OPTIONS, mesh_strategy=strategy, factorization=backend))
    assert result['metadata']['mesh_convergence_certified']
    records = result['metadata']['surface_wave_sampling']
    assert records and all(row['resolved'] for row in records)
    assert {row['polarization'] for row in records} == {'TM'}
    actual = field(result['co_solved_samples']['HH'])
    error = np.max(abs(actual - reference)) / np.max(abs(reference))
    record_property('peak_relative_field_error', float(error))
    record_property('max_rcs_error_db', float(np.max(abs(20*np.log10(abs(actual)/abs(reference))))))
    record_property('panel_count', result['metadata']['panel_count'])
    assert error < .01


@pytest.mark.parametrize('pol,z,factor', [('TM', -15j, .5), ('TE', 1000j, 2.)])
def test_sheet_dispersion_has_two_sided_factors(pol, z, factor):
    # Flat sheet symbols S=-1/(2*kappa), W=-kappa/2 in the implemented
    # outgoing Green convention, with the respective sheet mass terms.
    kappa = factor * (g.ETA0 / abs(z) if pol == 'TM' else abs(z) / g.ETA0)
    expected = np.sqrt(1. + kappa*kappa)
    index = g._bound_surface_wave_index(z, polarization=pol, transmitting_sheet=True)
    assert index == pytest.approx(expected)
    assert g._bound_surface_wave_index(-z, polarization=pol, transmitting_sheet=True) == 0.
    materials = g.MaterialLibrary.from_entries(sheet(z)['ibcs'], [], '.')
    assert g._segment_surface_wave_index(materials, 1, 1, 0, 1., pol) == pytest.approx(expected)


def test_te_sheet_field_converges_with_its_distinct_wave_law():
    result = td.solve_monostatic_rcs_2d_certified_single_polarization(
        sheet(1000j), [1.], ANGLES, 'TE', geometry_units='meters', execution_options=OPTIONS)
    refined = td.solve_monostatic_rcs_2d_single_polarization(
        sheet(1000j, n=800), [1.], ANGLES, 'TE', geometry_units='meters', execution_options=OPTIONS)
    assert result['metadata']['surface_wave_sampling'][0]['resolved']
    reference = field(refined['samples'])
    assert np.max(abs(field(result['samples']) - reference)) / np.max(abs(reference)) < .02


def test_sparse_sheet_cannot_certify_and_bistatic_records_sampling():
    with pytest.raises(ValueError, match='unresolved bound surface-wave sampling'):
        td.solve_monostatic_rcs_2d_certified(sheet(n=20), [1.], ANGLES,
            geometry_units='meters', execution_options=OPTIONS)
    result = td.solve_bistatic_rcs_2d(sheet(n=20), [1.], [0.], ANGLES,
        geometry_units='meters', execution_options=OPTIONS)
    assert any(not r['resolved'] for r in result['metadata']['surface_wave_sampling'])
    with pytest.raises(ValueError, match='panel limit|limit is'):
        td.solve_monostatic_rcs_2d_certified(sheet(), [1.], ANGLES,
            geometry_units='meters', execution_options=OPTIONS, max_panels=100)


def test_sheet_density_cap_does_not_silently_disable_sampling():
    shape = sheet(-.1j)
    materials = g.MaterialLibrary.from_entries(shape['ibcs'], [], '.')
    wavelength = g.C0 / 1.e9
    assert g._surface_wave_mesh_wavelength(wavelength, materials, 1, 1, 0, [1.]) == pytest.approx(
        wavelength / g.SURFACE_WAVE_MAX_DENSITY_FACTOR)
    with pytest.raises(ValueError, match='Automatic density is capped'):
        td.solve_monostatic_rcs_2d_certified(shape, [1.], [0.],
            geometry_units='meters', execution_options=OPTIONS)


@pytest.mark.parametrize('eps,mu,z,pol,expected', [
    (-4-.01j, -1-.01j, 30j, 'TM', 12.71594038489585),
    (1., 1-.1j, 100-3j, 'TE', 0.),  # physical transverse field grows
    (1., 1-1j, 1-30j, 'TM', 0.),   # physical attenuation exceeds phase
    (1., 1., 75-20j, 'TM', 0.),
])
def test_physical_medium_decay_and_attenuation(eps, mu, z, pol, expected):
    assert g._bound_surface_wave_index(z, eps, mu, pol) == pytest.approx(expected)


def test_negative_index_coating_certifies_only_with_physical_wave_evidence():
    from ghost_backend.validation.cylinder import sigma_coated_impedance_cylinder
    segments = []
    for radius, kind, ibc in [(.04, 3, 0), (.02, 4, 1)]:
        theta = np.linspace(0., -2*np.pi, 65)
        xy = np.column_stack((radius*np.cos(theta), radius*np.sin(theta)))
        segments.append(dict(name=str(kind), seg_type=kind,
            properties=[str(kind), '0', str(ibc), '1', '0'],
            point_pairs=[dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1])
                         for a,b in zip(xy[:-1], xy[1:])]))
    shape = dict(segments=segments, dielectrics=[['1','-4','-.01','-1','-.01']],
                 ibcs=[['1','constant','0','30','0','0']])
    result = td.solve_monostatic_rcs_2d_certified_single_polarization(
        shape, [1.], [0.,37.,90.], 'TM', geometry_units='meters', execution_options=OPTIONS)
    records = result['metadata']['surface_wave_sampling']
    assert records and all(record['resolved'] for record in records)
    assert records[0]['segments'][0]['phase_index'] > 12.7
    expected = sigma_coated_impedance_cylinder(.02, .04, -4-.01j, -1-.01j, 30j, 1e9, 'TM')
    assert max(abs(10*np.log10(row['rcs_linear']/expected)) for row in result['samples']) < .03


def test_preparation_forwards_cancellation_into_geometry_validation(monkeypatch):
    from ghost_backend.twod.preparation import prepare_geometry
    calls = []
    def cancel_after_entry():
        calls.append(True)
        if len(calls) > 1:
            raise InterruptedError('cancel geometry validation')
    monkeypatch.setattr(td, '_build_panels', lambda *a, **kw: pytest.fail('meshed before cancellation'))
    with pytest.raises(InterruptedError, match='cancel geometry validation'):
        prepare_geometry(sheet(), units='meters', checkpoint=cancel_after_entry)
    assert len(calls) == 2


@pytest.mark.parametrize('kind', ['monostatic', 'bistatic'])
def test_type_header_and_properties_only_inputs_have_identical_both_channel_fields(kind):
    shape = sheet(50-10j, n=50)
    first = shape['segments'][0]
    first['point_pairs'] = [dict(x1=-.1, y1=0., x2=0., y2=0.)]
    second = copy.deepcopy(first)
    second.update(name='right', properties=['1', '50', '2', '0', '0'],
                  point_pairs=[dict(x1=0., y1=0., x2=.05, y2=.05)])
    shape['segments'].append(second)
    shape['ibcs'].append(['2', 'constant', '100', '-20', '0', '0'])
    stripped = copy.deepcopy(shape)
    for segment in stripped['segments']:
        segment.pop('seg_type')
    results = []
    for snapshot in [shape, stripped]:
        args = dict(geometry_units='meters', execution_options=OPTIONS)
        result = (td.solve_monostatic_rcs_2d(snapshot, [1.], ANGLES, **args)
                  if kind == 'monostatic' else
                  td.solve_bistatic_rcs_2d(snapshot, [1.], [0., 45.], ANGLES, **args))
        results.append(result)
    for channel in ('HH', 'VV'):
        np.testing.assert_array_equal(field(results[0]['co_solved_samples'][channel]),
                                      field(results[1]['co_solved_samples'][channel]))


@pytest.mark.parametrize('flag', [900000, 900001, 1000000])
def test_reserved_material_id_fails_before_becoming_air(flag):
    with pytest.raises(ValueError, match='reserved for virtual sheet regions'):
        g.MaterialLibrary.from_entries([], [[str(flag), '4', '-.1', '1', '0']], '.')
    with pytest.raises(ValueError, match='reserved for virtual sheet regions'):
        g.MaterialLibrary({}, {flag: (4-.1j, 1.)})
    materials = g.MaterialLibrary.from_entries([], [['899999', '4', '-.1', '1', '0']], '.')
    assert g._region_medium(materials, 899999, 1.) == (4-.1j, 1.+0j)
    assert g._region_medium(materials, 900000, 1.) == (1.+0j, 1.+0j)
