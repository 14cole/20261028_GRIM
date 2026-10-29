"""Independent slab physics, ENZ admissibility, and bound-wave mesh checks."""
import cmath

import numpy as np
import pytest

from ghost_backend.twod import solver as rcs
from ghost_backend.twod.formulations.thin_layer import solve_thin_layer_fields, validate_thin_layer
from ghost_backend.twod.formulations.thin_layer_qualification import (
    local_bulk_reference, planar_scattering, thin_layer_surface_wave_index,
)
from ghost_backend.twod.geometry import _segment_surface_wave_index, _surface_wave_sampling


K0 = 2 * np.pi * 1e9 / rcs.C0


def fresnel_slab(eps, mu, d, pol, angle):
    """Independent two-interface multiple-reflection sum at centered planes."""
    beta = mu if pol == 'TM' else eps
    theta = np.deg2rad(angle)
    q0 = np.cos(theta)
    q1 = cmath.sqrt(eps * mu - np.sin(theta)**2)
    r01 = (q0 - q1 / beta) / (q0 + q1 / beta)
    phase = cmath.exp(-1j * K0 * q1 * d)
    denominator = 1 - r01**2 * phase**2
    front_r = r01 * (1 - phase**2) / denominator
    front_t = (1 - r01**2) * phase / denominator
    shift = cmath.exp(1j * K0 * q0 * d)
    return np.array([front_r * shift, front_t * shift])


@pytest.mark.parametrize('eps,mu', [(1, 1), (3-.02j, 1), (2.1-.05j, 1.3-.02j),
                                    (-.02-1e-6j, 1), (.25-.001j, 1)])
@pytest.mark.parametrize('pol', ['TM', 'TE'])
def test_centered_exact_bulk_transfer_matches_independent_fresnel(eps, mu, pol):
    angles = [0., 37., 70., 89., 89.999]
    _, exact = planar_scattering(eps, mu, .0005, K0, pol, angles)
    expected = [fresnel_slab(eps, mu, .0005, pol, angle) for angle in angles]
    np.testing.assert_allclose(exact, expected, rtol=1.e-9, atol=3.e-12)


@pytest.mark.parametrize('pol', ['TM', 'TE'])
def test_lossless_sheet_and_exact_slab_preserve_power(pol):
    sheet, bulk = planar_scattering(3, 1.3, .001, K0, pol, [0., 35., 80., 89.999])
    np.testing.assert_allclose(np.sum(abs(sheet)**2, axis=1), 1., atol=2.e-14)
    np.testing.assert_allclose(np.sum(abs(bulk)**2, axis=1), 1., atol=2.e-14)


def test_jump_scattering_survives_singular_equivalent_transfer():
    # det(I-J/2)=0 (B*C=-4) is a transfer-coordinate singularity, not a
    # singular scattering problem. Avoid inverting that matrix altogether.
    beta, delta = -1.e-4, .1
    sine_squared = -4. / (delta**2 * (beta - 1.) * (1. - 1. / beta))
    angle = np.rad2deg(np.arcsin(np.sqrt(sine_squared)))
    sheet, bulk = planar_scattering(beta, 1., delta/K0, K0, 'TE', [angle])
    assert np.all(np.isfinite(sheet))
    np.testing.assert_allclose(np.sum(abs(sheet)**2), 1., atol=3.e-14)
    np.testing.assert_allclose(bulk[0], fresnel_slab(beta, 1., delta/K0, 'TE', angle), atol=1.e-13)


def test_propagating_reference_rejects_an_old_electrically_thin_enz_case():
    validate_thin_layer(1.e-6-1.e-9j, 1, .001, K0)
    with pytest.raises(ValueError, match='reflection/transmission mismatch'):
        local_bulk_reference(1.e-6-1.e-9j, 1, .001, K0, 'TE')


@pytest.mark.parametrize('eps,mu,pol', [(-.02-1.e-6j, 1, 'TE'),
                                        (1, -.02-1.e-6j, 'TM')])
def test_guided_slab_comparison_rejects_enz_case_that_propagating_waves_pass(eps, mu, pol):
    validate_thin_layer(eps, mu, .0005, K0)
    sheet, bulk = planar_scattering(eps, mu, .0005, K0, pol, np.linspace(0., 89.999, 361))
    assert np.max(abs(sheet-bulk)) < .001
    with pytest.raises(ValueError, match='guided-mode propagation index'):
        local_bulk_reference(eps, mu, .0005, K0, pol)


def layer_snapshot(eps, d, count):
    theta = np.linspace(0., -2*np.pi, 81)
    points = .08 * np.column_stack((np.cos(theta), np.sin(theta)))
    return dict(segments=[dict(name='layer', seg_type=1,
        properties=['1', str(count), '1', '0', '0'],
        point_pairs=[dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1]) for a, b in zip(points[:-1], points[1:])])],
        ibcs=[['1', 'thin_dielectric', str(d), '2']],
        dielectrics=[['2', str(complex(eps).real), str(complex(eps).imag), '1', '0']])


def layer_mesh(snapshot, automatic):
    materials = rcs.MaterialLibrary.from_entries(snapshot['ibcs'], snapshot['dielectrics'], '.')
    kwargs = dict(materials=materials, frequencies_ghz=[1.]) if automatic else {}
    panels = rcs._build_panels(snapshot, 1., rcs.C0/1e9, **kwargs)
    infos = rcs._build_coupled_panel_info(panels, materials, 1., 'TE', K0)
    mesh = rcs._build_linear_mesh_interface_aware(panels, infos)[0]
    return materials, mesh


def test_unsupported_local_physics_rejects_before_assembly(monkeypatch):
    _, mesh = layer_mesh(layer_snapshot(-.02-1.e-6j, .0005, 1), False)
    def unexpected(*args, **kwargs):
        pytest.fail('Unsupported local thin-layer physics must fail before matrix assembly.')
    monkeypatch.setattr(rcs, '_assemble_linear_operator_matrices', unexpected)
    with pytest.raises(ValueError, match='guided-mode propagation index'):
        solve_thin_layer_fields(mesh, K0, [0.], 'TE', -.02-1.e-6j, 1., .0005)


def test_supported_fast_modes_control_automatic_mesh_and_explicit_sampling():
    eps, d = -.005-1.e-6j, .0001
    evidence = local_bulk_reference(eps, 1., d, K0, 'TE')
    assert evidence['guided_mode_count'] == 2
    assert 4.65 < evidence['maximum_guided_phase_index'] < 4.67
    assert not evidence['all_bulk_modes_searched']
    assert not evidence['global_scattering_error_bounded']
    materials, coarse = layer_mesh(layer_snapshot(eps, d, 1), False)
    index = _segment_surface_wave_index(materials, 1, 1, 0, 1., 'TE')
    assert index == pytest.approx(evidence['maximum_guided_phase_index'])
    assert not _surface_wave_sampling(coarse, materials, 1., 'TE')['resolved']
    materials, automatic = layer_mesh(layer_snapshot(eps, d, 0), True)
    assert len(automatic.elements) > len(coarse.elements)
    assert _surface_wave_sampling(automatic, materials, 1., 'TE')['resolved']
    assert thin_layer_surface_wave_index(1., eps, d, K0, 'TM') == pytest.approx(index)


def test_out_of_domain_truncated_pole_does_not_explode_ordinary_mesh():
    evidence = local_bulk_reference(3., 1., .0005, K0, 'TE')
    assert evidence['excluded_out_of_domain_sheet_mode_count'] == 1
    assert evidence['maximum_guided_phase_index'] < 1.001


def test_cached_evidence_cannot_be_mutated_by_callers():
    evidence = local_bulk_reference(3., 1., .0005, K0, 'TE')
    evidence['maximum_guided_phase_index'] = 1.e9
    assert local_bulk_reference(3., 1., .0005, K0, 'TE')['maximum_guided_phase_index'] < 1.001
