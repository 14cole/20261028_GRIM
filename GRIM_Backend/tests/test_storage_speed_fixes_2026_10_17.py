"""Regressions for the dataset-storage speed/memory fixes (2026-10-17).

Every cache or shortcut here must stay exact: in-place edits of attached raw
pairs and of the legacy ``rcs_power``/``rcs_phase`` arrays must always show up
in later reads.
"""
from __future__ import annotations

import json
import os
import tracemalloc
import zipfile

import numpy as np
import pytest

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.storage import raw_coverage_scope, seal_samples, sealed_samples
from GRIM_Backend.io import native_cache
from GRIM_Backend.io.batch import grim_save_compression, save_dataset_batch
from GRIM_Backend.io.native import SAVE_COMPRESSION_AUTO

SHAPE = (8, 3, 6, 2)
UNITS = {"frequency": "GHz", "rcs_linear_quantity": "sigma_3d"}
SCALE = np.float32(np.sqrt(4 * np.pi))


def axes(shape=SHAPE):
    return (np.linspace(-10, 10, shape[0]), np.linspace(-1, 1, shape[1]),
            np.linspace(8, 12, shape[2]), ["HH", "VV"][:shape[3]])


def field(seed=0, shape=SHAPE, dtype=np.complex64):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(shape) + 1j * rng.standard_normal(shape)).astype(dtype)


def write_physical_with_pair(path, f):
    """A physical complex archive that also retains a raw solver pair."""
    az, el, fr, pol = axes(f.shape)
    np.savez(path, azimuths=az, elevations=el, frequencies=fr, polarizations=np.asarray(pol),
             grim_format_version=np.asarray(2, np.int16), storage_kind="complex",
             storage_domain="physical", rcs_complex=f,
             rcs_amp_real=(f.real / SCALE).astype(np.float32),
             rcs_amp_imag=(f.imag / SCALE).astype(np.float32),
             units=json.dumps(UNITS), source_path="", history="")
    os.replace(str(path) + ".npz", path)


def normalized(real, imag, selection):
    raw = np.empty(np.shape(real[selection]), dtype=np.complex128)
    raw.real, raw.imag = real[selection], imag[selection]
    raw *= np.sqrt(4.0 * np.pi)
    return raw.astype(np.result_type(real.dtype, imag.dtype, np.complex64))


@pytest.fixture
def scans(monkeypatch):
    calls = []
    original = RcsGrid._scan_raw_pair_coverage
    monkeypatch.setattr(RcsGrid, "_scan_raw_pair_coverage",
                        staticmethod(lambda *args: calls.append(1) or original(*args)))
    return calls


CUT = (slice(None), 1, 2, 0)


# ------------------------------------------------------- 1. raw-pair coverage

def test_loaded_raw_pair_is_sealed_and_validated_once(tmp_path, scans):
    path = tmp_path / "pair.grim"
    write_physical_with_pair(path, field())
    grid = RcsGrid.load(path, storage="disk")
    real, imag = grid.extra["rcs_amp_real"], grid.extra["rcs_amp_imag"]
    assert grid._storage_domain == "physical" and sealed_samples(real) and sealed_samples(imag)
    expected = normalized(np.asarray(real), np.asarray(imag), CUT)
    del scans[:]
    for _ in range(4):
        np.testing.assert_array_equal(grid.rcs_slice(CUT), expected)
        np.asarray(grid.power[CUT])
    assert len(scans) <= 1
    with pytest.raises(ValueError):
        real[0, 1, 2, 0] = 1.0


def test_sealed_pair_cache_follows_replaced_and_unsealed_pairs(tmp_path, scans):
    path = tmp_path / "pair.grim"
    f = field(1)
    write_physical_with_pair(path, f)
    grid = RcsGrid.load(path, storage="disk")
    grid.rcs_slice(CUT)
    # A replaced entry (a new, ordinary array) is validated on every read.
    edited = np.array(grid.extra["rcs_amp_real"], copy=True)
    grid.extra["rcs_amp_real"] = edited
    np.testing.assert_array_equal(grid.rcs_slice(CUT), normalized(edited, grid.extra["rcs_amp_imag"], CUT))
    edited[3, 1, 2, 0] = np.nan          # coverage now contradicts the field
    np.testing.assert_array_equal(grid.rcs_slice(CUT), f[CUT])
    edited[3, 1, 2, 0] = 0.25
    np.testing.assert_array_equal(grid.rcs_slice(CUT), normalized(edited, grid.extra["rcs_amp_imag"], CUT))


def test_unsealing_a_pair_forfeits_the_cached_verdict(tmp_path):
    path = tmp_path / "pair.grim"
    f = field(2)
    write_physical_with_pair(path, f)
    grid = RcsGrid.load(path, storage="disk")
    imag = grid.extra["rcs_amp_imag"]
    np.testing.assert_array_equal(grid.rcs_slice(CUT), normalized(grid.extra["rcs_amp_real"], imag, CUT))
    root = imag
    while isinstance(root.base, np.ndarray):
        root = root.base
    for value in (root, imag):
        value.flags.writeable = True
    imag[5, 1, 2, 0] = np.nan
    assert not sealed_samples(imag)
    np.testing.assert_array_equal(grid.rcs_slice(CUT), f[CUT])


def test_user_attached_pair_edits_are_seen_on_every_read(scans):
    f = field(3)
    grid = RcsGrid(*axes(), rcs=f, units=UNITS)
    real = (f.real / SCALE).astype(np.float32)
    imag = (f.imag / SCALE).astype(np.float32)
    grid.extra["rcs_amp_real"], grid.extra["rcs_amp_imag"] = real, imag
    np.testing.assert_array_equal(grid.rcs_slice(CUT), normalized(real, imag, CUT))
    real[0, 1, 2, 0] = np.nan
    np.testing.assert_array_equal(grid.rcs_slice(CUT), f[CUT])
    real[0, 1, 2, 0] = 2.0
    np.testing.assert_array_equal(grid.rcs_slice(CUT), normalized(real, imag, CUT))
    assert len(scans) == 3


def test_operation_scope_reuses_and_then_drops_its_verdict(scans):
    f = field(4)
    grid = RcsGrid(*axes(), rcs=f, units=UNITS)
    real = (f.real / SCALE).astype(np.float32)
    imag = (f.imag / SCALE).astype(np.float32)
    grid.extra["rcs_amp_real"], grid.extra["rcs_amp_imag"] = real, imag
    with raw_coverage_scope():
        with raw_coverage_scope():
            for _ in range(3):
                grid.rcs_slice(CUT)
        grid.rcs_slice(CUT)
    assert len(scans) == 1
    real[0, 1, 2, 0] = np.nan
    np.testing.assert_array_equal(grid.rcs_slice(CUT), f[CUT])


def test_isar_digest_matches_merged_payload_without_merging(tmp_path, monkeypatch):
    from GRIM_Backend.plotting.modes import isar_mode
    path = tmp_path / "pair.grim"
    write_physical_with_pair(path, field(5))
    grid = RcsGrid.load(path, storage="disk")
    args = (grid, np.arange(2, 7), 1, np.arange(6), 0)
    lazy = isar_mode._selected_data_token(*args)
    merged = grid.native_sample_payload()
    assert merged["storage_domain"] == "raw_field"
    assert isar_mode._native_sample_bytes(grid) == merged["rcs_complex"].nbytes
    # The token the merged complex payload gave before is unchanged.
    monkeypatch.setattr(type(grid), "native_sample_payload", lambda self, **kw: merged)
    assert lazy == isar_mode._selected_data_token(*args)


def test_seal_samples_freezes_the_whole_view_chain():
    owner = np.zeros(12)
    view = owner.reshape(3, 4)[1:]
    seal_samples(view)
    assert not owner.flags.writeable and sealed_samples(view) and sealed_samples(owner)
    assert not sealed_samples(np.zeros(3)) and not sealed_samples([1.0])


# ------------------------------------------------------ 2. legacy freshness

def legacy_grid(seed=6):
    grid = RcsGrid(*axes(), rcs=field(seed), units={"frequency": "GHz"})
    _ = grid.rcs_power
    return grid


@pytest.fixture
def fingerprints(monkeypatch):
    calls = []
    original = RcsGrid._sample_fingerprint
    monkeypatch.setattr(RcsGrid, "_sample_fingerprint", lambda self: calls.append(1) or original(self))
    return calls


def test_legacy_selection_read_skips_the_whole_grid_hash(fingerprints):
    grid = legacy_grid()
    del fingerprints[:]
    source = np.array(grid._complex, copy=True)
    for _ in range(3):
        np.testing.assert_array_equal(grid.rcs_slice(CUT), source[CUT])
    assert not fingerprints


@pytest.mark.parametrize("component", ["rcs_power", "rcs_phase"])
def test_legacy_edit_inside_the_selection_is_seen(component):
    grid = legacy_grid()
    getattr(grid, component)[4, 1, 2, 0] = 4.0 if component == "rcs_power" else 0.5
    result = grid.rcs_slice(CUT)
    assert grid._complex is None and "rcs_amp_real" not in grid.extra
    expected = RcsGrid._complex_from_power_phase(grid.rcs_power[CUT], grid.rcs_phase[CUT])
    np.testing.assert_array_equal(result, expected)


def test_legacy_edit_elsewhere_is_seen_by_reads_of_it_and_by_whole_grid_use(tmp_path):
    grid = legacy_grid()
    grid.rcs_power[7, 0, 5, 1] = 9.0
    # Cells nobody edited still read their exact source...
    assert grid._complex is not None
    # ...the edited cell reads the edit, and so does anything whole-grid.
    assert abs(grid.rcs_slice((7, 0, 5, 1))) ** 2 == pytest.approx(9.0, rel=1e-6)
    other = legacy_grid()
    other.rcs_power[7, 0, 5, 1] = 9.0
    loaded = RcsGrid.load(other.save(tmp_path / "edited.grim"))
    assert loaded.power[7, 0, 5, 1] == pytest.approx(9.0, rel=1e-6)
    third = legacy_grid()
    third.rcs_phase[7, 0, 5, 1] = 1.0
    assert np.angle(third.rcs[7, 0, 5, 1]) == pytest.approx(1.0, rel=1e-6)


def test_replaced_or_reshaped_legacy_arrays_use_the_full_check(fingerprints):
    grid = legacy_grid()
    replacement = np.array(grid.rcs_power, copy=True)
    replacement[0, 1, 2, 0] = 3.0
    grid.rcs_power = replacement
    assert abs(grid.rcs_slice(CUT)[0]) ** 2 == pytest.approx(3.0, rel=1e-6)
    assert fingerprints and grid._complex is None
    reshaped = legacy_grid()
    reshaped.rcs_phase.shape = (SHAPE[0], -1)
    assert not reshaped._legacy_selection_unchanged(CUT)


# --------------------------------------------------------- 3. raw precision

@pytest.mark.parametrize("quantity", ["sigma_3d", "sigma_2d"])
def test_complex64_raw_field_reads_back_at_stored_precision(quantity):
    raw = field(7)
    units = {"frequency": "GHz", "rcs_linear_quantity": quantity}
    grid = RcsGrid(*axes(), rcs=raw, rcs_storage_domain="raw_field", units=units)
    wide = raw.astype(np.complex128)
    if quantity == "sigma_3d":
        wide *= np.sqrt(4.0 * np.pi)
    else:
        k0 = 2.0 * np.pi * np.asarray(axes()[2]) * 1e9 / 299_792_458.0
        wide *= (1.0 / (2.0 * np.sqrt(k0)))[None, None, :, None]
    full = grid.rcs
    assert full.dtype == np.complex64 and grid.real_dtype == np.float32
    np.testing.assert_array_equal(full, wide.astype(np.complex64))
    np.testing.assert_array_equal(grid.rcs_slice(CUT), wide[CUT].astype(np.complex64))
    np.testing.assert_array_equal(grid.rcs_slice((1, 2, 3, 1)), wide[1, 2, 3, 1].astype(np.complex64))
    assert np.asarray(grid.power).dtype == np.float32


def test_complex128_raw_field_is_unchanged():
    raw = field(8, dtype=np.complex128)
    grid = RcsGrid(*axes(), rcs=raw, rcs_storage_domain="raw_field", units=UNITS)
    expected = raw * np.sqrt(4.0 * np.pi)
    assert grid.rcs.dtype == np.complex128
    np.testing.assert_array_equal(grid.rcs, expected)


# ------------------------------------------------- 4. power/phase RAM loads

def test_power_phase_memory_load_adopts_members_bit_identically(tmp_path):
    rng = np.random.default_rng(9)
    shape = (100, 20, 200, 2)
    power = rng.random(shape, dtype=np.float32)
    phase = rng.uniform(-3, 3, shape).astype(np.float32)
    power[0, 0, 0, 0] = -0.0
    power[1, 0, 0, 0] = np.nan
    phase[2, 0, 0, 0] = np.nan          # unknown phase keeps power_phase storage
    phase[3, 0, 0, 0] = 5.0             # wrapped by the declared convention
    units = {"frequency": "GHz", "phase_wrap": "-180_180"}
    reference = RcsGrid(*axes(shape), rcs_power=power, rcs_phase=phase, units=units)
    assert reference.storage_kind == "power_phase"
    path = reference.save(tmp_path / "pp.grim", compressed=False)
    # What the constructor-copying load built from the same stored members.
    with np.load(path) as data:
        expected = RcsGrid(*axes(shape), rcs_power=data["rcs_power"], rcs_phase=data["rcs_phase"],
                           units=json.loads(str(data["units"])))
    tracemalloc.start()
    try:
        loaded = RcsGrid.load(path)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert loaded.storage_kind == "power_phase"
    for name in ("_power", "_phase"):
        assert getattr(loaded, name).tobytes() == getattr(expected, name).tobytes()
    assert peak < 1.5 * (power.nbytes + phase.nbytes)


def test_power_only_memory_load_is_unchanged(tmp_path):
    power = np.random.default_rng(10).random(SHAPE).astype(np.float32)
    grid = RcsGrid(*axes(), rcs_power=power, units={"frequency": "GHz"})
    loaded = RcsGrid.load(grid.save(tmp_path / "p.grim"))
    assert loaded.storage_kind == "power" and loaded._power.tobytes() == grid._power.tobytes()


# --------------------------------------------------- 5. adaptive compression

def stored_methods(path):
    with zipfile.ZipFile(path) as archive:
        return {info.filename: info.compress_type for info in archive.infolist()}


def test_save_auto_uses_the_adaptive_decision(tmp_path):
    shape = (100, 20, 280, 2)          # above the small-archive threshold
    noisy = RcsGrid(*axes(shape), rcs=field(11, shape), units={"frequency": "GHz"})
    smooth = RcsGrid(*axes(shape), rcs=np.ones(shape, np.complex64), units={"frequency": "GHz"})
    assert SAVE_COMPRESSION_AUTO == "auto"
    assert not grim_save_compression(noisy) and grim_save_compression(smooth)
    assert stored_methods(noisy.save(tmp_path / "n.grim", compressed="auto"))["rcs_complex.npy"] == zipfile.ZIP_STORED
    assert stored_methods(smooth.save(tmp_path / "s.grim", compressed="auto"))["rcs_complex.npy"] == zipfile.ZIP_DEFLATED
    paths = save_dataset_batch([(noisy, tmp_path / "bn"), (smooth, tmp_path / "bs")])
    assert stored_methods(paths[0])["rcs_complex.npy"] == zipfile.ZIP_STORED
    assert stored_methods(paths[1])["rcs_complex.npy"] == zipfile.ZIP_DEFLATED
    forced = save_dataset_batch([(noisy, tmp_path / "bf")], compressed=True)
    assert stored_methods(forced[0])["rcs_complex.npy"] == zipfile.ZIP_DEFLATED
    with pytest.raises(TypeError):
        noisy.save(tmp_path / "x.grim", compressed="yes")


# ------------------------------------------------------ 6. squared magnitude

def test_tiled_squared_magnitude_is_bit_identical(monkeypatch):
    import GRIM_Backend.datasets.storage as storage
    original = storage.result_blocks
    monkeypatch.setattr(storage, "result_blocks", lambda shape: original(shape, 7))
    values = field(12, (9, 5, 4, 2))
    values[0, 0, 0, 0] = complex(np.inf, 1)
    values[1, 0, 0, 0] = complex(np.nan, np.nan)
    values[2, 0, 0, 0] = complex(3e19, 3e19)
    for selection in (Ellipsis, (slice(None), 1), (3, 2, 1, 0)):
        view = values[selection]
        real, imag = view.real, view.imag
        with np.errstate(over="ignore", invalid="ignore"):
            expected = np.asarray(real * real + imag * imag)
        assert np.asarray(RcsGrid._squared_magnitude(view)).tobytes() == expected.tobytes()


# ------------------------------------------------- 7. direct member mapping

@pytest.mark.parametrize("storage", ["memory", "disk"])
@pytest.mark.parametrize("compressed", [False, True])
def test_region_load_maps_stored_members_in_place(tmp_path, monkeypatch, storage, compressed):
    shape = (30, 6, 20, 2)
    grid = RcsGrid(*axes(shape), rcs=field(13, shape), units={"frequency": "GHz"})
    path = grid.save(tmp_path / "region.grim", compressed=compressed)
    mapped = []
    original = native_cache._stored_member_map
    monkeypatch.setattr(native_cache, "_stored_member_map",
                        lambda *args: mapped.append(r := original(*args)) or r)
    selection = {"frequency": (9, 11), "polarization": ["VV"]}
    region = RcsGrid.load(path, storage=storage, selection=selection)
    full = RcsGrid.load(path)
    keep = np.flatnonzero((full.frequencies >= 9) & (full.frequencies <= 11))
    np.testing.assert_array_equal(region.rcs, full.rcs[:, :, keep][..., [1]])
    assert any(value is not None for value in mapped) != compressed
    # The archive is not left mapped: it can be replaced right away.
    os.replace(grid.save(tmp_path / "other.grim"), path)


def test_direct_member_map_verifies_the_member_crc(tmp_path):
    grid = RcsGrid(*axes(), rcs=field(14), units={"frequency": "GHz"})
    path = grid.save(tmp_path / "crc.grim", compressed=False)
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("rcs_complex.npy")
    assert native_cache._stored_member_map(path, info) is not None
    with open(path, "r+b") as handle:
        handle.seek(info.header_offset + 30 + len(info.filename) + info.file_size - 4)
        handle.write(b"\xff\xff\xff\x7f")
    with pytest.raises(zipfile.BadZipFile):
        native_cache._stored_member_map(path, info)
    with pytest.raises((zipfile.BadZipFile, ValueError)):
        RcsGrid.load(path, selection={"polarization": ["HH"]})
