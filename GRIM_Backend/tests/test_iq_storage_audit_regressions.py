"""Regressions from the complex I/Q storage audit (2026-10-16)."""
from __future__ import annotations

import json
import warnings
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from GRIM_Backend.assembly import model
from GRIM_Backend.datasets import transforms
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.io.loaders import load_dataset, load_flat_csv

UNITS_3D = {"frequency": "GHz", "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"}
AZ, EL, FR, POL = np.arange(4.0), np.array([0.0]), np.array([8.0, 10.0]), ["HH", "VV"]
SHAPE = (4, 1, 2, 2)


def _field(seed=0, dtype=np.complex128):
    rng = np.random.default_rng(seed)
    return (rng.normal(size=SHAPE) + 1j * rng.normal(size=SHAPE)).astype(dtype)


def _complex_grid(field=None, **kwargs):
    return RcsGrid(AZ, EL, FR, POL, rcs=_field() if field is None else field,
                   units=dict(UNITS_3D), **kwargs)


def _partial_phase_grid():
    field = _field()
    phase = np.angle(field)
    phase[0, 0, 0, 0] = np.nan
    return RcsGrid(AZ, EL, FR, POL, rcs_power=np.abs(field) ** 2, rcs_phase=phase,
                   units=dict(UNITS_3D))


def _power_grid(power=None):
    return RcsGrid(AZ, EL, FR, POL, rcs_power=np.abs(_field()) ** 2 if power is None else power,
                   units=dict(UNITS_3D))


# --- Assembly preflight -------------------------------------------------------

@pytest.mark.parametrize("make", [_complex_grid, _power_grid, _partial_phase_grid])
def test_base_preflight_accepts_version_2_archives(tmp_path, make):
    path = make().save(tmp_path / "body.grim")
    report = model.preflight_base_grim(path)
    assert report.valid, report.summary


def test_base_preflight_still_rejects_archive_without_samples(tmp_path):
    path = tmp_path / "empty.grim"
    with open(path, "wb") as stream:
        np.savez(stream, azimuths=AZ, elevations=EL, frequencies=FR,
                 polarizations=np.asarray(POL), grim_format_version=np.int16(2),
                 storage_kind="complex")
    report = model.preflight_base_grim(path)
    assert not report.valid
    assert "rcs_complex or rcs_power" in report.summary


# --- Legacy delta normalization ------------------------------------------------

def test_legacy_delta_raw_field_is_converted_to_physical_on_load(tmp_path):
    # A legacy GHOST delta stores the physical amplitude A in a raw-field
    # archive; the loader converts it once to physical samples (|A|**2).
    raw = _field()
    path = tmp_path / "delta.grim"
    with open(path, "wb") as stream:
        np.savez(stream, azimuths=AZ, elevations=EL, frequencies=FR, polarizations=np.asarray(POL),
                 grim_format_version=np.int16(2), storage_kind="complex", storage_domain="raw_field",
                 rcs_complex=raw, units=json.dumps(UNITS_3D), power_domain="delta_amp_sq",
                 rcs_domain="delta", source_path="", history="")
    loaded = RcsGrid.load(path)
    assert loaded.storage_domain == "physical"
    assert "power_domain" not in loaded.extra and "rcs_domain" not in loaded.extra
    np.testing.assert_allclose(np.asarray(loaded.power), np.abs(raw) ** 2)
    shifted = transforms.shift_dataset(loaded, phase_degrees=30.0)
    np.testing.assert_allclose(np.asarray(shifted.power), np.abs(raw) ** 2)
    # In memory the retired tags carry no meaning: ordinary raw scaling.
    tagged = RcsGrid(AZ, EL, FR, POL, rcs=raw, rcs_storage_domain="raw_field", units=dict(UNITS_3D),
                     extra={"power_domain": "delta_amp_sq", "rcs_domain": "delta"})
    np.testing.assert_allclose(np.asarray(tagged.power), 4.0 * np.pi * np.abs(raw) ** 2)


def test_legacy_delta_v1_with_raw_pair_loads(tmp_path):
    raw = _field()
    path = tmp_path / "legacy_delta.grim"
    with open(path, "wb") as stream:
        np.savez(stream, azimuths=AZ, elevations=EL, frequencies=FR, polarizations=np.asarray(POL),
                 rcs_power=np.abs(raw) ** 2, rcs_phase=np.angle(raw),
                 rcs_amp_real=raw.real, rcs_amp_imag=raw.imag,
                 units=json.dumps(UNITS_3D), rcs_domain="delta", power_domain="delta_amp_sq",
                 source_path="", history="")
    grid = RcsGrid.load(path)
    np.testing.assert_allclose(np.asarray(grid.power), np.abs(raw) ** 2)


def test_sigma_3d_raw_field_scale_is_unchanged():
    raw = _field()
    grid = RcsGrid(AZ, EL, FR, POL, rcs=raw, rcs_storage_domain="raw_field", units=dict(UNITS_3D))
    np.testing.assert_allclose(np.asarray(grid.power), 4.0 * np.pi * np.abs(raw) ** 2)


# --- Statistics and decimation -------------------------------------------------

def test_complex_std_is_stored_as_power_variance():
    field = _field()
    result = _complex_grid(field).statistics_dataset(statistic="std", axes=("azimuth",), domain="complex")
    expected = np.var(field, axis=0, keepdims=True)
    assert result.storage_kind == "power"
    np.testing.assert_allclose(np.asarray(result.power), expected, rtol=1e-12)


@pytest.mark.parametrize("statistic", ["min", "max", "median"])
def test_complex_order_statistics_are_rejected(statistic):
    with pytest.raises(ValueError, match="not supported"):
        _complex_grid().statistics_dataset(statistic=statistic, axes=("azimuth",), domain="complex")


def test_complex_statistics_refuse_power_only_data():
    with pytest.raises(ValueError, match="power only"):
        _power_grid().statistics_dataset(statistic="mean", axes=("azimuth",), domain="complex")
    # Partial phase keeps the documented rule: unknown-phase cells are missing.
    result = _partial_phase_grid().statistics_dataset(statistic="mean", axes=("azimuth",), domain="complex")
    assert np.isfinite(result.rcs).all()


def test_coherent_decimation_refuses_power_only_data():
    with pytest.raises(ValueError, match="power only"):
        transforms.decimate_axis(_power_grid(), axis="azimuth", factor=2, mode="coherent")
    result = transforms.decimate_axis(_power_grid(), axis="azimuth", factor=2, mode="power")
    assert result.storage_kind == "power"
    zero = _power_grid(np.zeros(SHAPE))
    coherent_zero = transforms.decimate_axis(zero, axis="azimuth", factor=2, mode="coherent")
    np.testing.assert_array_equal(coherent_zero.rcs, 0j)


def test_complex_mean_still_supported():
    field = _field()
    result = _complex_grid(field).statistics_dataset(statistic="mean", axes=("azimuth",), domain="complex")
    np.testing.assert_allclose(result.rcs, field.mean(axis=0, keepdims=True))


# --- Sample edits --------------------------------------------------------------

def test_magnitude_edit_on_zero_sample_leaves_phase_unknown():
    field = _field()
    field[0, 0, 0, 0] = 0
    grid = _complex_grid(field)
    grid.set_power_phase((0, 0, 0, 0), power=4.0)
    assert np.asarray(grid.power)[0, 0, 0, 0] == pytest.approx(4.0)
    assert np.isnan(np.asarray(grid.phase)[0, 0, 0, 0])
    assert grid.phase_coverage() == "partial"


def test_magnitude_edit_keeps_direction_of_nonzero_sample():
    field = _field()
    grid = _complex_grid(field)
    grid.set_power_phase((1, 0, 0, 0), power=9.0)
    assert grid.storage_kind == "complex"
    assert np.angle(grid.rcs[1, 0, 0, 0]) == pytest.approx(np.angle(field[1, 0, 0, 0]))


def test_python_scalar_edit_keeps_complex64():
    grid = _complex_grid(_field(dtype=np.complex64))
    grid.set_power_phase((0, 0, 0, 0), power=2.0)
    assert grid._complex.dtype == np.complex64


def test_negative_legacy_power_becomes_zero_not_missing():
    grid = _complex_grid()
    grid.rcs_power[0, 0, 0, 0] = -1.0
    result = transforms.flip_phase(grid)
    assert np.asarray(result.power)[0, 0, 0, 0] == 0.0


def test_align_interp_keeps_power_only_storage():
    power = np.abs(_field()) ** 2
    power[::2] = 0.0
    source = _power_grid(power)
    target = RcsGrid(np.array([0.5, 1.5, 2.5]), EL, FR, POL, rcs_power=np.ones((3, 1, 2, 2)),
                     units=dict(UNITS_3D))
    aligned = source.align_to(target, mode="interp")
    assert aligned.storage_kind == "power"


# --- ISAR / range / report -----------------------------------------------------

def test_isar_preflight_rejects_power_only_with_zero_cells():
    from GRIM_Backend.plotting.modes.isar_mode import _isar_preflight_error

    power = np.abs(_field()) ** 2
    power[::2] = 0.0
    message = _isar_preflight_error(_power_grid(power))
    assert message and "power only" in message


def test_report_db_values_are_not_floored():
    from GRIM_Backend.reports.plot_data import _series_y

    named = SimpleNamespace(name="d", grid=_complex_grid())
    values = _series_y(named, np.array([0.0, 1e-14, 1.0]), quantity="magnitude", frequency_values=10.0)
    assert np.isnan(values[0])
    assert values[1] == pytest.approx(-140.0)
    assert values[2] == pytest.approx(0.0)


def test_report_phase_is_wrapped():
    from GRIM_Backend.reports.plot_data import _series_y

    named = SimpleNamespace(name="d", grid=_complex_grid())
    values = _series_y(named, np.array([3 * np.pi, np.nan, 0.5]), quantity="phase", frequency_values=10.0)
    assert abs(values[0]) == pytest.approx(180.0)
    assert np.isnan(values[1])
    assert values[2] == pytest.approx(np.rad2deg(0.5))


# --- Loaders -------------------------------------------------------------------

def test_cst_theta_phi_txt_large_power_is_float64_and_overflow_is_value_error(tmp_path):
    header = (
        "Theta(deg) Phi(deg) Abs(RCS)(dBm^2) Abs(Theta)(dBm^2) Phase(Theta)(deg) "
        "Abs(Phi)(dBm^2) Phase(Phi)(deg) Ax.Ratio(dB)\n"
    )
    path = tmp_path / "g_f=10GHz.txt"
    path.write_text(header + "0 0 10 10 33.3333333 5 10 0\n"
                    "1 0 10 400 33.3333333 5 10 0\n")
    grid = load_dataset(str(path))
    assert grid.power_slice().dtype == np.float64
    assert np.nanmax(grid.power_slice()) == pytest.approx(1.0e40)
    overflow = tmp_path / "h_f=10GHz.txt"
    overflow.write_text(header + "0 0 10 4000 33.3333333 5 10 0\n")
    with pytest.raises(ValueError, match="line 2.*overflows finite linear power"):
        load_dataset(str(overflow))


def test_flat_csv_db_overflow_is_value_error(tmp_path):
    path = tmp_path / "huge.csv"
    path.write_text("azimuth,elevation,frequency,polarization,magnitude_dbsm\n0,0,10,VV,5000\n")
    with pytest.raises(ValueError, match="line 2"):
        load_flat_csv(str(path))


# --- GHOST readers honour declared frequency units ------------------------------

def test_ghost_convention_scale_honours_mhz():
    ghost_root = Path(__file__).resolve().parents[2] / "tools" / "GHOST"
    if str(ghost_root) not in sys.path:
        sys.path.insert(0, str(ghost_root))
    fields = pytest.importorskip("ghost_backend.assembly.fields")
    ghz = {"frequencies": np.array([10.0]),
           "units": json.dumps({"rcs_linear_quantity": "sigma_2d", "frequency": "GHz"})}
    mhz = {"frequencies": np.array([10000.0]),
           "units": json.dumps({"rcs_linear_quantity": "sigma_2d", "frequency": "MHz"})}
    np.testing.assert_allclose(fields.convention_scale(mhz), fields.convention_scale(ghz))


# --- Interpolation phase-sampling report ---------------------------------------

def _frequency_sweep(step_mhz, distance_m=1.0):
    frequencies = np.arange(10_000.0, 10_000.0 + 20 * step_mhz, step_mhz)
    field = np.exp(-1j * 4 * np.pi * distance_m * frequencies * 1e6 / 299_792_458.0)
    return RcsGrid([0.0], [0.0], frequencies, ["HH"], rcs=field.reshape(1, 1, -1, 1),
                   units={"frequency": "MHz"}), frequencies


@pytest.mark.parametrize("step_mhz", [5.0, 15.0, 30.0])
def test_regrid_reports_measured_phase_step_and_predicted_loss(step_mhz):
    grid, frequencies = _frequency_sweep(step_mhz)
    dphi = 4 * np.pi * step_mhz * 1e6 / 299_792_458.0
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = grid.interpolate_axis("frequency", frequencies[:-1] + step_mhz / 2)
    report = json.loads(result.extra["regrid_support_json"])
    predicted = 20 * np.log10(np.cos(dphi / 2))
    assert report["max_source_step_phase_rad"] == pytest.approx(dphi, rel=1e-6)
    assert report["predicted_worst_midpoint_loss_db"] == pytest.approx(predicted, rel=1e-6)
    # The prediction is exactly the loss linear I/Q interpolation produces.
    assert 10 * np.log10(np.asarray(result.power)).mean() == pytest.approx(predicted, abs=1e-6)
    warned = any("linear I/Q interpolation" in str(item.message) for item in caught)
    assert warned == (dphi > 0.67)
    assert ("sampling_warning" in report) == (dphi > 0.67)


def test_align_records_phase_sampling():
    grid, frequencies = _frequency_sweep(30.0)
    target = RcsGrid([0.0], [0.0], frequencies[:-1] + 15.0, ["HH"],
                     rcs_power=np.ones((1, 1, frequencies.size - 1, 1)), units={"frequency": "MHz"})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        aligned = grid.align_to(target, mode="interp")
    report = json.loads(aligned.extra["align_sampling_json"])
    assert report["max_source_step_phase_rad"] > 0.67
    assert "sampling_warning" in report


def test_power_only_regrid_has_no_phase_report():
    grid = _power_grid()
    result = grid.interpolate_axis("azimuth", np.array([0.5, 1.5]))
    assert "max_source_step_phase_rad" not in json.loads(result.extra["regrid_support_json"])


# --- Precision of derived and converted values ----------------------------------

def test_small_population_complex_statistics_reduce_in_double_precision():
    rng = np.random.default_rng(0)
    noise = rng.normal(size=(360, 1, 2, 1)) + 1j * rng.normal(size=(360, 1, 2, 1))
    field = (10 * np.exp(0.3j) + 1e-3 * noise).astype(np.complex64)
    grid = RcsGrid(np.arange(360.0), [0.0], [8.0, 9.0], ["HH"], rcs=field, units={"frequency": "GHz"})
    result = grid.statistics_dataset("std", ("azimuth",), domain="complex")
    expected = np.var(field.astype(np.complex128), axis=0, keepdims=True)
    # float32 output rounding only (the float32 reduction was ~3e-6).
    np.testing.assert_allclose(np.asarray(result.power), expected, rtol=1e-7)


def test_csv_round_trip_of_complex64_is_exact_to_storage(tmp_path):
    from GRIM_Backend.io.csv import write_flat_csv

    field = (_field(3) * 10).astype(np.complex64)
    grid = RcsGrid(AZ, EL, FR, POL, rcs=field, units=dict(UNITS_3D))
    path = tmp_path / "round.csv"
    write_flat_csv(grid, str(path), scale="linear", include_phase=True)
    back = load_flat_csv(str(path))
    error = np.abs(back.rcs - field.astype(np.complex128)).max()
    assert error <= 1e-10 * np.sqrt(np.mean(np.abs(field) ** 2))


def test_power_phase_conversion_rounds_once_to_complex64():
    rng = np.random.default_rng(4)
    power = rng.uniform(0.5, 400.0, size=SHAPE).astype(np.float32)
    phase = rng.uniform(-np.pi, np.pi, size=SHAPE).astype(np.float32)
    converted = RcsGrid._complex_from_power_phase(power, phase)
    exact = (np.sqrt(power.astype(np.float64)) * np.exp(1j * phase.astype(np.float64)))
    assert converted.dtype == np.complex64
    np.testing.assert_array_equal(converted, exact.astype(np.complex64))
