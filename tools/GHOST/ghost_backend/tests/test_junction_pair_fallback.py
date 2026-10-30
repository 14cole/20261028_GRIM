"""An explicitly requested polynomial pair must preserve junction fields."""
import os
from unittest.mock import patch
import numpy as np
import pytest
from ghost_backend.twod import solver
from ghost_backend.twod.assembly import polynomial_pair as pair
from ghost_backend.tests.test_2d_capability_acceptance import TopologyAcceptanceTests


@pytest.mark.parametrize('backend', ['dense', 'compressed'])
@pytest.mark.parametrize('degree', [2, 3])
def test_optional_pair_matches_independent_junction_fields(backend, degree):
    shape = TopologyAcceptanceTests._partial_coating(8)
    def solve():
        return solver.solve_monostatic_rcs_2d(shape, [.6], [0., 73.], geometry_units='meters',
            execution_options=dict(factorization=backend, mesh_strategy='local', basis_order=degree,
                                   assembly_threads=1, blas_threads=1))
    with patch.dict(os.environ, GHOST_POLYNOMIAL_PAIR='off'):
        reference = solve()
    with patch.dict(os.environ, GHOST_POLYNOMIAL_PAIR='auto'), pair.polynomial_pair_scope(2) as owner:
        actual = solve()
        assert not owner.pending
        if degree == 2:
            assert any('combined material junctions' in e.get('reason', '') for e in owner.evidence)
    for pol in ('VV', 'HH'):
        fields = [np.asarray([complex(r['rcs_amp_real'], r['rcs_amp_imag'])
                             for r in result['co_solved_samples'][pol]]) for result in (reference, actual)]
        np.testing.assert_array_equal(*fields)
