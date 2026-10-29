"""Independent sign oracle and public-path phase conversion regressions."""
import numpy as np
import pytest
from ghost_backend.assembly.line_expansion import (
    SeamCoefficients, ELECTRIC_LINE, expand_perimeter, line_phase_mapping,
    LEGACY_PHASE_MAPPING_DEG,
)
from ghost_backend.assembly.fields import sum_features, _signed_seam


def fixture():
    coefficient = SeamCoefficients(1., np.array([0., 90., 180.]),
                                  np.full(3, 1+2j), np.full(3, 3-4j))
    segments = np.array([[[0., 0., 0.], [0., 0., .041]]])
    normals = np.array([[[1., 0., 0.], [1., 0., 0.]]])
    return coefficient, segments, normals


def test_broadside_native_b_sign_and_local_to_radar_polarization():
    c, segments, normals = fixture()
    result = expand_perimeter(segments, c, None, [[1., 0., 0.]], segment_normals=normals)
    # Along z, TM drives radar VV; TE drives radar HH. Standard outgoing G3
    # requires -B_TM and +B_TE times L/(4*pi), independently of implementation.
    np.testing.assert_allclose(result['F_vv'], -(1+2j)*.041/(4*np.pi), atol=2e-17)
    np.testing.assert_allclose(result['F_hh'], (3-4j)*.041/(4*np.pi), atol=2e-17)
    np.testing.assert_allclose(result['F_vh'], 0., atol=2e-17)


@pytest.mark.parametrize('batch', [1, 32])
def test_conversion_once_and_public_api_agree_for_cross_polarized_looks(batch):
    c, segments, normals = fixture()
    segments[0, 1] = [0., .02, .03579106033634656]
    directions = np.column_stack((np.ones(37), np.linspace(-.7,.7,37), np.full(37,.31)))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    converted = c.as_electric_line()
    assert converted.convention == ELECTRIC_LINE
    assert converted.as_electric_line() is converted
    assert _signed_seam(converted, -1).convention == ELECTRIC_LINE
    expected = expand_perimeter(segments, c, None, directions, segment_normals=normals,
                                _look_batch_size=batch)
    actual = expand_perimeter(segments, converted, None, directions, segment_normals=normals,
                              _look_batch_size=batch)
    assert np.max(abs(expected['F_vh'])) > 1e-5
    for key in expected:
        np.testing.assert_allclose(actual[key], expected[key], atol=2e-17)
    for coeff in (c, converted):
        public = sum_features(None, [dict(delta=coeff, perimeter=segments, segment_normals=normals)],
                              directions, 1.)
        for key in expected:
            np.testing.assert_allclose(public['feature_amps'][0][key], expected[key], atol=2e-17)


def test_explicit_legacy_override_and_separate_residual_calibration():
    c, segments, normals = fixture()
    kwargs = dict(segment_normals=normals)
    zero = expand_perimeter(segments, c, None, [[1.,0.,0.]], psi_tm_deg=0., psi_te_deg=0., **kwargs)
    legacy = expand_perimeter(segments, c, None, [[1.,0.,0.]],
                             psi_tm_deg=166.9, psi_te_deg=-9.2, **kwargs)
    for key, phase in zip(('F_vv','F_hh'), LEGACY_PHASE_MAPPING_DEG):
        np.testing.assert_allclose(legacy[key], zero[key]*np.exp(1j*np.deg2rad(phase)), atol=2e-17)
    base = expand_perimeter(segments, c, None, [[1.,0.,0.]], **kwargs)
    calibrated = expand_perimeter(segments, c.as_electric_line(), None, [[1.,0.,0.]],
                                  psi_tm_deg=12., psi_te_deg=12., **kwargs)
    for key in base:
        np.testing.assert_allclose(calibrated[key], base[key]*np.exp(1j*np.deg2rad(12)), atol=2e-17)
    with pytest.raises(ValueError, match='Unknown'):
        line_phase_mapping('unknown')


def test_source_distribution_excludes_tests_and_audits(tmp_path):
    import importlib.util
    from pathlib import Path
    script=Path(__file__).resolve().parents[2]/'scripts/build_distribution.py'
    spec=importlib.util.spec_from_file_location('release_audit',script)
    release=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    for name in ('README.md','ghost_backend/solver.py','ghost_backend/tests/test_solver.py',
                 'AUDIT_FIXES.md','audit_run/check.py','Local_Audit/results.py'):
        target=tmp_path/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text('test')
    assert set(release.release_files(tmp_path)) == {Path('README.md'),Path('ghost_backend/solver.py')}
