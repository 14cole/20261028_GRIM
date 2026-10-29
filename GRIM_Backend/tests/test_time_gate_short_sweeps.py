"""Short-sweep gating checked against explicit DFTs and point responses."""
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.constants import C0
from GRIM_Backend.datasets.transforms import (
    time_gate, gate_geometry, gate_preview_limits, down_range_profile,
)
from GRIM_Backend.ui.dataset_dialogs import TimeGateDialog


def grid_for(count, sign="+jwt", field=None):
    hz = 8e9 + np.arange(count) * 1e8
    if field is None:
        field = np.exp(-4j * np.pi * hz * .18737028625 / C0)
    if sign == "-jwt":
        field = np.conj(field)
    field = np.asarray(field).reshape(-1, 1, count, 1)
    return RcsGrid(np.arange(len(field)), [0.], hz, ["HH"], rcs=field,
                   units={"frequency": "Hz", "time_convention": sign})


@pytest.mark.parametrize("count", range(2, 8))
@pytest.mark.parametrize("sign", ["+jwt", "-jwt"])
@pytest.mark.parametrize("taper", [0., .2, 1.])
def test_short_sweep_matches_explicit_dft_and_complement(count, sign, taper):
    rng = np.random.default_rng(count)
    field = rng.normal(size=count) + 1j * rng.normal(size=count)
    grid = grid_for(count, sign, field)
    original = grid.rcs_slice((0, 0, slice(None), 0)).copy()
    period = C0 / (2e8)
    size = 1 << int(np.ceil(np.log2(4 * count)))
    # Independent inverse/forward DFT matrices, including signed range bins.
    k = np.arange(size)
    n = np.arange(count)
    ranges = np.where(k < size // 2, k, k - size) * period / size
    start, stop = -.30 * period, .30 * period
    mask = ((ranges >= start) & (ranges <= stop)).astype(float)
    edge = taper * (stop - start) / 2
    if edge:
        distance = np.minimum(ranges - start, stop - ranges)
        mask *= .5 - .5 * np.cos(np.pi * np.clip(distance / edge, 0, 1))
    inverse = np.exp(2j * np.pi * k[:, None] * n / size) / size
    forward = np.exp(-2j * np.pi * n[:, None] * k / size)
    expected = forward @ ((inverse @ field) * mask)
    if sign == "-jwt":
        expected = expected.conj()
    params = dict(start_m=start, stop_m=stop, taper=taper, compensate=False)
    kept = time_gate(grid, **params).rcs_slice((0, 0, slice(None), 0))
    removed = time_gate(grid, mode="remove", **params).rcs_slice((0, 0, slice(None), 0))
    np.testing.assert_allclose(kept, expected, atol=2e-14)
    np.testing.assert_allclose(kept + removed, original, atol=2e-14)
    np.testing.assert_array_equal(grid.rcs_slice((0, 0, slice(None), 0)), original)
    full = time_gate(grid, start_m=-period/2, stop_m=period/2, taper=0,
                     compensate=False).rcs_slice((0, 0, slice(None), 0))
    np.testing.assert_allclose(full, original, atol=2e-14)


@pytest.mark.parametrize("count", [2, 3, 4, 5, 7, 8, 65, 201])
@pytest.mark.parametrize("sign", ["+jwt", "-jwt"])
def test_preview_width_spacing_and_point_direction(count, sign):
    grid = grid_for(count, sign)
    limits = gate_preview_limits(grid)
    window = np.ones(count) if count < 4 else np.hanning(count)
    # Direct discrete Fourier response at the reported half-power radius.
    x = .5 * limits["point_width_m"] / limits["unambiguous_m"]
    response = np.sum(window * np.exp(2j * np.pi * np.arange(count) * x)) / window.sum()
    assert abs(response)**2 == pytest.approx(.5, abs=1e-12)
    ranges, power = down_range_profile(grid, elevation_index=0, polarization_index=0)
    assert power.max() > 0
    assert ranges[np.argmax(power)] == pytest.approx(.18737028625,
                                                     abs=limits["display_spacing_m"]/2)
    assert np.diff(ranges) == pytest.approx(limits["display_spacing_m"])
    assert limits["resolution_m"] == pytest.approx(C0/(2e8*count))
    assert limits["bandwidth_hz"] == (count - 1)*1e8
    # Center-point compensation is valid even for short sweeps.
    center = .18737028625
    halfwidth = .55 * limits["resolution_m"]
    kept = time_gate(grid, start_m=center-halfwidth, stop_m=center+halfwidth)
    np.testing.assert_allclose(kept.rcs_slice((0, 0, slice(None), 0)),
                               grid.rcs_slice((0, 0, slice(None), 0)), atol=2e-14)
    negative = grid_for(count, sign, np.exp(4j*np.pi*grid.frequencies*center/C0))
    negative_ranges, negative_power = down_range_profile(negative, elevation_index=0, polarization_index=0)
    assert negative_ranges[np.argmax(negative_power)] == pytest.approx(-center,
                                                       abs=limits["display_spacing_m"]/2)


def test_bad_frequency_and_phase_checks_remain():
    with pytest.raises(ValueError, match="at least 2"):
        gate_geometry(grid_for(1))
    for frequencies in ([8e9, 8e9], [9e9, 8e9], [8e9, np.nan],
                        [8e9, np.inf], [8e9, 8.1e9, 8.3e9]):
        grid = grid_for(len(frequencies))
        # Simulate a malformed axis without constructor cleanup.
        grid.frequencies = np.asarray(frequencies)
        with pytest.raises(ValueError, match="uniformly spaced"):
            gate_geometry(grid)
    grid = grid_for(2, field=[1+1j, np.nan+1j*np.nan])
    with pytest.raises(ValueError, match="complex.*every frequency"):
        time_gate(grid, start_m=-.5, stop_m=.5)
    power_only = RcsGrid([0.], [0.], [8e9, 8.1e9], ["HH"],
                         rcs=np.ones((1, 1, 2, 1)), rcs_domain="linear_power",
                         units={"frequency": "Hz"})
    with pytest.raises(ValueError, match="complex.*every frequency"):
        time_gate(power_only, start_m=-.5, stop_m=.5)
    mixed = grid_for(2, field=[1+1j, 2+1j, 1+1j, np.nan+1j*np.nan])
    result = time_gate(mixed, start_m=-.5, stop_m=.5)
    assert np.all(np.isfinite(result.rcs_slice((0, 0, slice(None), 0))))
    assert np.all(np.isnan(result.rcs_slice((1, 0, slice(None), 0))))


@pytest.mark.parametrize("count", [2, 3, 4, 7, 8, 201])
def test_dialog_short_defaults_limits_and_validation(count):
    app = QApplication.instance() or QApplication([])
    dialog = TimeGateDialog(grid_for(count))
    try:
        assert dialog.btn_box.button(QDialogButtonBox.Ok).isEnabled()
        assert len(dialog._axes.lines) == 2
        assert np.any(np.isfinite(dialog._axes.lines[0].get_ydata()))
        text = dialog.range_limits.text()
        assert f"{count} frequencies" in text
        assert "minimum gate width" in text and "−3 dB" in text
        assert "does not improve resolution" in text
        assert ("Rectangular" if count < 4 else "Hann") in text
        time_gate(grid_for(count), **dialog.get_params())
        dialog.spin_stop.setValue(dialog.spin_start.value())
        dialog.update_preview()
        assert not dialog.btn_box.button(QDialogButtonBox.Ok).isEnabled()
        assert "beyond gate start" in dialog.preview_status.text()
        dialog.spin_start.setValue(dialog.spin_start.minimum())
        dialog.spin_stop.setValue(dialog.spin_stop.maximum())
        dialog.update_preview()
        assert dialog.btn_box.button(QDialogButtonBox.Ok).isEnabled()
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
