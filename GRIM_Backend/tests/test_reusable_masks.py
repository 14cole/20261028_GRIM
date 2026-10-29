"""Physical mask interchange and independently checked native reconstruction."""
from dataclasses import replace
import json

import numpy as np
import pytest

from GRIM_Backend.isar.mask_geometry import (
    MissingMaskMetadata, define_mask, load_mask, save_mask,
)
from GRIM_Backend.isar.mask_operator import MaskPolarOperator
from GRIM_Backend.isar.masking import MaskImage, comparison_cuts, finish_cut, cut_image
from GRIM_Backend.isar.operators import PolarPointOperator
from GRIM_Backend.isar.quality import image_contract, C0
from GRIM_Backend.plotting.overlay_data import read_overlay_points
from GRIM_Backend.plotting.requests import PlotCancelled


def source_image(*, center=0., scale=1., signs=(1, 1), negative=False):
    az, freq = np.arange(0., 360., 5.), np.linspace(8e9, 12e9, 17)
    axis = np.linspace(-.05, .05, 9)
    theta = np.deg2rad(az-center)
    points = np.array([[-.025, .025], [.025, -.025]])
    coefficients = np.array([1.+.3j, -.2+.6j])
    phase = 4*np.pi/C0*np.cos(np.deg2rad(20.))
    fields = [coefficient*np.exp(-1j*phase*freq[None, :]*(point[0]*np.sin(theta[:, None])+
              point[1]*np.cos(theta[:, None]))) for point, coefficient in zip(points, coefficients)]
    measured = sum(fields)
    if negative:
        measured = measured.conj()
        fields = [f.conj() for f in fields]
    contract = image_contract(theta, freq, center, 20., scale)
    contract['coordinate_signs'] = list(signs)
    context = dict(native_samples=measured, native_azimuth_degrees=az, native_frequency_hz=freq,
        look_center_degrees=center, elevation_degrees=20., distance_scale_per_metre=scale,
        conjugate_time=negative, azimuths=az, elevations=np.array([20.]), frequencies=freq,
        polarizations=['VV'], units={'frequency':'Hz', 'azimuth':'deg', 'elevation':'deg',
        'time_convention':'exp(-jwt)' if negative else 'exp(+jwt)'}, extra={}, window='Rectangular', history='')
    image = MaskImage('Known targets', axis*scale, axis*scale, np.ones((9, 9)),
        np.ones((9, 9), complex), context, dict(contract=contract, unit='m', cuts=[]))
    return image, fields


def boundary(image):
    return np.array([[-.06, -.06], [0., -.06], [0., .06], [-.06, .06]]) * image.inverse['distance_scale_per_metre']


def test_csv_roundtrip_is_overlay_compatible_and_preserves_exact_physical_definition(tmp_path):
    image, _ = source_image(center=17., scale=1/.0254, signs=(-1, 1))
    path = tmp_path/'region.csv'
    definition = save_mask(path, image, boundary(image), include=False)
    points, restored = load_mask(path, image)
    np.testing.assert_allclose(points, boundary(image), atol=1e-14)
    assert restored == definition
    overlay = read_overlay_points(path)
    np.testing.assert_array_equal(overlay[:-1], definition['vertices'])
    np.testing.assert_array_equal(overlay[0], overlay[-1])
    second, _ = source_image(center=-42., scale=1000., signs=(1, -1))
    moved, same = load_mask(path, second)
    physical = define_mask(second, moved, include=False)
    np.testing.assert_allclose(physical['vertices'], definition['vertices'], atol=1e-16)
    other = tmp_path/'resaved.csv'
    save_mask(other, second, moved, include=False, definition=same)
    assert other.read_bytes() == path.read_bytes()
    with pytest.raises(ValueError, match='do not match'):
        save_mask(other, second, moved+1., definition=same)


def test_plain_overlay_requires_explicit_units_and_rejects_disconnected_or_xyz(tmp_path):
    image, _ = source_image(scale=1000.)
    path = tmp_path/'plain.csv'
    path.write_text('x,y\n0,0\n1,0\n0,1\n0,0\n')
    with pytest.raises(MissingMaskMetadata):
        load_mask(path, image)
    points, _ = load_mask(path, image, legacy_unit='in')
    np.testing.assert_allclose(points, [[0, 0], [25.4, 0], [0, 25.4]])
    for text in ('0,0,0\n1,0,0\n0,1,0', '0,0\n1,0\n\n0,1', '0,0\n1,NaN\n0,1'):
        path.write_text(text)
        with pytest.raises(ValueError):
            load_mask(path, image, legacy_unit='m')


def test_tampered_mask_and_unsupported_version_are_rejected(tmp_path):
    image, _ = source_image()
    path = tmp_path/'mask.csv'
    save_mask(path, image, boundary(image))
    text = path.read_text()
    path.write_text(text.replace('"version": 1', '"version": 7'))
    with pytest.raises(ValueError, match='Unsupported'):
        load_mask(path, image)
    lines = text.splitlines()
    lines[-2] = '-0.07,0.06'
    path.write_text('\n'.join(lines))
    with pytest.raises(ValueError, match='checksum'):
        load_mask(path, image)


def test_maximum_size_closed_polygon_roundtrips(tmp_path):
    image, _ = source_image()
    t = np.arange(4096)*2*np.pi/4096
    points = np.column_stack((np.cos(t), np.sin(t)))
    path = tmp_path/'large.csv'
    save_mask(path, image, points)
    loaded, _ = load_mask(path, image)
    np.testing.assert_array_equal(loaded, points)


def test_boundary_membership_is_invariant_under_display_units():
    selected = []
    for scale in (1., 1000., 1/.0254):
        source, _ = source_image(scale=scale)
        image = replace(source, x=np.array([-1e-9, -.5e-10, .5e-10, 2e-10])*scale,
                        y=np.array([-.02, 0., .02])*scale,
                        magnitude=np.ones((4,3)), complex_image=None)
        selected.append(cut_image(image, boundary(image), include=True, name='test').magnitude)
    for other in selected[1:]:
        np.testing.assert_array_equal(other, selected[0])


@pytest.mark.parametrize('reverse', [False, True])
def test_fast_forward_operator_matches_independent_exact_sum_and_its_adjoint(reverse):
    x, y = np.linspace(-.053, .047, 17), np.linspace(-.07, .04, 15)
    if reverse:
        x, y = x[::-1], y[::-1]
    az, freq = np.arange(0, 360, 13), np.linspace(8e9, 12e9, 11)
    rng = np.random.default_rng(124)
    samples = rng.normal(size=(len(x), len(y)))+1j*rng.normal(size=(len(x), len(y)))
    valid = rng.random((len(az), len(freq))) > .1
    op = MaskPolarOperator(x, y, az, freq, 20., valid=valid)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    exact = PolarPointOperator(np.repeat(np.deg2rad(az), len(freq))[valid.ravel()],
        np.tile(freq, len(az))[valid.ravel()], np.column_stack((xx.ravel(), yy.ravel())), elevation_degrees=20.)
    expected = exact.forward(samples.ravel()) / op.normalization
    assert np.linalg.norm(op @ samples.ravel()-expected)/np.linalg.norm(expected) < 1e-4
    test = rng.normal(size=op.shape[0])+1j*rng.normal(size=op.shape[0])
    np.testing.assert_allclose(np.vdot(op @ samples.ravel(), test), np.vdot(samples.ravel(), op.rmatvec(test)), atol=1e-11)


@pytest.mark.parametrize('negative,signs,scale', [(False, (1, 1), 1.), (True, (-1, -1), 1/.0254)])
def test_partial_cut_recovers_known_target_and_saved_mask_repeats(tmp_path, negative, signs, scale):
    image, fields = source_image(negative=negative, signs=signs, scale=scale)
    vertices = boundary(image)
    path = tmp_path/'mask.csv'
    save_mask(path, image, vertices)
    loaded, definition = load_mask(path, image)
    include, exclude = comparison_cuts(image, loaded, name='target', mask_definition=definition)
    expected = fields[0 if signs[0] == 1 else 1]
    actual = include[1].rcs[:, 0, :, 0]
    assert np.linalg.norm(actual-expected)/np.linalg.norm(expected) < .001
    np.testing.assert_allclose(include[1].rcs+exclude[1].rcs, image.inverse['native_samples'][:, None, :, None], atol=5e-16)
    repeated = finish_cut(image, loaded, name='repeat', include=True, mask_definition=definition)
    np.testing.assert_array_equal(repeated[1].rcs, include[1].rcs)
    provenance = json.loads(repeated[1].extra['mask_cut_json'])
    assert provenance['image']['mask_definition']['sha256'] == definition['sha256']
    assert provenance['native_fit']['relative_complex_residual'] < .001


def test_full_mask_is_exact_and_keeps_unknown_samples_unknown():
    image, _ = source_image()
    image.inverse['native_samples'][2, 3] = np.nan+1j*np.nan
    vertices = [[-1,-1], [1,-1], [1,1], [-1,1]]
    include, exclude = comparison_cuts(image, vertices, name='all')
    np.testing.assert_array_equal(include[1].rcs[:,0,:,0], image.inverse['native_samples'])
    valid = np.isfinite(image.inverse['native_samples'])
    np.testing.assert_array_equal(exclude[1].rcs[:,0,:,0][valid], np.zeros(valid.sum()))
    assert np.isnan(exclude[1].rcs[2,0,3,0])
    assert include[0].inverse['native_fit']['method'] == 'full_scene_identity_v1'


def test_inaccurate_fit_memory_limit_invalid_geometry_and_cancellation_fail_cleanly():
    image, _ = source_image()
    image.x = image.y = np.linspace(-1e-5, 1e-5, 9)
    with pytest.raises(ValueError, match='cannot reproduce'):
        finish_cut(image, boundary(image), include=True, name='bad')
    x = np.linspace(-1, 1, 5)
    with pytest.raises(ValueError, match='memory budget'):
        MaskPolarOperator(x, x, [0, 5], [1e9, 2e9], maximum_bytes=1)
    with pytest.raises(ValueError, match='positive frequencies'):
        MaskPolarOperator(x, x, [0, 5], [-1., 2.])
    with pytest.raises(PlotCancelled):
        MaskPolarOperator(x, x, [0, 5], [1e9, 2e9], cancel=lambda: True)
