"""Speed-ups of 2026-10-17 must not change a single bit of any result.

Each faster path is compared with the path it replaced (forced back on through
the switch it adds, a monkeypatch, or a reference implementation kept here) on
every storage kind: canonical complex64/complex128, power only, power/phase
with unknown phase and unwrapped turns, raw solver fields (sigma_3d, sigma_2d)
and tagged legacy GHOST deltas, with zero and NaN samples.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import os
import re
import threading
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from GRIM_Backend.datasets import combine as C
from GRIM_Backend.datasets import parallel_blocks as PB
from GRIM_Backend.datasets import reduction_workspace as RW
from GRIM_Backend.datasets import result_storage as RS
from GRIM_Backend.datasets import transforms as T
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.result_storage import operation_result_storage, result_storage_mode
from GRIM_Backend.datasets.work_control import WorkCancelled, work_control
from GRIM_Backend.io import csv as CSV
from GRIM_Backend.io.loaders import load_flat_csv

KINDS = ("complex", "power", "power_phase", "raw3d", "raw2d", "delta")


def make(seed, kind, dtype=np.complex64, shape=(9, 3, 16, 2), *, wrap=None, nan=True):
    rng = np.random.default_rng(seed)
    quantity = "sigma_2d" if kind == "raw2d" or seed % 4 == 3 else "sigma_3d"
    units = {"azimuth": "deg", "elevation": "deg", "frequency": "GHz", "rcs_linear_quantity": quantity,
             "rcs_log_unit": "dBke" if quantity == "sigma_2d" else "dBsm"}
    if wrap:
        units["phase_wrap"] = wrap
    axes = (np.arange(shape[0]) * 2.0 - 4.0, np.arange(shape[1]) * 2.5,
            8.0 + 0.25 * np.arange(shape[2]), ["HH", "VV", "HV", "VH"][:shape[3]])
    field = ((rng.normal(size=shape) + 1j * rng.normal(size=shape))
             * 10.0 ** rng.uniform(-3, 1, size=shape)).astype(dtype)
    flat = field.reshape(-1)
    flat[int(rng.integers(flat.size))] = 0
    if nan:
        flat[rng.random(flat.size) < 0.03] = np.nan + 1j * np.nan
    extra = {"note": np.asarray(f"seed-{seed}")}
    real = np.float64 if dtype == np.complex128 else np.float32
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if kind == "complex":
            return RcsGrid(*axes, rcs=field, units=units, extra=extra)
        if kind == "power":
            return RcsGrid(*axes, rcs_power=(np.abs(field) ** 2).astype(real), units=units, extra=extra)
        if kind == "power_phase":
            power = (np.abs(field) ** 2).astype(real)
            phase = np.angle(field).astype(real)
            live = np.flatnonzero(np.isfinite(power.reshape(-1)) & (power.reshape(-1) > 0))
            phase.reshape(-1)[live[-1]] = np.nan
            if wrap is None:
                phase.reshape(-1)[live[0]] += 4.0 * np.pi
            return RcsGrid(*axes, rcs_power=power, rcs_phase=phase, units=units, extra=extra)
        if kind == "delta":
            # A legacy GHOST delta archive, as the native loader converts it.
            import json
            return RcsGrid._from_native_arrays(dict(
                azimuths=np.asarray(axes[0], float), elevations=np.asarray(axes[1], float),
                frequencies=np.asarray(axes[2], float), polarizations=np.asarray(axes[3]),
                units=json.dumps(units), grim_format_version=np.int16(2), storage_kind="complex",
                storage_domain="raw_field", rcs_complex=field, power_domain="delta_amp_sq",
                rcs_domain="delta", source_path="", history="", **extra), path="legacy delta")
        return RcsGrid(*axes, rcs=field, rcs_storage_domain="raw_field", units=units, extra=extra)


def digest(grid):
    """Bits of the authoritative samples, axes, metadata and history."""
    h = hashlib.sha256()

    def put(value):
        a = np.asarray(value)
        h.update(f"{a.dtype.str}{a.shape}".encode())
        h.update(repr(a.tolist()).encode() if a.dtype.kind in "OUS" else np.ascontiguousarray(a).tobytes())

    payload = grid.native_sample_payload()
    for key in sorted(payload):
        h.update(key.encode())
        put(payload[key]) if isinstance(payload[key], np.ndarray) else h.update(repr(payload[key]).encode())
    for name in ("azimuths", "elevations", "frequencies", "polarizations"):
        put(getattr(grid, name))
    for key in sorted(grid.extra):
        if key != "operation_provenance_json":
            h.update(key.encode())
            put(grid.extra[key])
    h.update(repr(grid.history).encode())
    h.update(repr(sorted(grid.units.items())).encode())
    h.update(repr((grid.storage_kind, grid.storage_domain, grid.real_dtype)).encode())
    return h.hexdigest()


GRIDS = [(kind, dtype, seed) for kind in KINDS for dtype in (np.complex64, np.complex128) for seed in (2, 7)]
GRID_IDS = [f"{k}-{np.dtype(d).name}-{s}" for k, d, s in GRIDS]


@pytest.fixture(params=GRIDS, ids=GRID_IDS)
def grid(request):
    kind, dtype, seed = request.param
    return make(seed, kind, dtype, wrap=(None, "-180_180", "0_360")[seed % 3])


def quiet(fn):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn()


# ---------------------------------------------------------------- statistics

def test_vectorized_nan_rank_matches_numpy_nan_functions():
    rng = np.random.default_rng(0)
    for _ in range(600):
        shape = tuple(int(x) for x in rng.integers(1, 7, size=4))
        values = rng.standard_normal(shape) * 10 ** rng.uniform(-3, 3)
        values[rng.random(shape) < rng.choice([0, 0.05, 0.4, 1.0])] = np.nan
        if rng.random() < 0.3:
            values[rng.random(shape) < 0.1] = np.inf
            values[rng.random(shape) < 0.1] = -np.inf
        if rng.random() < 0.3:
            values = np.round(values)      # ties, including -0.0 against +0.0
        axes = tuple(sorted(rng.choice(4, size=int(rng.integers(1, 4)), replace=False).tolist()))
        for rank, reference in ((np.median, np.nanmedian), (np.percentile, np.nanpercentile)):
            args = (float(rng.choice([0, 10, 50, 90, 100, rng.uniform(0, 100)])),) if rank is np.percentile else ()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                expected = reference(values, *args, axis=axes, keepdims=True)
                kwargs = {"method": "linear"} if rank is np.percentile else {}
                actual = RW._vectorized_nan_rank(values, axes, rank, args, kwargs)
            assert actual.dtype == expected.dtype and actual.shape == expected.shape
            assert np.array_equal(actual.view(np.uint8), expected.view(np.uint8))


@pytest.mark.parametrize("statistic", ["median", "p90", "p0", "p100"])
@pytest.mark.parametrize("axes", [("azimuth",), ("elevation",), ("polarization",), ("azimuth", "frequency")])
@pytest.mark.parametrize("domain", ["magnitude", "dbsm"])
def test_small_population_rank_statistics_are_the_nan_function_bits(statistic, axes, domain):
    grid = make(4, "complex", np.complex64)
    original = RW._VECTORIZED_RANK
    try:
        RW._VECTORIZED_RANK = {}
        expected = quiet(lambda: grid.statistics_dataset(statistic, axes, domain=domain))
    finally:
        RW._VECTORIZED_RANK = original
    actual = quiet(lambda: grid.statistics_dataset(statistic, axes, domain=domain))
    assert digest(actual) == digest(expected)


# ---------------------------------------------------------------- CSV export

def _reference_flat_csv(grid, path, scale="linear", delimiter=",", include_phase=False):
    """The row-by-row writer this release replaced (kept as the oracle)."""
    original = CSV._write_flat_csv_block

    def rows(stream, delimiter, grid, selection, power_block, phase_block, *, magnitude_columns,
             phase_wrap, frequency_unit, leading, labels):
        writer = csv.writer(stream, delimiter=delimiter)
        fn = CSV._finite_csv_number
        for ai, azimuth in enumerate(grid.azimuths[selection[0]]):
            for ei, elevation in enumerate(grid.elevations[selection[1]]):
                for fi, frequency in enumerate(grid.frequencies[selection[2]]):
                    frequency_hz = float(frequency) * CSV._FREQUENCY_FACTORS[frequency_unit]
                    for pi, polarization in enumerate(grid.polarizations[selection[3]]):
                        index = (ai, ei, fi, pi)
                        power = float(power_block[index])
                        row = [CSV.FLAT_CSV_SCHEMA, fn(azimuth), leading[0], fn(elevation), leading[1],
                               fn(frequency), frequency_unit, str(polarization)] + list(labels)
                        for column in magnitude_columns:
                            if not np.isfinite(power):
                                row.append("")
                            elif column == "magnitude_power_linear":
                                row.append(fn(power))
                            elif power == 0.0:
                                row.append("-inf")
                            elif column == "magnitude_dbke":
                                wavelength = 299792458.0 / frequency_hz
                                row.append(fn(10.0 * np.log10(power * 2.0 * math.pi / wavelength)))
                            else:
                                row.append(fn(10.0 * np.log10(power)))
                        if phase_block is not None:
                            phase_rad = float(phase_block[index])
                            if phase_wrap == "0_360":
                                phase_deg = np.mod(np.degrees(phase_rad), 360.0)
                            else:
                                phase_deg = np.mod(np.degrees(phase_rad) + 180.0, 360.0) - 180.0
                            row.append(fn(phase_deg) if np.isfinite(phase_rad) else "")
                        writer.writerow(row)

    CSV._write_flat_csv_block = rows
    try:
        return CSV.write_flat_csv(grid, path, scale=scale, delimiter=delimiter, include_phase=include_phase)
    finally:
        CSV._write_flat_csv_block = original


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("options", [dict(scale="both", include_phase=True), dict(scale="linear"),
                                     dict(scale="both", include_phase=True, delimiter="\t")])
def test_block_csv_writer_is_byte_identical(tmp_path, kind, options):
    grid = make(3, kind, np.complex128 if kind == "raw3d" else np.complex64, wrap="0_360" if kind == "power_phase" else None)
    grid.polarizations = np.asarray(["H,H", 'V"V'][: len(grid.polarizations)])   # quoting
    expected, actual = tmp_path / "expected.csv", tmp_path / "actual.csv"
    _reference_flat_csv(grid, expected, **options)
    CSV.write_flat_csv(grid, actual, **options)
    assert actual.read_bytes() == expected.read_bytes()


def test_flat_csv_round_trip_and_line_numbered_errors(tmp_path):
    grid = make(5, "complex", np.complex128)
    path = tmp_path / "grid.csv"
    CSV.write_flat_csv(grid, path, scale="both", include_phase=True)
    loaded = load_flat_csv(str(path))
    np.testing.assert_allclose(np.asarray(loaded.power), np.asarray(grid.power), rtol=1e-12, equal_nan=True)
    lines = path.read_text().splitlines()
    header = lines[0].split(",")
    bad = lines[3].split(",")
    bad[header.index("magnitude_dbsm")] = str(float(bad[header.index("magnitude_dbsm")] or 0) + 1.0)
    bad[header.index("magnitude_power_linear")] = bad[header.index("magnitude_power_linear")] or "1"
    lines[3] = ",".join(bad)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match=r"line 4: redundant magnitude columns conflict"):
        load_flat_csv(str(path))


def test_python_float_closeness_matches_numpy_isclose():
    rng = np.random.default_rng(1)
    a = rng.uniform(0, 10, 20000) * 10.0 ** rng.integers(-20, 20, 20000)
    b = a * (1 + rng.choice([0, 1e-7, 4.9e-6, 5e-6, 5.1e-6, 1e-3], a.size))
    for x, y in zip(a.tolist(), b.tolist()):
        assert (abs(x - y) <= 0.0 + 5.0e-6 * abs(y)) == bool(np.isclose(x, y, rtol=5.0e-6, atol=0.0))


# ---------------------------------------------------------------- crop / select

def test_progression_selection_equals_fancy_gather():
    values = np.random.default_rng(2).standard_normal((7, 5, 9, 3)).astype(np.float32)
    for selection in (np.ix_([0, 2, 4], [1], [0, 1, 2, 3], [0, 2]), np.ix_([6, 5, 4], [0, 1], [3], [1]),
                      np.ix_([0, -1], [0], [0], [0]), np.ix_([3], [4], [8], [2]),
                      (np.array([0, 2]), slice(None), slice(1, 8, 3), 1)):
        assert np.array_equal(RS.select_result(values, selection), values[selection])
    with pytest.raises(IndexError):
        RS.select_result(values, np.ix_([0, 7], [0], [0], [0]))


def test_strided_crop_copies_once_and_matches_two_step_crop(grid):
    az, f = grid.azimuths, grid.frequencies
    one = T.crop_dataset(grid, azimuth_range=(float(az[1]), float(az[-1])), frequency_stride=3, azimuth_stride=2)
    ranged = grid.axis_crop(azimuth_range=(float(az[1]), float(az[-1])))
    two = ranged.axis_crop(azimuths=ranged.azimuths[::2], elevations=ranged.elevations,
                           frequencies=ranged.frequencies[::3], polarizations=ranged.polarizations)
    for a, b in ((one, two),):
        pa, pb = a.native_sample_payload(), b.native_sample_payload()
        assert set(pa) == set(pb)
        for key, value in pa.items():
            if isinstance(value, np.ndarray):
                assert value.dtype == pb[key].dtype and np.array_equal(value.view(np.uint8), pb[key].view(np.uint8))
        assert {k for k in a.extra if k != "operation_provenance_json"} == {k for k in b.extra if k != "operation_provenance_json"}
    assert "crop_dataset" in one.history.splitlines()[-1]


@pytest.mark.parametrize("crop", [dict(azimuth_range=(-2.0, 6.0)), dict(polarizations=["VV"]),
                                  dict(frequencies=[8.25, 8.5, 9.0]), dict(elevation_stride=2)])
def test_crop_views_match_fancy_path(grid, crop, monkeypatch):
    fast = T.crop_dataset(grid, **crop)
    monkeypatch.setattr(RS, "_progression_slice", lambda index, extent: None)
    assert digest(T.crop_dataset(grid, **crop)) == digest(fast)


# ---------------------------------------------------------------- arithmetic

@pytest.mark.parametrize("dtypes", [(np.complex64, np.complex64), (np.complex128, np.complex128),
                                    (np.complex64, np.complex128)])
def test_coherent_sums_match_sequential_owned_additions(dtypes):
    a, b = make(1, "complex", dtypes[0]), make(2, "complex", dtypes[1])
    total = a.coherent_add_many(b, a, b)
    left = np.asarray(a.rcs)
    expected = ((left + np.asarray(b.rcs)) + left) + np.asarray(b.rcs)
    expected[~np.isfinite(expected.real) | ~np.isfinite(expected.imag)] = np.nan + 1j * np.nan
    stored = total.native_sample_payload()["rcs_complex"]
    assert stored.dtype == expected.dtype
    assert np.array_equal(stored.view(np.uint8), expected.view(np.uint8))


@pytest.mark.parametrize("dtype", [np.complex64, np.complex128])
def test_incoherent_sums_match_sequential_power_reads(dtype):
    a, b = make(1, "complex", dtype), make(2, "complex", dtype)
    total = a.incoherent_add_many(b, a)
    expected = (np.asarray(a.power_slice()) + np.asarray(b.power_slice())) + np.asarray(a.power_slice())
    expected[~np.isfinite(expected)] = np.nan
    np.maximum(expected, 0.0, out=expected)
    stored = total.native_sample_payload()["rcs_power"]
    assert stored.dtype == expected.dtype
    assert np.array_equal(stored.view(np.uint8), expected.view(np.uint8))


# ---------------------------------------------------------------- join / stitch

def _parts(grid):
    half = len(grid.azimuths) // 2
    left = T.crop_dataset(grid, azimuth_range=(float(grid.azimuths[0]), float(grid.azimuths[half + 1])))
    right = T.crop_dataset(grid, azimuth_range=(float(grid.azimuths[half]), float(grid.azimuths[-1])))
    return left, right


@pytest.mark.parametrize("operation", ["join_first", "join_last", "stitch_first", "stitch_last",
                                       "stitch_power_mean", "stitch_coherent_mean"])
def test_merge_tile_views_match_fancy_targets(grid, operation, monkeypatch):
    left, right = _parts(grid)

    def run():
        kind, policy = operation.split("_", 1)
        if kind == "join":
            return RcsGrid.join_many(left, right, overlap=policy)
        policy = {"first": "priority-first", "last": "priority-last"}.get(policy, policy.replace("_", "-"))
        return quiet(lambda: T.stitch_datasets(left, right, policy=policy, metadata_attested=True))

    try:
        fast = run()
    except ValueError as exc:
        pytest.skip(f"operation not applicable to this storage: {exc}")
    monkeypatch.setattr(C, "_tile_target", lambda *indices: np.ix_(*indices))
    assert digest(run()) == digest(fast)


def test_stitch_still_rejects_infinite_stored_phase():
    power = np.ones((3, 1, 2, 1))
    phase = np.zeros((3, 1, 2, 1))
    phase[2, 0, 1, 0] = np.nan          # unknown phase keeps power/phase storage
    grid = RcsGrid([0.0, 1.0, 2.0], [0.0], [8.0, 9.0], ["HH"], rcs_power=power, rcs_phase=phase)
    assert grid.storage_kind == "power_phase"
    grid._phase = np.array(grid._phase)
    grid._phase[0, 0, 0, 0] = np.inf
    with pytest.raises(ValueError, match="infinite samples"):
        RcsGrid.stitch_many(grid, grid)


def test_join_datasets_history_is_reproducible():
    left, right = _parts(make(6, "complex"))
    first, second = T.join_datasets(left, right), T.join_datasets(left, right)
    assert first.history == second.history
    assert not re.search(r"max_output_bytes=\d", first.history)


def test_join_datasets_still_applies_the_available_memory_limit(monkeypatch):
    import psutil
    left, right = _parts(make(6, "complex"))

    class Tiny:
        available = 2

    monkeypatch.setattr(psutil, "virtual_memory", lambda: Tiny())
    with pytest.raises(MemoryError):
        T.join_datasets(left, right)


# ---------------------------------------------------------------- adoption

ADOPTING = {
    "offset_db": lambda g: T.offset_db(g, 3.0),
    "shift_phase": lambda g: T.shift_dataset(g, phase_degrees=30.0),
    "coherent_divide": lambda g: T.coherent_divide(g, g),
    "phase_center": lambda g: T.translate_phase_center(g, x_m=0.1, y_m=0.2, z_m=0.0),
    "decimate_power": lambda g: T.decimate_axis(g, axis="azimuth", factor=2, mode="power"),
    "decimate_coherent": lambda g: T.decimate_axis(g, axis="frequency", factor=3, mode="coherent"),
    "incoherent_subtract": lambda g: g.incoherent_add(g).incoherent_subtract(g),
    "db_subtract": lambda g: g.arithmetic_db_subtract(g),
    "stat_mean": lambda g: g.statistics_dataset("mean", ("azimuth",)),
    "stat_mean_db": lambda g: g.statistics_dataset("mean", ("frequency",), domain="dbsm"),
    "stat_complex": lambda g: g.statistics_dataset("mean", ("elevation",), domain="complex", broadcast_reduced=True),
    "stat_complex_std": lambda g: g.statistics_dataset("std", ("azimuth",), domain="complex"),
}


@pytest.mark.parametrize("name", sorted(ADOPTING))
def test_adopted_results_equal_copied_results(grid, name, monkeypatch):
    operation = ADOPTING[name]
    try:
        fast = quiet(lambda: operation(grid))
    except ValueError as exc:
        pytest.skip(f"not applicable: {exc}")
    monkeypatch.setattr(RcsGrid, "_adopt_owned_samples", staticmethod(lambda **_samples: None))
    copied = quiet(lambda: operation(grid))
    assert digest(fast) == digest(copied)


def test_adoption_cleans_like_the_constructor():
    rng = np.random.default_rng(3)
    power = rng.normal(size=(4, 3, 5, 2))
    power[0, 0, 0, 0], power[1, 0, 0, 0], power[2, 0, 0, 0] = np.inf, -np.inf, np.nan
    power[3, 0, 0, 0] = -0.0
    phase = rng.normal(size=power.shape)
    phase[0, 1, 0, 0] = np.inf
    axes = (np.arange(4.0), np.arange(3.0), 8 + np.arange(5.0), ["HH", "VV"])
    expected = RcsGrid(*axes, rcs_power=power.copy(), rcs_phase=phase.copy())
    owned_power, owned_phase = power.copy(), phase.copy()
    token = RcsGrid._adopt_owned_samples(rcs_power=owned_power, rcs_phase=owned_phase)
    actual = RcsGrid(*axes, rcs_power=owned_power, rcs_phase=owned_phase, _adopt_clean_arrays=token)
    assert digest(actual) == digest(expected)
    assert RcsGrid._adopt_owned_samples(rcs_power=power.astype(np.float32), rcs_phase=phase) is None
    assert RcsGrid._adopt_owned_samples(rcs=np.zeros(2, np.complex64), extra={"rcs_amp_real": 1}) is None


# ---------------------------------------------------------------- legacy readers

LEGACY = {
    "coherent_divide": lambda a, b: T.coherent_divide(a, b),
    "decimate": lambda a, b: T.decimate_axis(a, axis="azimuth", factor=2, mode="coherent"),
    "time_gate": lambda a, b: T.time_gate(a, start_m=-0.1, stop_m=0.1),
    "phase_center": lambda a, b: T.translate_phase_center(a, x_m=0.1, y_m=0.0, z_m=0.2),
    "interpolate": lambda a, b: a.interpolate_axis("frequency", a.frequencies[:-1] + 0.1),
    "join": lambda a, b: RcsGrid.join_many(*_parts(a), overlap="first"),
}


@pytest.mark.parametrize("name", sorted(LEGACY))
def test_legacy_arrays_are_hashed_once_per_operation_not_per_tile(name, monkeypatch):
    # Legacy exposure switches some operations to their power/phase path, so
    # the reference is the same operation on another legacy-exposed copy.
    # (The pre-change tree gives these same bits; see the phase-2 report.)
    a, b = make(1, "complex", shape=(40, 4, 32, 2)), make(2, "complex", shape=(40, 4, 32, 2))
    a2, b2 = T.duplicate_dataset(a), T.duplicate_dataset(b)
    _ = a.rcs_power, b.rcs_power, a2.rcs_power, b2.rcs_power   # a script reads, never edits
    expected = quiet(lambda: LEGACY[name](a2, b2))
    calls = []
    original = RcsGrid._sample_fingerprint
    monkeypatch.setattr(RcsGrid, "_sample_fingerprint", lambda self: calls.append(1) or original(self))
    # Many tiles, so a per-tile legacy check would hash dozens of times.
    import GRIM_Backend.datasets.axes as AX
    monkeypatch.setattr(AX, "_RESULT_BLOCK_CELLS", 512)
    monkeypatch.setattr(T, "_GATE_WORK_BYTES", 8 * T._gate_fft_size(32) * 48)
    monkeypatch.setattr(C, "_JOIN_MERGE_BLOCK_CELLS", 512)
    actual = quiet(lambda: LEGACY[name](a, b))
    np.testing.assert_array_equal(np.asarray(actual.power), np.asarray(expected.power))
    assert len(calls) <= 8, len(calls)


# ---------------------------------------------------------------- native save

def test_complex_save_skips_phase_derivation_but_round_trips(tmp_path, monkeypatch):
    grid = make(8, "complex", np.complex64)
    calls = []
    original = RcsGrid._phase_from_field
    monkeypatch.setattr(RcsGrid, "_phase_from_field", lambda self, *a, **k: calls.append(1) or original(self, *a, **k))
    path = grid.save(tmp_path / "g.grim", compressed=False)
    assert not calls
    assert digest(RcsGrid.load(path)) == digest(RcsGrid.load(grid.save(tmp_path / "h.grim")))
    assert np.array_equal(RcsGrid.load(path).native_sample_payload()["rcs_complex"].view(np.uint8),
                          grid.native_sample_payload()["rcs_complex"].view(np.uint8))


def test_power_phase_save_still_validates_phase(tmp_path):
    grid = make(8, "power_phase", np.complex128)
    grid._phase = np.array(grid._phase)
    grid._phase[0, 0, 0, 0] = np.inf
    with pytest.raises(ValueError, match="infinite rcs_phase"):
        grid.save(tmp_path / "bad.grim")


# ---------------------------------------------------------------- tile threads

THREADED = {
    "coherent_add": lambda g: g.coherent_add(g),
    "incoherent_add": lambda g: g.incoherent_add_many(g, g),
    "time_gate": lambda g: T.time_gate(g, start_m=-0.2, stop_m=0.25, taper=0.4),
    "time_gate_remove": lambda g: T.time_gate(g, start_m=-0.1, stop_m=0.15, mode="remove"),
    "interpolate": lambda g: g.interpolate_axis("frequency", g.frequencies[:-1] + 0.07),
    "regrid_azimuth": lambda g: T.regrid_axis(g, "azimuth", start=-3.0, stop=10.0, step=0.5),
    "construct_power_phase": lambda g: RcsGrid(g.azimuths, g.elevations, g.frequencies, g.polarizations,
                                               rcs_power=np.array(g.power), rcs_phase=np.array(g.phase)),
}


@pytest.mark.parametrize("name", sorted(THREADED))
@pytest.mark.parametrize("storage", ["memory", "disk"])
def test_threaded_tiles_equal_serial_tiles(grid, name, storage, tmp_path, monkeypatch):
    # Small tiles so even these small grids run many concurrent tiles.
    monkeypatch.setattr("GRIM_Backend.datasets.arithmetic._COHERENT_OPERATION_BLOCK_CELLS", 64)
    import GRIM_Backend.datasets.grid as G
    monkeypatch.setattr(G, "result_blocks", lambda shape, maximum_cells=64: RS.result_blocks(shape, 64))
    import GRIM_Backend.datasets.axes as AX
    monkeypatch.setattr(AX, "_RESULT_BLOCK_CELLS", 64)
    monkeypatch.setattr(T, "_GATE_WORK_BYTES", 4 * T._gate_fft_size(len(grid.frequencies)) * 48)

    def run(threads):
        with PB.dataset_threads(threads), operation_result_storage(storage, cache_dir=tmp_path):
            return quiet(lambda: THREADED[name](grid))

    try:
        serial = run(1)
    except ValueError as exc:
        pytest.skip(f"not applicable: {exc}")
    assert digest(run(4)) == digest(serial)


def test_tile_helper_order_context_and_controls(tmp_path):
    seen = []

    def body(tile):
        seen.append((threading.current_thread().name, result_storage_mode(), PB.worker_count()))
        return tile * 2

    with PB.dataset_threads(3), operation_result_storage("disk", cache_dir=tmp_path):
        assert list(PB.map_tiles(body, range(50))) == [2 * t for t in range(50)]
    assert {mode for _name, mode, _count in seen} == {"disk"}          # context propagated
    assert {count for _name, _mode, count in seen} == {1}              # no nested pools
    assert any(name.startswith("grim-tiles") for name, _m, _c in seen)
    with PB.dataset_threads(1):
        assert PB.worker_count() == 1 and PB.scaled_cells(1000) == 1000
    with PB.dataset_threads(4):
        assert PB.scaled_cells(1000) == 250
    previous = PB._CONFIGURED
    try:
        PB.configure_dataset_threads(1)
        assert PB.worker_count() == 1
        PB.configure_dataset_threads(None)
        assert PB.worker_count() == (PB._ENVIRONMENT or min(PB._DEFAULT_MAXIMUM, PB.available_cpus()))
    finally:
        PB._CONFIGURED = previous
    with pytest.raises(ValueError):
        PB.configure_dataset_threads(0)


def test_tile_helper_drains_in_flight_tiles_on_cancellation():
    started, finished = [], []
    gate = threading.Event()

    def body(tile):
        started.append(tile)
        gate.wait(0.05)
        finished.append(tile)

    from GRIM_Backend.datasets.memory import _bounded_grid_selections
    calls = {"n": 0}

    def cancelled():
        calls["n"] += 1
        return calls["n"] > 6

    with PB.dataset_threads(4), work_control(cancelled=cancelled):
        with pytest.raises(WorkCancelled):
            PB.run_tiles(body, _bounded_grid_selections((64, 4), 4))
    # Every tile that started has finished before the exception reached us.
    assert sorted(map(str, started)) == sorted(map(str, finished))


def test_tile_errors_propagate_and_stop_submission():
    def body(tile):
        if tile == 5:
            raise RuntimeError("tile failed")
        return tile

    with PB.dataset_threads(4), pytest.raises(RuntimeError, match="tile failed"):
        list(PB.map_tiles(body, range(10_000)))
