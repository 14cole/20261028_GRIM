"""Quantitative ISAR / range-imaging accuracy against synthetic point scatterers.

Point scatterers of RCS ``sigma`` at look-frame ``(x, y)`` use the ISAR phase
law ``sqrt(sigma) exp(-j 4 pi f / c (x sin(az) + y cos(az)))`` (exp(+jwt)).
Amplitudes are read at the band-limited (exact-DFT upsampled) peak so that
pixel scalloping, a display-sampling effect, is separated from the window
coherent-gain normalization being checked.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.transforms import down_range_profile, time_gate
from GRIM_Backend.isar.quality import C0, plan_isar
from GRIM_Backend.plotting.modes import isar_mode as isar
from GRIM_Backend.plotting.modes import az_vs_range_mode as azr
from GRIM_Backend.plotting.modes.range_freq_mode import prepare_range_frequency
from GRIM_Backend.plotting.requests import PlotPlan, PlotRequest

CONTRACT = {"phase_reference": "fixed origin", "range_phase_convention": "S~exp(-j*2*k*R)",
            "measurement_geometry": "far-field monostatic", "motion_compensation": "stable"}


def field(az_deg, f_hz, points, elevation_deg=0.0):
    theta = np.deg2rad(np.asarray(az_deg, float))[:, None]
    f = np.asarray(f_hz, float)[None, :]
    projection = np.cos(np.deg2rad(elevation_deg))
    total = np.zeros((theta.shape[0], f.shape[1]), complex)
    for x, y, sigma in points:
        r = (x * np.sin(theta) + y * np.cos(theta)) * projection
        total += np.sqrt(sigma) * np.exp(-4j * np.pi * f * r / C0)
    return total


def grid(az, f_hz, points=(), *, samples=None, negative_time=False, elevation=0.0):
    samples = field(az, f_hz, points, elevation) if samples is None else samples
    if negative_time:
        samples = np.conj(samples)
    return RcsGrid(np.asarray(az, float), [elevation], np.asarray(f_hz, float), ["VV"],
                   rcs=np.asarray(samples, np.complex128)[:, None, :, None],
                   units={"frequency": "Hz", "azimuth": "deg", "elevation": "deg",
                          "time_convention": "exp(-jwt)" if negative_time else "exp(+jwt)"},
                   extra=dict(CONTRACT))


def look_to_body(x, y, center_deg):
    a = np.deg2rad(center_deg)
    return x * np.cos(a) + y * np.sin(a), -x * np.sin(a) + y * np.cos(a)


def band_limited_peak(image, x_axis, y_axis, factor=8):
    """Exact DFT interpolation of an fftshifted, zero-padded Fourier image."""
    image = np.asarray(image, complex)
    n0, n1 = image.shape
    spectrum = np.fft.fft2(np.fft.ifftshift(image))
    m0, m1 = n0 * factor, n1 * factor
    up = np.fft.fftshift(np.fft.ifft2(spectrum, s=(m0, m1))) * (m0 * m1) / (n0 * n1)
    i, j = np.unravel_index(np.argmax(abs(up)), up.shape)
    dx, dy = x_axis[1] - x_axis[0], y_axis[1] - y_axis[0]
    return (i - m0 // 2) / factor * dx, (j - m1 // 2) / factor * dy, 20 * np.log10(abs(up[i, j]))


def form(dataset, **options):
    options.setdefault("aperture_mode", "coherent")
    return isar.form_isar(dataset, retain_complex=True, **options)[0][0]


F = np.linspace(9e9, 11e9, 101)
AZ = np.linspace(-4.0, 4.0, 81)


@pytest.mark.parametrize("recon", ["fast", "accurate"])
@pytest.mark.parametrize("center", [0.0, 30.0])
def test_peak_position_sign_and_flips(recon, center):
    az = AZ + center
    body = look_to_body(0.3, -0.5, center)
    dataset = grid(az, F, [(*body, 4.0)])
    for flip_x, flip_y in ((False, False), (True, False), (False, True), (True, True)):
        band = form(dataset, reconstruction=recon, window="Hanning", flip_x=flip_x, flip_y=flip_y)
        x, y, _ = band_limited_peak(band["complex_image"], band["x_range"], band["y_range"])
        x += band["x_range"][len(band["x_range"]) // 2]
        y += band["y_range"][len(band["y_range"]) // 2]
        assert x == pytest.approx(-0.3 if flip_x else 0.3, abs=0.012)
        assert y == pytest.approx(0.5 if flip_y else -0.5, abs=0.012)


@pytest.mark.parametrize("window", ["Rectangular", "Hanning", "Hamming", "Blackman",
                                    "Blackman-Harris", "Kaiser beta=15"])
def test_window_coherent_gain_keeps_point_rcs(window):
    origin = form(grid(AZ, F, [(0.0, 0.0, 4.0)]), reconstruction="fast", window=window)
    # An origin point sits exactly on a pixel: its pixel value is the RCS.
    assert 20 * np.log10(np.abs(origin["complex_image"]).max()) == pytest.approx(10 * np.log10(4.0), abs=1e-3)
    for recon, tolerance in (("accurate", 0.03), ("fast", 0.2)):
        band = form(grid(AZ, F, [(0.3, -0.5, 4.0)]), reconstruction=recon, window=window)
        level = band_limited_peak(band["complex_image"], band["x_range"], band["y_range"])[2]
        assert level == pytest.approx(10 * np.log10(4.0), abs=tolerance)


@pytest.mark.parametrize("window,pslr", [("Rectangular", -13.26), ("Hanning", -31.47),
                                         ("Hamming", -42.7), ("Blackman", -58.1),
                                         ("Blackman-Harris", -92.0)])
def test_sidelobes_resolution_and_extents(window, pslr):
    band = form(grid(AZ, F, [(0.0, 0.0, 1.0)]), reconstruction="fast", window=window)
    for cut in ("range", "cross_range"):
        assert band["psf"][cut]["pslr_db"] == pytest.approx(pslr, abs=0.8)
    sampling = band["sampling"]
    fc, df, dtheta = F.mean(), F[1] - F[0], np.deg2rad(AZ[1] - AZ[0])
    assert sampling["range_resolution"] == pytest.approx(C0 / (2 * (F[-1] - F[0])))
    assert sampling["cross_resolution"] == pytest.approx(C0 / fc / (2 * np.deg2rad(np.ptp(AZ))))
    y, x = band["y_range"], band["x_range"]
    assert (y[1] - y[0]) * y.size == pytest.approx(C0 / (2 * df))          # unambiguous range
    assert (x[1] - x[0]) * x.size == pytest.approx(C0 / fc / (2 * dtheta))  # unambiguous cross range
    assert 2 * sampling["range_half_extent"] == pytest.approx(C0 / (2 * df))


@pytest.mark.parametrize("recon", ["fast", "accurate"])
def test_two_scatterer_relative_level(recon):
    points = [(0.0, 0.0, 4.0), (0.35, 0.45, 0.25)]  # 12.04 dB apart
    dataset = grid(AZ, F, points)
    band = form(dataset, reconstruction=recon, window="Hanning")
    levels = []
    for x, y, sigma in points:
        single = form(grid(AZ, F, [(x, y, sigma)]), reconstruction=recon, window="Hanning")
        levels.append(band_limited_peak(single["complex_image"], single["x_range"], single["y_range"])[2])
    strong = 20 * np.log10(np.abs(band["complex_image"]).max())
    assert strong == pytest.approx(10 * np.log10(4.0), abs=0.05)
    assert levels[0] - levels[1] == pytest.approx(10 * np.log10(16.0), abs=0.1)


@pytest.mark.parametrize("recon", ["fast", "accurate"])
def test_unknown_phase_and_missing_sectors_are_zero_weight_gaps(recon):
    point = [(0.3, -0.5, 4.0)]
    complete = form(grid(AZ, F, point), reconstruction=recon, window="Hanning")
    reference = band_limited_peak(complete["complex_image"], complete["x_range"], complete["y_range"])[2]
    samples = field(AZ, F, point)
    phase = np.angle(samples)
    phase[30:40] = np.nan                       # known power, unknown phase
    partial = RcsGrid(AZ, [0.0], F, ["VV"], rcs_power=(abs(samples) ** 2)[:, None, :, None],
                      rcs_phase=phase[:, None, :, None],
                      units={"frequency": "Hz", "azimuth": "deg", "elevation": "deg",
                             "time_convention": "exp(+jwt)"}, extra=dict(CONTRACT))
    keep_f = np.r_[0:45, 55:101]                # missing frequency sector
    keep_az = np.r_[0:35, 45:81]                # missing azimuth sector, one coherent band
    cases = [(partial, {}), (grid(AZ, F[keep_f], point), {}),
             (grid(AZ[keep_az], F, point), {"aperture_center_degrees": 0.0})]
    for dataset, options in cases:
        band = form(dataset, reconstruction=recon, window="Hanning", **options)
        assert band["phase_coverage"] < 0.95
        level = band_limited_peak(band["complex_image"], band["x_range"], band["y_range"])[2]
        assert level == pytest.approx(reference, abs=0.02)


def test_isar_refuses_power_only_and_normalizes_negative_time():
    positive = form(grid(AZ, F, [(0.1, 0.1, 1.0)]))
    negative = form(grid(AZ, F, [(0.1, 0.1, 1.0)], negative_time=True))
    np.testing.assert_allclose(positive['complex_image'], negative['complex_image'], atol=1e-7)
    power = RcsGrid(AZ, [0.0], F, ["VV"], rcs_power=np.ones((AZ.size, 1, F.size, 1)),
                    units={"frequency": "Hz", "azimuth": "deg", "elevation": "deg",
                           "time_convention": "exp(+jwt)"}, extra=dict(CONTRACT))
    with pytest.raises(ValueError, match="power only"):
        isar.form_isar(power)


def test_elevation_projects_onto_horizontal_plane():
    dataset = grid(AZ, F, [(0.3, -0.4, 1.0)], elevation=30.0)
    band = form(dataset, reconstruction="accurate", window="Hanning")
    x, y, level = band_limited_peak(band["complex_image"], band["x_range"], band["y_range"])
    assert (x, y) == (pytest.approx(0.3, abs=0.01), pytest.approx(-0.4, abs=0.01))
    assert level == pytest.approx(0.0, abs=0.03)


def test_plan_isar_does_not_charge_uniform_frequency_steps_to_fast_pfa():
    """Regression: Fast PFA never interpolates a uniform frequency axis."""
    f = np.linspace(9e9, 11e9, 81)              # 25 MHz: 150 deg/sample at 2.5 m
    az = np.linspace(-1.0, 1.0, 161)
    plan = plan_isar(az, f, scene_half_extent_m=(0.05, 2.5), reconstruction="auto")
    assert plan["max_native_frequency_phase_step_rad"] > 2.5
    assert not plan["frequency_interpolated_by_fast_pfa"]
    assert plan["recommended_reconstruction"] == "fft"
    assert not any("Fast PFA's linear interpolation" in w for w in plan["warnings"])
    fast = form(grid(az, f, [(0.0, 2.5, 1.0)]), reconstruction="fast", window="Rectangular")
    assert band_limited_peak(fast["complex_image"], fast["x_range"], fast["y_range"])[2] > -0.05
    # A resampled (nonuniform) frequency axis is interpolated and still reported.
    jittered = f + np.r_[0.0, np.tile([3e6, -3e6], 40)]
    nonuniform = plan_isar(az, jittered, scene_half_extent_m=(0.05, 2.0), reconstruction="fast")
    assert nonuniform["frequency_interpolated_by_fast_pfa"]
    assert any("Fast PFA's linear interpolation" in w for w in nonuniform["warnings"])


def test_plan_isar_fast_azimuth_loss_bounds_measured_loss():
    az = np.linspace(-1.0, 1.0, 21)             # coarse azimuth sampling
    f = np.linspace(9e9, 11e9, 101)
    plan = plan_isar(az, f, scene_half_extent_m=(2.0, 0.05), reconstruction="fast")
    step = plan["fast_interpolation_phase_step_rad"]
    assert step == pytest.approx(4 * np.pi * f[-1] / C0 * 2.0 * np.deg2rad(0.1), rel=1e-3)
    predicted = plan["fast_linear_midpoint_loss_db"]
    assert predicted == pytest.approx(-20 * np.log10(np.cos(step / 2)))
    assert any(f"{predicted:.1f} dB" in w for w in plan["warnings"])
    fast = form(grid(az, f, [(2.0, 0.0, 1.0)]), reconstruction="fast", window="Rectangular")
    measured = -band_limited_peak(fast["complex_image"], fast["x_range"], fast["y_range"], 16)[2]
    assert 0.5 < measured < predicted


def _range_request(dataset, window, mode="az_vs_range", time_sign=None):
    plan = PlotPlan("d", dataset, (list(range(len(dataset.azimuths))), [0],
                                   list(range(len(dataset.frequencies))), [0]))
    if mode == "az_vs_range":
        options = {"window": window, "unit_name": "m", "unit_scale": 1.0, "peak_norm": False,
                   "azimuth_width": 1.0, "time_sign": time_sign}
    else:
        options = {"percent": 100, "window": window, "unit": "m"}
    return PlotRequest(mode, dataset, (plan,), scale="dbsm", options=options)


@pytest.mark.parametrize("negative_time", [False, True])
@pytest.mark.parametrize("window,limit", [("Rectangular", 0.25), ("Hanning", 0.1)])
def test_az_vs_range_off_bin_point_level_and_position(negative_time, window, limit):
    """Regression: unpadded profiles read up to 3.9 dB (rect) low off-bin."""
    f = np.linspace(9e9, 11e9, 201)
    native_bin = C0 / (2 * f.size * (f[1] - f[0]))
    y0 = 20.375 * native_bin                    # worst case for 4x padding
    dataset = grid([-1.0, 0.0, 1.0], f, [(0.0, y0, 1.0)], negative_time=negative_time)
    item = azr.prepare_azimuth_range(_range_request(dataset, window, time_sign="-jwt" if negative_time else None)).items[0]
    row, ranges = item["display"][1], item["range_axis"]
    assert item["range_padding_factor"] >= 4
    assert ranges[np.argmax(row)] == pytest.approx(y0, abs=native_bin / 4)
    assert 0.0 >= np.max(row) > -limit
    assert item["range_scalloping_loss_db"] < limit


def test_range_padding_is_independent_of_dataset_size():
    for n_az in (10, 20000, 200000):
        assert azr._range_fft_size(201, n_az) >= 804
    assert azr._range_fft_size(1701, 36001) >= 6804


def test_range_frequency_level_and_down_range_profile_and_gate():
    f = np.linspace(9e9, 11e9, 201)
    points = [(0.0, 0.6, 4.0), (0.0, -1.5, 1.0)]
    dataset = grid([-1.0, 0.0, 1.0], f, points)
    panel = prepare_range_frequency(_range_request(dataset, "Hanning", "range_freq")).items[0]
    profile, y = np.asarray(panel["image"]).reshape(-1), np.asarray(panel["y"])
    for y0, sigma in ((0.6, 4.0), (-1.5, 1.0)):
        near = abs(y - y0) < 0.05
        assert np.max(profile[near]) == pytest.approx(10 * np.log10(sigma), abs=0.1)
    assert panel["resolution"] == pytest.approx(C0 / (2 * f.size * (f[1] - f[0])))
    ranges, power = down_range_profile(dataset, elevation_index=0, polarization_index=0)
    # Relative (preview) scale: the two levels keep their 6.02 dB separation.
    levels = [10 * np.log10(power[abs(ranges - y0) < 0.05].max()) for _, y0, _ in points]
    assert levels[0] - levels[1] == pytest.approx(10 * np.log10(4.0), abs=0.1)
    single = grid([0.0], f, [points[0]])  # the point sits exactly at the gate centre
    gated = time_gate(single, start_m=0.0, stop_m=1.2, taper=0.2)
    np.testing.assert_allclose(gated.rcs_slice((slice(None), 0, slice(None), 0)),
                               single.rcs_slice((slice(None), 0, slice(None), 0)), rtol=1e-6, atol=1e-9)
