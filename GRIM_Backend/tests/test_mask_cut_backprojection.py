"""Backprojection cuts use native polar geometry and a verified native fit."""
import unittest
import numpy as np
from test_isar_improvements import grid, params
from GRIM_Backend.plotting.modes.isar_mode import form_isar
from GRIM_Backend.isar.masking import (image_from_band, comparison_cuts, reconstruct_radar,
                                     _project_backprojection_image, finish_cut)
from GRIM_Backend.isar.operators import PolarPointOperator


class BackprojectionMaskTests(unittest.TestCase):
    def source(self, *, flips=False, negative=False):
        az = np.linspace(0., 360., 25)
        f = np.linspace(9e9, 11e9, 9)
        phase = 4*np.pi / 299792458. * np.cos(np.deg2rad(20.))
        t = np.deg2rad(az)[:, None]
        field = np.exp(-1j*phase*f*(.12*np.sin(t)+.08*np.cos(t)))
        field += .6j*np.exp(-1j*phase*f*(-.15*np.sin(t)-.07*np.cos(t)))
        if negative:
            field = field.conj()
        source = grid(az=az, freq=f, field=field, elevation=20.)
        if negative:
            source.units['time_convention'] = 'exp(-jwt)'
            source.extra['time_convention'] = 'exp(-jwt)'
            source.extra['range_phase_convention'] = 'S~exp(+j*2*k*R)'
        bands, _ = form_isar(source, reconstruction='backprojection', aperture_mode='coherent',
                            scene_half_extent_m=(.25, .25), window='Rectangular',
                            retain_complex=True, length_unit='in', flip_x=flips, flip_y=flips)
        image = image_from_band(bands[0], dict(params(source), unit_name='in'))
        return source, image

    def test_native_forward_projection_matches_independent_point_operator(self):
        for flips, negative in ((False, False), (True, True)):
            with self.subTest(flips=flips, negative=negative):
                _, image = self.source(flips=flips, negative=negative)
                c = image.inverse
                signs = image.metadata['contract']['coordinate_signs']
                x, y = np.meshgrid(signs[0]*image.x/c['distance_scale_per_metre'],
                                   signs[1]*image.y/c['distance_scale_per_metre'], indexing='ij')
                az = np.repeat(np.deg2rad(c['native_azimuth_degrees']-c['look_center_degrees']), len(c['native_frequency_hz']))
                freq = np.tile(c['native_frequency_hz'], len(c['native_azimuth_degrees']))
                op = PolarPointOperator(az, freq, np.column_stack((x.ravel(), y.ravel())), elevation_degrees=20.)
                expected = op.forward(image.complex_image.ravel()).reshape(len(c['azimuths']), -1)
                if c['conjugate_time']:
                    expected = expected.conj()
                np.testing.assert_allclose(_project_backprojection_image(image), expected, rtol=2e-6, atol=2e-6)

    def test_complementary_cuts_share_fit_and_preserve_axes_missing_samples_and_source(self):
        _, image = self.source()
        original = image.complex_image.copy()
        image.inverse['native_samples'][1, 2] = complex(np.nan, np.nan)
        x, y = image.x, image.y
        boundary = [(x.min(), y.min()), (0, y.min()), (0, y.max()), (x.min(), y.max())]
        include, exclude = comparison_cuts(image, boundary, name='target')
        baseline = reconstruct_radar(image)
        np.testing.assert_allclose(include[1].rcs + exclude[1].rcs, baseline.rcs,
                                   rtol=2e-5, atol=2e-6, equal_nan=True)
        self.assertTrue(np.isnan(include[1].rcs[1, 0, 2, 0]))
        self.assertEqual(include[0].inverse['native_fit'], exclude[0].inverse['native_fit'])
        self.assertLessEqual(include[0].inverse['native_fit']['relative_complex_residual'], .001)
        self.assertEqual(include[1].rcs.shape, (24, 1, 9, 1))
        np.testing.assert_array_equal(image.complex_image, original)
        self.assertIn('retains the fit residual', include[1].history)

    def test_excluding_entire_image_gives_zero_radar_response(self):
        _, image = self.source()
        x, y = image.x, image.y
        boundary = [(x.min()-1, y.min()-1), (x.max()+1, y.min()-1),
                    (x.max()+1, y.max()+1), (x.min()-1, y.max()+1)]
        _, result = finish_cut(image, boundary, include=False, name='target_exclude')
        np.testing.assert_array_equal(result.rcs, np.zeros_like(result.rcs))

