"""Randomized invariant tests for dataset operations (seeded numpy, no hypothesis).

A generator covers every storage kind (complex, power, power_phase, raw solver
fields for sigma_3d and sigma_2d, and legacy GHOST deltas as converted on load), complex64 and
complex128, GHz/MHz/Hz frequency axes, single-sample axes, zero and NaN samples
and every phase_wrap declaration. Identities that hold only up to a documented
rounding (complex64, power/phase -> I/Q canonicalization, phase wrapping of a
polar store) use the documented tolerance instead of exact equality.

The final section holds regression tests for bugs found by these invariants.
"""
from __future__ import annotations

import json
import os
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from GRIM_Backend.datasets import transforms as T
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.operations import operation_events
from GRIM_Backend.scripting import workspace as W

KINDS = ("complex", "power", "power_phase", "raw3d", "raw2d", "delta")
FREQ_SCALE = {"GHz": 1.0, "MHz": 1.0e3, "Hz": 1.0e9}
RAW_KEYS = {"rcs_amp_real", "rcs_amp_imag", "raw_complex_amplitude_preserved"}
DELTA_TAGS = {"power_domain": "delta_amp_sq", "rcs_domain": "delta"}


def _converted_legacy_delta(axes, field, units, extra=None):
    """A legacy GHOST delta archive (raw field = physical A), as GRIM loads it."""
    payload = dict(azimuths=np.asarray(axes[0], float), elevations=np.asarray(axes[1], float),
                   frequencies=np.asarray(axes[2], float), polarizations=np.asarray(axes[3]),
                   units=json.dumps(units), grim_format_version=np.int16(2), storage_kind="complex",
                   storage_domain="raw_field", rcs_complex=field, source_path="", history="",
                   **{key: np.asarray(value) for key, value in DELTA_TAGS.items()})
    payload.update(extra or {})
    return RcsGrid._from_native_arrays(payload, path="legacy delta")


def make(seed, kind, dtype, *, shape=None, frequency_unit=None, phase_wrap="random"):
    """Random grid of one storage kind; seeds select shape, units and defects."""
    rng = np.random.default_rng(seed)
    if shape is None:
        shape = tuple(int(rng.choice([1, 2, 3, 5])) for _ in range(3)) + (int(rng.choice([1, 2])),)
    frequency_unit = frequency_unit or ("GHz", "MHz", "Hz")[seed % 3]
    azimuths = float(rng.integers(-180, 170)) + float(rng.choice([1.0, 2.5, 5.0])) * np.arange(shape[0])
    elevations = float(rng.integers(-30, 30)) + 2.5 * np.arange(shape[1])
    frequencies = (8.0 + 0.5 * np.arange(shape[2])) * FREQ_SCALE[frequency_unit]
    pols = ["HH", "VV"][: shape[3]]
    quantity = "sigma_2d" if (kind == "raw2d" or (kind == "delta" and seed % 2 == 0)
                              or (kind in ("complex", "power", "power_phase") and seed % 4 == 3)) else "sigma_3d"
    units = {"azimuth": "deg", "elevation": "deg", "frequency": frequency_unit,
             "rcs_linear_quantity": quantity, "rcs_log_unit": "dBke" if quantity == "sigma_2d" else "dBsm"}
    if phase_wrap == "random":
        phase_wrap = (None, "-180_180", "0_360")[int(rng.integers(3))]
    if phase_wrap:
        units["phase_wrap"] = phase_wrap
    real = np.float64 if dtype == np.complex128 else np.float32
    field = ((rng.normal(size=shape) + 1j * rng.normal(size=shape))
             * 10.0 ** rng.uniform(-3, 1, size=shape)).astype(dtype)
    flat = field.reshape(-1)
    if flat.size > 1:
        flat[int(rng.integers(flat.size))] = 0
    if flat.size > 2:
        flat[int(rng.integers(flat.size))] = np.nan + 1j * np.nan
    extra = {"note": np.asarray(f"seed-{seed}")}
    axes = (azimuths, elevations, frequencies, pols)
    if kind == "complex":
        return RcsGrid(*axes, rcs=field, units=units, extra=extra)
    if kind == "power":
        return RcsGrid(*axes, rcs_power=(np.abs(field) ** 2).astype(real), units=units, extra=extra)
    if kind == "power_phase":
        power = (np.abs(field) ** 2).astype(real)
        phase = np.angle(field).astype(real)
        live = np.flatnonzero(np.isfinite(power.reshape(-1)) & (power.reshape(-1) > 0))
        if live.size:
            phase.reshape(-1)[live[-1]] = np.nan  # a nonzero sample of unknown phase
        if live.size > 1 and phase_wrap is None:
            phase.reshape(-1)[live[0]] += 4.0 * np.pi  # an unwrapped turn count
        return RcsGrid(*axes, rcs_power=power, rcs_phase=phase, units=units, extra=extra)
    if kind == "delta":
        return _converted_legacy_delta(axes, field, units, extra)
    return RcsGrid(*axes, rcs=field, rcs_storage_domain="raw_field", units=units, extra=extra)


CASES = [(kind, dtype, seed) for kind in KINDS for dtype in (np.complex64, np.complex128)
         for seed in (11, 26)]
IDS = [f"{kind}-{np.dtype(dtype).name}-{seed}" for kind, dtype, seed in CASES]


@pytest.fixture(params=CASES, ids=IDS)
def grid(request):
    kind, dtype, seed = request.param
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return make(seed, kind, dtype)


def rtol_for(grid):
    return 2e-6 if grid.real_dtype == np.float32 or grid._complex is not None and grid._complex.dtype == np.complex64 else 1e-12


def unknown(grid):
    power, phase = np.asarray(grid.power, float), np.asarray(grid.phase, float)
    return np.isfinite(power) & (power > 0) & ~np.isfinite(phase)


def assert_same(a, b, *, rtol=0.0, kind=True, atol=0.0):
    assert a.shape == b.shape
    for name in ("azimuths", "elevations", "frequencies"):
        np.testing.assert_allclose(getattr(a, name), getattr(b, name), rtol=1e-12, atol=1e-9)
    assert list(a.polarizations) == list(b.polarizations)
    if kind:
        assert (a.storage_kind, a.storage_domain) == (b.storage_kind, b.storage_domain)
    pa, pb = np.asarray(a.power, float), np.asarray(b.power, float)
    np.testing.assert_array_equal(np.isfinite(pa), np.isfinite(pb))
    finite = np.isfinite(pa)
    if rtol or atol:
        np.testing.assert_allclose(pa[finite], pb[finite], rtol=rtol, atol=atol)
    else:
        np.testing.assert_array_equal(pa[finite], pb[finite])
    np.testing.assert_array_equal(unknown(a), unknown(b))
    known = finite & (pa > 0) & ~unknown(a)
    ha, hb = np.asarray(a.phase, float)[known], np.asarray(b.phase, float)[known]
    if rtol or atol:
        assert np.all(np.abs(np.angle(np.exp(1j * (ha - hb)))) <= max(10 * rtol, 1e-12) + atol)
    else:
        np.testing.assert_array_equal(ha, hb)


def assert_exact_storage(a, b, *, round_trip=False):
    """Bit-identical samples, storage, dtype, units and metadata.

    A save/load round trip must keep every metadata key and add none. An
    operation result follows the derived-metadata policy (free-form keys are
    not carried); no metadata tag defines a field's normalization.
    """
    assert_same(a, b)
    assert a.real_dtype == b.real_dtype
    assert a.units == b.units
    left, right = a.native_sample_payload(), b.native_sample_payload()
    assert set(left) == set(right)
    for key, value in left.items():
        if isinstance(value, np.ndarray):
            assert value.dtype == right[key].dtype
            assert np.array_equal(value, right[key], equal_nan=True), key
        else:
            assert value == right[key]
    keys = set(a.extra) - RAW_KEYS
    if round_trip:
        assert keys == set(b.extra) - RAW_KEYS
    else:
        keys = set()
    for key in keys:
        assert np.array_equal(np.asarray(a.extra[key]), np.asarray(b.extra[key])), key


def complex_reference(other_like, seed=5):
    rng = np.random.default_rng(seed)
    field = rng.normal(size=other_like.shape) + 1j * rng.normal(size=other_like.shape)
    dtype = np.complex128 if other_like.real_dtype == np.float64 else np.complex64
    return RcsGrid(other_like.azimuths, other_like.elevations, other_like.frequencies,
                   other_like.polarizations, rcs=field.astype(dtype), units=dict(other_like.units))


# --------------------------------------------------------------------------
# Invariants that hold for every generated dataset
# --------------------------------------------------------------------------

def test_duplicate_and_flip_twice_are_identities(grid):
    assert_exact_storage(grid, T.duplicate_dataset(grid))
    once = T.flip_phase(grid)
    np.testing.assert_array_equal(unknown(once), unknown(grid))
    twice = T.flip_phase(once)
    if grid.storage_kind == "power_phase" and grid.units.get("phase_wrap") == "0_360":
        # Documented: re-wrapping -phase into [0, 2*pi) rounds by up to one
        # ulp of 2*pi in a polar store; the complex field is unchanged.
        assert_same(grid, twice, rtol=rtol_for(grid))
    else:
        assert_exact_storage(grid, twice)
    if grid.storage_kind == "complex":
        field, flipped = grid.rcs, once.rcs
        finite = np.isfinite(field)
        np.testing.assert_array_equal(flipped[finite], np.conj(field[finite]))


def test_phase_shift_identities(grid):
    rtol = 10 * rtol_for(grid)
    assert_exact_storage(grid, T.shift_dataset(grid, phase_degrees=360.0))
    assert_exact_storage(grid, W.shift_dataset(grid, phase_degrees=-720.0))
    composed = T.shift_dataset(T.shift_dataset(grid, phase_degrees=30.0), phase_degrees=45.0)
    assert_same(composed, T.shift_dataset(grid, phase_degrees=75.0), rtol=rtol, atol=1e-12, kind=False)
    back = T.shift_dataset(T.shift_dataset(grid, phase_degrees=37.0), phase_degrees=-37.0)
    assert_same(grid, back, rtol=rtol, atol=1e-12, kind=False)
    np.testing.assert_array_equal(unknown(composed), unknown(grid))


def test_offset_db_round_trip_and_scale(grid):
    rtol = 10 * rtol_for(grid)
    assert_same(grid, T.offset_db(T.offset_db(grid, 7.5), -7.5), rtol=rtol, kind=False)
    plus_ten = W.offset_db(grid, 10.0)
    power, scaled = np.asarray(grid.power, float), np.asarray(plus_ten.power, float)
    finite = np.isfinite(power)
    np.testing.assert_allclose(scaled[finite], 10.0 * power[finite], rtol=rtol)
    np.testing.assert_array_equal(unknown(plus_ten), unknown(grid))


def test_wrap_phase_changes_representation_only(grid):
    for mode in ("0_360", "-180_180"):
        wrapped = T.wrap_phase(grid, mode)
        assert wrapped.units["phase_wrap"] == mode
        assert_same(grid, wrapped, rtol=rtol_for(grid), kind=False)
        phase = np.asarray(wrapped.phase, float)
        phase = phase[np.isfinite(phase)]
        if phase.size:
            low, high = (0.0, 2 * np.pi) if mode == "0_360" else (-np.pi, np.pi)
            assert phase.min() >= low and phase.max() <= high


def test_self_subtraction_is_zero(grid):
    difference = grid.incoherent_subtract(grid)
    power = np.asarray(difference.power, float)
    finite = np.isfinite(np.asarray(grid.power, float))
    np.testing.assert_array_equal(np.isfinite(power), finite)
    assert np.all(power[finite] == 0) and difference.storage_kind == "power"
    if grid.storage_kind == "power":
        return
    coherent = np.asarray(grid.coherent_subtract(grid).power, float)
    known = finite & ~unknown(grid)
    assert np.all(coherent[known] == 0)
    # Unknown phase is missing in coherent arithmetic, never a known zero.
    assert not np.any(np.isfinite(coherent[unknown(grid)]))


def test_add_then_subtract_restores_the_field(grid):
    reference = complex_reference(grid)
    rtol = 10 * rtol_for(grid)
    if grid.storage_kind != "power":
        restored = grid.coherent_add(reference).coherent_subtract(reference)
        field, original = restored.rcs, grid.rcs
        known = np.isfinite(original) & ~unknown(grid)
        scale = np.abs(reference.rcs).max()
        np.testing.assert_allclose(field[known], original[known], rtol=rtol, atol=rtol * scale)
        assert not np.any(np.isfinite(field[~known]))
    power_reference = RcsGrid(grid.azimuths, grid.elevations, grid.frequencies, grid.polarizations,
                              rcs_power=np.asarray(reference.power), units=dict(grid.units))
    restored = grid.incoherent_add(power_reference).incoherent_subtract(power_reference)
    power, original = np.asarray(restored.power, float), np.asarray(grid.power, float)
    finite = np.isfinite(original)
    np.testing.assert_array_equal(np.isfinite(power), finite)
    np.testing.assert_allclose(power[finite], original[finite], rtol=100 * rtol,
                               atol=100 * rtol * np.asarray(power_reference.power).max())


def test_interpolation_onto_the_same_grid_is_exact(grid):
    other = T.duplicate_dataset(grid)
    for output in (grid.align_to(other),):
        outputs = output if isinstance(output, tuple) else (output,)
        for aligned in outputs:
            assert_exact_storage(grid, aligned) if aligned.storage_kind == grid.storage_kind else assert_same(grid, aligned)
    for axis, values in (("azimuth", grid.azimuths), ("elevation", grid.elevations),
                         ("frequency", grid.frequencies)):
        result = T.regrid_axis(grid, axis, values=np.asarray(values))
        np.testing.assert_array_equal(unknown(result), unknown(grid))
        if grid.storage_kind == "complex":
            # Linear I/Q interpolation is exact at source samples; the field
            # is computed (and stored) in complex128.
            original, field = grid.rcs, result.rcs
            np.testing.assert_array_equal(np.isfinite(field), np.isfinite(original))
            finite = np.isfinite(original)
            np.testing.assert_array_equal(field[finite], original[finite].astype(np.complex128))
        else:
            # power/phase cells go through I/Q (documented last-bit change).
            assert_same(grid, result, rtol=rtol_for(grid), kind=False)


def test_crop_then_join_restores_the_grid_in_either_order(grid):
    for axis, values in (("azimuths", grid.azimuths), ("frequencies", grid.frequencies)):
        if len(values) < 2:
            continue
        half = len(values) // 2
        first = W.crop_dataset(grid, **{axis: list(values[:half])})
        second = W.crop_dataset(grid, **{axis: list(values[half:])})
        for parts in ((first, second), (second, first)):
            joined = W.join_datasets(*parts)
            if grid.storage_kind == "power_phase":
                # A fully known shard canonicalizes to complex (documented).
                assert_same(grid, joined, rtol=rtol_for(grid))
            else:
                assert_exact_storage(grid, joined)


def test_priority_stitch_of_overlapping_shards_restores_the_grid(grid):
    if len(grid.azimuths) < 2:
        return
    half = len(grid.azimuths) // 2
    first = T.crop_dataset(grid, azimuths=list(grid.azimuths[:half + 1]))
    second = T.crop_dataset(grid, azimuths=list(grid.azimuths[half:]))
    for policy in ("priority-first", "priority-last"):
        stitched = W.stitch_datasets(first, second, policy=policy)
        # Stitch merges power/phase and normalizes phase into its declared
        # interval (documented); samples agree to the I/Q rounding.
        assert_same(grid, stitched, rtol=rtol_for(grid), kind=False)
        assert stitched.has_unknown_field_phase() == grid.has_unknown_field_phase()


def test_statistics_and_decimation_of_constant_data_are_constant(grid):
    dtype = np.complex128 if grid.real_dtype == np.float64 else np.complex64
    constant = RcsGrid(grid.azimuths, grid.elevations, grid.frequencies, grid.polarizations,
                       rcs=np.full(grid.shape, 2.0 + 1.0j, dtype=dtype), units=dict(grid.units))
    for statistic in ("mean", "median", "min", "max", "p90"):
        for broadcast in (False, True):
            result = constant.statistics_dataset(statistic, axes=("azimuth", "elevation"),
                                                 domain="magnitude", broadcast_reduced=broadcast)
            np.testing.assert_allclose(np.asarray(result.power, float), 5.0, rtol=1e-6)
    mean = constant.statistics_dataset("mean", axes=("azimuth",), domain="complex")
    np.testing.assert_allclose(mean.rcs, 2.0 + 1.0j, rtol=1e-6)
    spread = constant.statistics_dataset("std", axes=("azimuth",), domain="complex")
    np.testing.assert_allclose(np.asarray(spread.power, float), 0.0, atol=1e-6)
    for axis, count in (("azimuth", len(grid.azimuths)), ("elevation", len(grid.elevations)),
                        ("frequency", len(grid.frequencies))):
        if count < 2:
            continue
        for mode in ("power", "coherent"):
            for partial in ("keep", "drop"):
                result = W.decimate_axis(constant, axis=axis, factor=2, mode=mode, partial=partial)
                np.testing.assert_allclose(np.asarray(result.power, float), 5.0, rtol=1e-6)
                if mode == "coherent":
                    np.testing.assert_allclose(result.rcs, 2.0 + 1.0j, rtol=1e-6)
                else:
                    assert result.storage_kind == "power"


def test_extrusion_and_phase_center_round_trips(grid):
    rtol = 10 * rtol_for(grid)
    there = "dbke" if grid.linear_quantity() == "sigma_3d" else "dbsm"
    back = "dbsm" if there == "dbke" else "dbke"
    restored = W.convert_extrusion(W.convert_extrusion(grid, to=there, length_m=1.7), to=back, length_m=1.7)
    assert (restored.linear_quantity(), restored.default_log_unit()) == (grid.linear_quantity(), grid.default_log_unit())
    assert_same(grid, restored, rtol=rtol, kind=False)
    if grid.phase_coverage() != "none":
        moved = W.translate_phase_center(grid, x_m=0.3, y_m=-0.2, z_m=0.1)
        np.testing.assert_array_equal(unknown(moved), unknown(grid))
        returned = W.translate_phase_center(moved, x_m=-0.3, y_m=0.2, z_m=-0.1)
        assert_same(grid, returned, rtol=10 * rtol, atol=1e-12, kind=False)


def test_native_save_load_is_exact(grid, tmp_path):
    path = grid.save(tmp_path / "grid.grim")
    for storage in ("memory", "disk"):
        loaded = RcsGrid.load(path, storage=storage)
        assert_exact_storage(grid, loaded, round_trip=True)
        again = RcsGrid.load(loaded.save(tmp_path / f"again-{storage}.grim"))
        assert_exact_storage(grid, again, round_trip=True)


def test_csv_export_import_round_trip(grid, tmp_path):
    from GRIM_Backend.io.csv import write_flat_csv
    from GRIM_Backend.io.loaders import load_flat_csv
    path = tmp_path / "grid.csv"
    write_flat_csv(grid, path, scale="linear", include_phase=True)
    loaded = load_flat_csv(str(path))
    assert_same(grid, loaded, rtol=1e-12 if grid.real_dtype == np.float64 else 1e-6, kind=False)
    for key in ("frequency", "rcs_linear_quantity", "rcs_log_unit"):
        assert loaded.units.get(key) == grid.units.get(key)
    if grid.units.get("phase_wrap"):
        assert loaded.units["phase_wrap"] == grid.units["phase_wrap"]


def test_operations_record_provenance(grid):
    operations = {
        "flip_phase": lambda: W.flip_phase(grid),
        "offset_db": lambda: W.offset_db(grid, 1.0),
        "shift_dataset": lambda: W.shift_dataset(grid, phase_degrees=10.0),
        "wrap_phase": lambda: W.wrap_phase(grid, "0_360"),
        "duplicate_dataset": lambda: W.duplicate_dataset(grid),
        "crop_dataset": lambda: W.crop_dataset(grid, azimuths=[grid.azimuths[0]]),
        "incoherent_subtract": lambda: grid.incoherent_subtract(grid),
        "statistics_dataset": lambda: grid.statistics_dataset("mean", axes=("azimuth",)),
    }
    for name, operation in operations.items():
        result = operation()
        events = operation_events(result)
        assert events and events[-1]["operation"] == name
        assert name in str(result.history)
    assert not operation_events(grid)


# --------------------------------------------------------------------------
# Regression tests for bugs found by the invariants above
# --------------------------------------------------------------------------

def _delta(field=None, azimuths=(0.0, 1.0, 2.0), *, tagged=True):
    if field is None:
        rng = np.random.default_rng(7)
        field = rng.normal(size=(len(azimuths), 2, 2, 1)) + 1j * rng.normal(size=(len(azimuths), 2, 2, 1))
    units = {"frequency": "GHz", "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"}
    axes = (list(azimuths), [0.0, 5.0], [10.0, 11.0], ["HH"])
    if not tagged:
        return RcsGrid(*axes, rcs=field, rcs_storage_domain="raw_field", units=units)
    return _converted_legacy_delta(axes, field, units)


@pytest.mark.parametrize("operation", [
    pytest.param(lambda g: T.flip_phase(T.flip_phase(g)), id="flip-twice"),
    pytest.param(lambda g: T.crop_dataset(g, azimuths=list(g.azimuths)), id="crop"),
    pytest.param(lambda g: g.shift_azimuth(5.0).shift_azimuth(-5.0), id="shift-azimuth"),
    pytest.param(lambda g: g.shift_elevation(1.0).shift_elevation(-1.0), id="shift-elevation"),
    pytest.param(lambda g: g.mirror_about_azimuth(1.0), id="mirror"),
    pytest.param(lambda g: g.swap_elevation_azimuth().swap_elevation_azimuth(), id="swap-twice"),
    pytest.param(lambda g: g.convert_axis_units(frequency="MHz").convert_axis_units(frequency="GHz"), id="axis-units"),
    pytest.param(lambda g: g.round_axes(3), id="round"),
    pytest.param(lambda g: g.wrap_azimuth("0_360"), id="wrap-azimuth"),
    pytest.param(lambda g: T.join_datasets(T.crop_dataset(g, azimuths=[0.0]),
                                           T.crop_dataset(g, azimuths=[1.0, 2.0])), id="join"),
    pytest.param(lambda g: T.stitch_datasets(T.crop_dataset(g, azimuths=[0.0, 1.0]),
                                             T.crop_dataset(g, azimuths=[1.0, 2.0])), id="stitch-of-crops"),
    pytest.param(lambda g: RcsGrid.overlap_many(g, T.duplicate_dataset(g))[0], id="overlap"),
])
def test_converted_legacy_delta_keeps_physical_power_through_exact_transforms(operation):
    # A legacy delta (stored A with physical power |A|^2) is converted on
    # load; exact transforms then preserve |A|^2 like any physical field.
    source = _delta()
    result = operation(source)
    if isinstance(result, tuple):
        result = result[0]
    power = np.sort(np.asarray(result.power, float).ravel())
    np.testing.assert_allclose(power, np.sort(np.abs(source._complex.ravel()) ** 2), rtol=1e-12)
    assert not set(DELTA_TAGS) & set(result.extra)


def test_legacy_delta_flip_conjugates_without_rescaling():
    source = _delta()
    flipped = T.flip_phase(source)
    assert flipped.storage_domain == "physical"
    np.testing.assert_array_equal(flipped.rcs, np.conj(source.rcs))


def test_join_of_converted_delta_and_normalized_raw_fields_uses_physical_samples():
    # A converted legacy delta is physical (|A|^2); an ordinary raw field
    # carries scale sqrt(4*pi). Their join keeps both physical responses.
    field = np.array([1 + 1j, 2 - 1j]).reshape(2, 1, 1, 1)
    units = {"frequency": "GHz", "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"}
    delta = _converted_legacy_delta(([0, 1], [0], [10], ["HH"]), field, units)
    plain = RcsGrid([2, 3], [0], [10], ["HH"], rcs=field, rcs_storage_domain="raw_field", units=units)
    expected = np.concatenate([np.abs(field.ravel()) ** 2, 4 * np.pi * np.abs(field.ravel()) ** 2])
    for parts in ((delta, plain), (plain, delta)):
        joined = T.join_datasets(*parts)
        np.testing.assert_allclose(np.asarray(joined.power).ravel(), expected, rtol=1e-12)
    # A legacy power/phase file carrying both raw pairs takes the same rule.
    legacy = RcsGrid._from_native_arrays(dict(
        azimuths=np.asarray([0.0, 1.0]), elevations=np.asarray([0.0]), frequencies=np.asarray([10.0]),
        polarizations=np.asarray(["HH"]), rcs_power=np.abs(field) ** 2, rcs_phase=np.angle(field),
        rcs_amp_real=field.real, rcs_amp_imag=field.imag, units=json.dumps(units),
        source_path="", history="", **DELTA_TAGS))
    joined = T.join_datasets(legacy, plain)
    np.testing.assert_allclose(np.asarray(joined.power).ravel(), expected, rtol=1e-12)


def test_native_load_does_not_add_representation_tags_to_extra(tmp_path):
    # Bug: every load copied the writer's rcs_domain/power_domain into
    # ``extra``; a later save then wrote that stale tag over the actual
    # representation (e.g. "complex_amplitude" for power-only storage).
    source = RcsGrid([0.0, 1.0], [0.0], [10.0], ["HH"], rcs=np.array([1 + 1j, 2j]).reshape(2, 1, 1, 1),
                     units={"frequency": "GHz"})
    loaded = RcsGrid.load(source.save(tmp_path / "complex.grim"))
    assert "rcs_domain" not in loaded.extra and "power_domain" not in loaded.extra
    power_only = loaded.edit_axis_value("azimuth", 0, -1.0)
    power_only.set_power_phase(Ellipsis, power=np.asarray(power_only.power), phase=np.full(power_only.shape, np.nan))
    assert power_only.storage_kind == "power"
    path = power_only.save(tmp_path / "power.grim")
    with np.load(path) as archive:
        assert str(archive["rcs_domain"]) == "linear_rcs"
    # The retired GHOST delta tags are not propagated.
    delta = RcsGrid.load(_delta().save(tmp_path / "delta.grim"))
    assert not set(DELTA_TAGS) & set(delta.extra)
    with np.load(tmp_path / "delta.grim") as archive:
        assert str(archive["power_domain"]) == "linear_rcs"
        assert str(archive["rcs_domain"]) != "delta"


def test_stitch_of_raw_field_with_zero_sample_keeps_zero_known():
    # Bug: stitching a raw solver field marked its exact zero samples as
    # unknown phase, so complete complex input became partial power_phase.
    field = np.array([0j, 1 + 1j, 2 + 0j]).reshape(3, 1, 1, 1)
    units = {"frequency": "GHz", "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"}
    for domain in ("raw_field", "physical"):
        source = RcsGrid([0.0, 1.0, 2.0], [0.0], [10.0], ["HH"], rcs=field,
                         rcs_storage_domain=domain, units=units)
        stitched = T.stitch_datasets(source, T.crop_dataset(source, azimuths=[2.0]))
        assert stitched.storage_kind == "complex", domain
        assert stitched.phase_coverage() == "complete", domain
        np.testing.assert_allclose(stitched.rcs, source.rcs, rtol=1e-12)


def test_assembly_embedding_round_trips_every_storage_kind(tmp_path):
    from PySide6.QtWidgets import QApplication
    from GRIM_Backend.assembly import tree as assembly_tree
    QApplication.instance() or QApplication([])
    for kind, dtype, seed in CASES:
        source = make(seed, kind, dtype)
        snapshot = {"version": 5, "tree": [{
            "name": "root", "type": "root", "included": True, "visible": True,
            "children": [{"name": "leaf", "type": "leaf", "included": True, "visible": True,
                          "mode": "incoh", "dataset": kind, "_grid": source, "children": []}]}]}
        target = tmp_path / f"{kind}-{seed}.asy"
        assembly_tree._write_assembly_snapshot(target, snapshot)
        root = assembly_tree._dict_to_item(json.loads(target.read_text(encoding="utf-8"))["tree"][0])
        restored = root.child(0).data(0, assembly_tree._ROLE_GRID)
        assert_exact_storage(source, restored, round_trip=True)
        snapshot["tree"][0]["children"][0]["_grid"] = restored
        assembly_tree._write_assembly_snapshot(target, snapshot)
        root = assembly_tree._dict_to_item(json.loads(target.read_text(encoding="utf-8"))["tree"][0])
        assert_exact_storage(source, root.child(0).data(0, assembly_tree._ROLE_GRID), round_trip=True)


def test_legacy_v1_delta_archives_survive_save_and_transforms(tmp_path):
    rng = np.random.default_rng(3)
    raw = rng.normal(size=(3, 2, 2, 1)) + 1j * rng.normal(size=(3, 2, 2, 1))
    raw[0, 0, 0, 0] = 0
    units = {"frequency": "GHz", "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"}
    for exceptional in (False, True):
        phase = np.angle(raw)
        if exceptional:
            phase[0, 0, 0, 0] = np.nan  # unknown phase at zero keeps polar storage
        path = tmp_path / f"legacy-{exceptional}.grim"
        with open(path, "wb") as stream:
            np.savez(stream, azimuths=[0.0, 1.0, 2.0], elevations=[0.0, 1.0], frequencies=[10.0, 11.0],
                     polarizations=np.asarray(["HH"]), rcs_power=np.abs(raw) ** 2, rcs_phase=phase,
                     rcs_amp_real=raw.real, rcs_amp_imag=raw.imag, units=json.dumps(units),
                     rcs_domain="delta", power_domain="delta_amp_sq", source_path="", history="")
        loaded = RcsGrid.load(path)
        np.testing.assert_allclose(np.asarray(loaded.power), np.abs(raw) ** 2, rtol=1e-12)
        assert_exact_storage(loaded, RcsGrid.load(loaded.save(tmp_path / f"again-{exceptional}.grim")),
                             round_trip=True)
        for result in (T.flip_phase(T.flip_phase(loaded)), loaded.shift_azimuth(1.0),
                       T.join_datasets(T.crop_dataset(loaded, azimuths=[0.0]),
                                       T.crop_dataset(loaded, azimuths=[1.0, 2.0]))):
            np.testing.assert_allclose(np.asarray(result.power), np.abs(raw) ** 2, rtol=1e-12)


def test_join_keeps_complex64_raw_field_precision():
    # Bug: the complex-native raw-field join always widened to complex128,
    # so crop-then-join of a complex64 solver field changed its storage.
    rng = np.random.default_rng(9)
    field = (rng.normal(size=(4, 1, 2, 1)) + 1j * rng.normal(size=(4, 1, 2, 1))).astype(np.complex64)
    source = RcsGrid(
        [0.0, 1.0, 2.0, 3.0], [0.0], [10.0, 11.0], ["HH"], rcs=field, rcs_storage_domain="raw_field",
        units={"frequency": "GHz", "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"})
    joined = T.join_datasets(T.crop_dataset(source, azimuths=[2.0, 3.0]),
                             T.crop_dataset(source, azimuths=[0.0, 1.0]))
    assert joined.native_sample_payload()["rcs_complex"].dtype == np.complex64
    assert_exact_storage(source, joined)
    with pytest.raises(ValueError, match="conflicting"):
        T.join_datasets(source, T.flip_phase(source))


@pytest.mark.parametrize("operation", [
    pytest.param(lambda g: g.round_axes(2), id="round"),
    pytest.param(lambda g: g.edit_axis_value("frequency", 0, 7.5), id="edit-frequency"),
])
def test_frequency_relabel_does_not_rescale_a_sigma_2d_converted_legacy_delta(operation):
    # A frequency relabel keeps the physical response of an ordinary raw
    # sigma_2d field and of a converted (physical) legacy delta.
    units = {"frequency": "GHz", "rcs_linear_quantity": "sigma_2d", "rcs_log_unit": "dBke"}
    field = np.array([1 + 1j, 2 - 1j, 0.5j]).reshape(1, 1, 3, 1)
    axes = ([0.0], [0.0], [8.0004, 9.0004, 10.0004], ["HH"])
    for source in (_converted_legacy_delta(axes, field, units),
                   RcsGrid(*axes, rcs=field, rcs_storage_domain="raw_field", units=units)):
        result = operation(source)
        assert result.storage_domain == source.storage_domain
        np.testing.assert_allclose(np.asarray(result.power), np.asarray(source.power), rtol=1e-12)
