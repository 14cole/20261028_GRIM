"""Physical invariants of weighted BoR junctions, including invisible partitions."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.bor import solver as bor
from ghost_backend.validation.sphere import sigma_coated_pec_sphere


FREQUENCY = 1e9
ANGLES = np.array([0., 35., 70., 90., 110., 145., 180.])
MEDIUM = (3. - .1j, 1.)


def channels(result):
    return np.array([result['amp_vv'], result['amp_hh']])


def relative_change(actual, reference):
    return float(np.max(abs(actual-reference)) / np.max(abs(reference)))


def split_sphere(elements=16, core=False, media=(MEDIUM, MEDIUM)):
    outer = bor.sphere_generatrix(.06, elements)
    half = elements // 2
    wall_count = max(2, elements // (8 if core else 4))
    wall = np.column_stack((np.linspace(.04 if core else 0., .06, wall_count+1),
                            np.zeros(wall_count+1)))
    surfaces = [(outer[:half+1], False), (outer[half:], False), (wall, False)]
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1), (1, 1)]),
               dict(medium=media[0], bounds=[(0, -1), (2, 1)]),
               dict(medium=media[1], bounds=[(1, -1), (2, -1)])]
    if core:
        inner = bor.sphere_generatrix(.04, elements)
        surfaces += [(inner[:half+1], True), (inner[half:], True)]
        regions[1]['bounds'].append((3, 1))
        regions[2]['bounds'].append((4, 1))
    return surfaces, regions


def reordered(surfaces, regions, order):
    inverse = {old: new for new, old in enumerate(order)}
    return ([surfaces[index] for index in order],
            [dict(region, bounds=[(inverse[index], sign) for index, sign in region['bounds']])
             for region in regions])


def solve_layout(surfaces, regions, backend='dense', **kwargs):
    return bor.solve_bor_banded_multiregion(
        surfaces, regions, FREQUENCY, ANGLES, workers=2,
        bor_options=dict(factorization=backend), **kwargs)


def test_invisible_partition_keeps_surface_order_and_mirror_symmetry():
    surfaces, regions = split_sphere()
    reference = channels(bor.solve_bor_dielectric(
        bor.sphere_generatrix(.06, 16), FREQUENCY, ANGLES, *MEDIUM,
        workers=2, bor_options=dict(factorization='dense')))
    original = channels(solve_layout(surfaces, regions))
    # Independent half-hat phi traces add DOFs, so compare accuracy rather
    # than demanding an identical discretization of the unsplit sphere.
    assert relative_change(original, reference) < 8e-4
    np.testing.assert_allclose(original, original[:, ::-1], rtol=2e-10, atol=2e-13)
    for order in ([1, 0, 2], [2, 1, 0]):
        actual = channels(solve_layout(*reordered(surfaces, regions, order)))
        np.testing.assert_allclose(actual, original, rtol=2e-10, atol=2e-13)


def test_identical_bands_converge_to_the_exact_coated_sphere():
    exact = sigma_coated_pec_sphere(.04, .06, *MEDIUM, FREQUENCY)
    errors = []
    for elements in (16, 32):
        result = solve_layout(*split_sphere(elements, core=True))
        amplitude = channels(result)
        errors.append(float(np.max(abs(10*np.log10(4*np.pi*abs(amplitude)**2/exact)))))
        assert result['mode_converged']
        assert result['linear_backward_error'] < 1e-12
        assert result['warnings'] == []
        np.testing.assert_allclose(amplitude, amplitude[:, ::-1], rtol=2e-10, atol=2e-13)
    # Previously 0.405/0.384 dB: refinement certified a wrong limiting field.
    assert errors[0] < .03
    assert errors[1] < .008
    assert errors[0] / errors[1] > 3.


@pytest.mark.parametrize('backend', ['dense', 'compressed'])
def test_unequal_bands_are_invariant_under_surface_and_region_relabeling(backend):
    surfaces, regions = split_sphere(12, core=True,
                                    media=((2.5-.08j, 1.-.01j), (4.-.2j, 1.1-.03j)))
    reference = channels(solve_layout(surfaces, regions))
    other_surfaces, other_regions = reordered(surfaces, regions, [4, 2, 1, 3, 0])
    # Change numeric region IDs as well, including the exterior's index.
    actual = channels(solve_layout(other_surfaces, other_regions[::-1], backend))
    np.testing.assert_allclose(actual, reference, rtol=2e-8, atol=2e-11)


def test_mirroring_unequal_bands_reverses_the_complex_pattern():
    surfaces, regions = split_sphere(16, core=True,
                                    media=((2.5-.08j, 1.-.01j), (4.-.2j, 1.1-.03j)))
    reference = channels(solve_layout(surfaces, regions))
    # Reflection reverses traversal; reverse the chain to preserve its
    # outward normal and retain the same regional signs/material identities.
    mirrored = [(points[::-1]*[1., -1.], conductor) for points, conductor in surfaces]
    actual = channels(solve_layout(mirrored, regions))
    np.testing.assert_allclose(actual, reference[:, ::-1], rtol=2e-9, atol=2e-12)


@pytest.mark.parametrize('conductor', [False, True])
def test_two_piece_continuation_preserves_the_unsplit_nodal_basis(conductor):
    points = bor.sphere_generatrix(.04, 16)
    surfaces = [(points[:9], conductor), (points[8:], conductor)]
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1), (1, 1)])]
    if conductor:
        whole = bor.solve_bor(points, FREQUENCY, ANGLES, formulation='efie',
                              workers=2, bor_options=dict(factorization='dense'))
    else:
        regions.append(dict(medium=MEDIUM, bounds=[(0, -1), (1, -1)]))
        whole = bor.solve_bor_dielectric(points, FREQUENCY, ANGLES, *MEDIUM,
                                         workers=2, bor_options=dict(factorization='dense'))
    split = solve_layout(surfaces, regions)
    np.testing.assert_allclose(channels(split), channels(whole), rtol=1e-7, atol=2e-11)


@pytest.mark.parametrize('backend', ['dense', 'compressed'])
def test_closed_core_cfie_keeps_its_relative_electric_and_magnetic_weights(backend):
    outer, inner = bor.sphere_generatrix(.06, 16), bor.sphere_generatrix(.04, 12)
    expected = bor.solve_bor_coated_pec(outer, inner, FREQUENCY, ANGLES, *MEDIUM,
                                       workers=2, bor_options=dict(factorization='dense'))
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1)]),
               dict(medium=MEDIUM, bounds=[(0, -1), (1, 1)])]
    actual = solve_layout([(outer, False), (inner, True)], regions, backend)
    assert actual['combined_core_surfaces'] == [1]
    np.testing.assert_allclose(channels(actual), channels(expected), rtol=2e-8, atol=2e-11)


def partial_geometry(elements=12):
    theta = np.linspace(0., np.pi/2, elements+1)
    radius = .04*(1.+.2*np.sin(2*theta))
    interface = np.column_stack((radius*np.sin(theta), radius*np.cos(theta)))
    core = bor.sphere_generatrix(.04, 2*elements)
    return interface, core[:elements+1], core[elements:]


@pytest.mark.parametrize('backend', ['dense', 'compressed'])
def test_partial_coating_matches_general_regional_equations(backend):
    interface, covered, bare = partial_geometry()
    regions = [dict(medium=None, exterior=True, bounds=[(0, 1), (2, 1)]),
               dict(medium=MEDIUM, bounds=[(0, -1), (1, 1)])]
    general = solve_layout([(interface, False), (covered, True), (bare, True)], regions)
    partial = bor.solve_bor_partial_coating(
        interface, covered, [bare], FREQUENCY, ANGLES, *MEDIUM, workers=2,
        bor_options=dict(factorization=backend))
    np.testing.assert_allclose(channels(partial), channels(general), rtol=2e-8, atol=2e-11)


def test_vacuum_partial_coating_is_invisible():
    errors = []
    for elements in (16, 32):
        interface, covered, bare = partial_geometry(elements)
        partial = bor.solve_bor_partial_coating(
            interface, covered, [bare], FREQUENCY, ANGLES, 1., 1., workers=2,
            bor_options=dict(factorization='dense'))
        core = bor.solve_bor(np.vstack((covered, bare[1:])), FREQUENCY, ANGLES,
                             formulation='efie', workers=2,
                             bor_options=dict(factorization='dense'))
        errors.append(relative_change(channels(partial), channels(core)))
    # The added interface/half-hat traces change the finite discretization,
    # but their effect must vanish as the invisible partition is refined.
    assert errors[0] < 7e-4
    assert errors[1] < 1e-4
    assert errors[0] / errors[1] > 3.
