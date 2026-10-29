"""Polynomial junction corrections must remove resonances without changing fields."""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import hankel2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.twod.formulations.combined_regions import _segment_green
from test_2d_resonance_2026_10_16 import (
    td, partial_coating, split_disk, _frequency_ghz, RADIUS,
    PARTIAL_RESONANCE_KA, sigma_dielectric_cylinder,
)


@pytest.mark.parametrize('degree', [2, 3])
@pytest.mark.parametrize('point', [(0., 0.), (.7, 0.), (.23, .01), (1., .4)])
def test_junction_derivative_integral(degree, point):
    # Independent adaptive integration of explicit Lagrange polynomials,
    # including both singular endpoints and a near-panel observation point.
    nodes = [0., 1.] + [i / degree for i in range(1, degree)]
    expected = []
    for j, node in enumerate(nodes):
        polynomial = np.poly1d([1.])
        for l, other in enumerate(nodes):
            if l != j:
                polynomial *= np.poly1d([1., -other]) / (node - other)
        derivative = polynomial.deriv()
        def integrand(t):
            r = np.hypot(.7*t-point[0], point[1])
            return .25j*hankel2(0, (8.-.1j)*r)*derivative(t)
        expected.append(quad(lambda t: integrand(t).real, 0, 1, epsabs=1e-11)[0]
                        + 1j*quad(lambda t: integrand(t).imag, 0, 1, epsabs=1e-11)[0])
    actual = _segment_green((0., 0.), (.7, 0.), point, 8.-.1j, derivative_degree=degree)
    np.testing.assert_allclose(actual, expected, atol=2e-10, rtol=2e-9)
    assert abs(sum(actual)) < 1e-13


def solve(shape, pol, ka, degree, factorization='dense'):
    result = td.solve_monostatic_rcs_2d_single_polarization(
        shape, [_frequency_ghz(ka)], [0., 90.], pol, geometry_units='meters',
        compute_condition_number=True, strict_quality_gate=False,
        execution_options=dict(basis_order=degree, mesh_strategy='global',
                               factorization=factorization, assembly_threads=1, blas_threads=1))
    amplitude = np.array([complex(s['rcs_amp_real'], s['rcs_amp_imag']) for s in result['samples']])
    return amplitude, result


@pytest.mark.parametrize('degree', [2, 3])
@pytest.mark.parametrize('pol', ['TE', 'TM'])
def test_polynomial_split_disk_at_interior_resonance(degree, pol):
    _, result = solve(split_disk(), pol, 2.4048, degree)
    exact = sigma_dielectric_cylinder(RADIUS, 4., 1., _frequency_ghz(2.4048)*1e9, pol)
    assert abs(result['samples'][0]['rcs_linear']/exact - 1) < .02
    assert result['metadata']['condition_est_max'] < 1e4
    assert 'exterior closed by open-junction arcs' in result['metadata']['formulation']


@pytest.mark.parametrize('degree', [2, 3])
@pytest.mark.parametrize('pol', ['TE', 'TM'])
def test_polynomial_partial_coating_matches_reference_and_compressed(degree, pol):
    amplitude, result = solve(partial_coating(panels=1), pol, PARTIAL_RESONANCE_KA, degree)
    reference, _ = solve(partial_coating(panels=4), pol, PARTIAL_RESONANCE_KA, 1)
    compressed, compressed_result = solve(partial_coating(panels=1), pol, PARTIAL_RESONANCE_KA,
                                          degree, 'compressed')
    assert result['metadata']['condition_est_max'] < 1e4
    assert np.max(abs(amplitude-reference))/np.max(abs(reference)) < .01
    assert 'compressed' in compressed_result['metadata']['solver_method']
    np.testing.assert_allclose(compressed, amplitude, rtol=1e-6, atol=1e-9)
