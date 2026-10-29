"""PTM and text managed loading, exact round trips, and reusable discovery."""
from __future__ import annotations

import csv
import gc
from pathlib import Path
import threading
import tracemalloc
from unittest import mock

import numpy as np
import pytest

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.result_storage import array_storage
from GRIM_Backend.datasets.work_control import WorkCancelled, work_control
from GRIM_Backend.io import loaders, text_storage
from GRIM_Backend.io.binary_storage import estimate_binary_import
from GRIM_Backend.io.ptm import read_ptm, write_ptm
from GRIM_Backend.tests.test_ptm import _independent_fixture
from GRIM_Backend.tests.test_streaming_vendor_imports import (
    CST_FLAT, CST_WIDE, SENTRI_HEADER, LEGACY_HEADER,
)


def write_rows(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        csv.writer(stream).writerows(rows)
    return path


def table(tmp_path, kind):
    if kind == 'flat':
        header = ['azimuth', 'elevation', 'frequency', 'polarization', 'magnitude_linear', 'phase_deg']
        rows = [[0, 0, 1, 'VV', 1, 45], [10, 0, 2, 'VV', 0, 90]]
        name = 'flat.csv'
    elif kind == 'cst-flat':
        header, rows = CST_FLAT, [[0, 0, 1, 'VV', 0, 45, ''], [0, 10, 2, 'VV', '-inf', 90, '']]
        name = 'flat.cst_data'
    elif kind == 'cst-wide':
        header, rows = CST_WIDE, [[1, 90, 0, 0, 45], [2, 90, 10, '-inf', 90]]
        name = 'wide.csv'
    elif kind == 'sentri':
        header = SENTRI_HEADER
        rows = [[1000, 90, 0, 0, 45, -10, 90, -20, 180, -30, 270],
                [2000, 90, 360, 0, 45, -10, 90, -20, 180, -30, 270]]
        name = 'sentri.csv'
    else:
        header = LEGACY_HEADER
        rows = [[10, 20, 0, -13.123456789, 31.123456789, -17.246813579, 24.987654321, 0]]
        name = 'f=1GHz_samples.txt'
    return write_rows(tmp_path / name, [header, *rows])


@pytest.mark.parametrize('kind', ['flat', 'cst-flat', 'cst-wide', 'sentri', 'legacy'])
def test_disk_text_matches_memory_and_reuses_immutable_discovery(tmp_path, kind):
    path = table(tmp_path, kind)
    expected = loaders.load_dataset(path)
    report = text_storage.estimate_text_import(path, storage='disk')
    plan = report['discovery_plan']
    assert plan.stages
    with pytest.raises(TypeError):
        plan.stages['new'] = ()
    real_discover = text_storage.discover_coordinates
    calls = []

    def require_cached(source, key, discover):
        calls.append(key)
        def forbidden():
            pytest.fail('valid source repeated coordinate discovery')
        return real_discover(source, key, forbidden)

    # Each parser imports this helper directly. Swap its binding so a repeated
    # discovery pass fails, while leaving sample parsing and validation intact.
    with mock.patch('GRIM_Backend.io.csv.discover_coordinates', require_cached), \
         mock.patch('GRIM_Backend.io.cst.discover_coordinates', require_cached), \
         mock.patch('GRIM_Backend.io.sentri.discover_coordinates', require_cached):
        actual = loaders.load_dataset(path, storage='disk', cache_dir=tmp_path,
                                      discovery_plan=plan,
                                      max_output_bytes=report['estimated_peak_bytes'])
    assert calls
    assert actual.load_storage == 'disk'
    for array in actual.native_sample_payload().values():
        if isinstance(array, np.ndarray) and array.ndim == 4:
            assert array_storage(array) == 'disk'
    np.testing.assert_array_equal(actual.power_slice(), expected.power_slice())
    np.testing.assert_array_equal(actual.phase_slice(), expected.phase_slice())
    assert actual.units == expected.units
    assert report['retained_bytes'] == 0


def test_changed_source_rebuilds_discovery_instead_of_using_stale_axes(tmp_path):
    path = table(tmp_path, 'flat')
    plan = text_storage.estimate_text_import(path)['discovery_plan']
    with path.open('a', encoding='utf-8') as stream:
        stream.write('20,0,3,VV,4,0\n')
    actual = loaders.load_dataset(path, storage='disk', cache_dir=tmp_path, discovery_plan=plan)
    np.testing.assert_array_equal(actual.azimuths, [0, 10, 20])
    assert actual.power_slice()[-1, 0, -1, 0] == 4


@pytest.mark.parametrize('byte_order', ['little', 'big'])
def test_ptm_disk_decodes_native_precision_seams_and_independent_source(tmp_path, byte_order):
    path = tmp_path / 'source.ptm'
    _independent_fixture(path, byte_order=byte_order)
    expected = read_ptm(path)
    with mock.patch.object(np, 'fromfile', side_effect=AssertionError('whole source read')):
        grid = loaders.load_dataset(path, storage='disk', cache_dir=tmp_path)
    assert array_storage(grid._complex) == 'disk'
    assert grid._complex.dtype == np.complex64
    np.testing.assert_array_equal(grid.rcs_slice(Ellipsis)[:, 0, :, 0], expected.iq)
    path.unlink()
    out = grid.save_ptm(tmp_path / 'export.ptm')
    np.testing.assert_array_equal(read_ptm(out).iq, expected.iq)


def test_ptm_load_and_export_peak_are_block_bounded(tmp_path):
    values = (np.arange(256 * 2048, dtype=np.float32).reshape(256, 2048) / 1000 + 1j).astype(np.complex64)
    path = write_ptm(tmp_path / 'large.ptm', np.arange(256) * .1,
                     np.linspace(1, 2, 2048), values, polarity='VV')
    report = estimate_binary_import(path, storage='disk')
    tracemalloc.start()
    grid = loaders.load_dataset(path, storage='disk', cache_dir=tmp_path,
                                 max_output_bytes=report['estimated_peak_bytes'])
    _, read_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    tracemalloc.start()
    grid.save_ptm(tmp_path / 'large_export.ptm')
    _, write_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert read_peak < values.nbytes // 2
    assert write_peak < values.nbytes // 2
    np.testing.assert_array_equal(grid.rcs_slice(Ellipsis)[:, 0, :, 0], values)


def test_ptm_export_unknown_phase_still_rejected_and_existing_target_retained(tmp_path):
    shape = (2, 1, 40, 1)
    power = np.ones(shape)
    phase = np.zeros(shape)
    phase[1, 0, -1, 0] = np.nan
    grid = RcsGrid([0, 1], [0], np.linspace(1, 2, 40), ['VV'], rcs_power=power, rcs_phase=phase)
    path = tmp_path / 'target.ptm'
    path.write_bytes(b'previous output')
    with pytest.raises(ValueError, match='lack phase'):
        grid.save_ptm(path)
    assert path.read_bytes() == b'previous output'
    assert not list(tmp_path.glob('*.tmp'))


def test_ptm_zero_without_phase_exports_zero_and_cancel_is_atomic(tmp_path):
    grid = RcsGrid([0, 1], [0], np.linspace(1, 2, 40), ['VV'], rcs_power=np.zeros((2, 1, 40, 1)))
    out = grid.save_ptm(tmp_path / 'zero.ptm')
    assert not read_ptm(out).iq.any()
    before = Path(out).read_bytes()
    count = 0
    def cancelled():
        nonlocal count
        count += 1
        return count >= 3
    with pytest.raises(WorkCancelled), work_control(cancelled=cancelled):
        grid.save_ptm(out)
    assert Path(out).read_bytes() == before
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('storage', ['disk', 'auto'])
def test_folder_managed_sources_and_combined_result(tmp_path, storage):
    for index in range(2):
        grid = RcsGrid([index * 10, index * 10 + 1], [0], [1, 2], ['VV'],
                       rcs=np.full((2, 1, 2, 1), index + 1 + 1j))
        grid.save(tmp_path / f'part_{index}.grim')
    result = loaders.load_folder(tmp_path, pattern='part_*.grim', storage=storage,
                                  cache_dir=tmp_path, workers=2,
                                  ram_budget_bytes=1 if storage == 'auto' else 10 * 1024**2)
    assert array_storage(result._complex) == 'disk'
    np.testing.assert_array_equal(result.azimuths, [0, 1, 10, 11])
    np.testing.assert_array_equal(result.rcs_slice(Ellipsis)[:, 0, 0, 0], [1+1j, 1+1j, 2+1j, 2+1j])


def test_folder_worker_context_propagates_cancellation(tmp_path):
    for index in range(2):
        (tmp_path / f'{index}.ptm').write_bytes(b'placeholder')
    main = threading.get_ident()
    seen = []
    def cancelled():
        seen.append(threading.get_ident())
        return threading.get_ident() != main
    report = {'retained_bytes': 1, 'estimated_peak_bytes': 2}
    with mock.patch.object(loaders, '_folder_file_estimate', return_value=report):
        with pytest.raises(WorkCancelled):
            loaders.load_folder(tmp_path, workers=2, cancelled=cancelled)
    assert any(identity != main for identity in seen)


def test_text_cancel_releases_temporary_outputs(tmp_path):
    path = table(tmp_path, 'flat')
    count = 0
    def cancelled():
        nonlocal count
        count += 1
        return count >= 2
    with pytest.raises(WorkCancelled), work_control(cancelled=cancelled):
        loaders.load_dataset(path, storage='disk', cache_dir=tmp_path)
    gc.collect()
    assert not list(tmp_path.glob('grim-result-*'))


@pytest.mark.parametrize("kind", ["flat", "cst-flat", "sentri"])
def test_sparse_text_disk_budget_excludes_mapped_grid(tmp_path, kind):
    size = 512
    if kind == "flat":
        header = ["azimuth", "elevation", "frequency", "polarization", "magnitude_linear", "phase_deg"]
        rows = [[index / 10, 0, 1 + index / 1000, "VV", 2, 45] for index in range(size)]
        name = "sparse.csv"
    elif kind == "cst-flat":
        header = CST_FLAT
        rows = [[0, index / 10, 1 + index / 1000, "VV", 0, 45, ""] for index in range(size)]
        name = "sparse.cst_data"
    else:
        header = SENTRI_HEADER
        rows = [[1000 + index, 90, index / 10, 0, 45, -10, 90, -20, 180, -30, 270]
                for index in range(size)]
        name = "sparse_sentri.csv"
    path = write_rows(tmp_path / name, [header, *rows])
    disk = text_storage.estimate_text_import(path, storage="disk")
    memory = text_storage.estimate_text_import(path, storage="memory")
    assert disk["estimated_peak_bytes"] < memory["retained_bytes"]
    with pytest.raises(MemoryError):
        loaders.load_dataset(path, max_output_bytes=disk["estimated_peak_bytes"])
    tracemalloc.start()
    result = loaders.load_dataset(path, storage="disk", cache_dir=tmp_path,
                                   discovery_plan=disk["discovery_plan"],
                                   max_output_bytes=disk["estimated_peak_bytes"])
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < memory["retained_bytes"]
    assert all(array_storage(value) == "disk" for value in result.native_sample_payload().values()
               if isinstance(value, np.ndarray) and value.ndim == 4)
    assert np.isfinite(result.power_slice((0, 0, 0, 0)))
    assert np.isnan(result.power_slice((0, 0, 1, 0)))


def test_folder_auto_spills_combination_when_ram_inputs_leave_insufficient_room(tmp_path, monkeypatch):
    from GRIM_Backend.datasets import result_storage
    # Nine small native cuts let the retained batch exceed one reader's bounded
    # validation workspace, so all inputs fit but an additional union does not.
    paths = []
    for index in range(9):
        grid = RcsGrid([index], [0], np.linspace(1, 2, 128), ['VV'],
                       rcs=np.full((1, 1, 128, 1), index + 1 + 1j))
        paths.append(grid.save(tmp_path / f'part_{index}.grim'))
    plans = [loaders._folder_file_estimate(path, 'memory') for path in paths]
    retained = sum(plan['retained_bytes'] for plan in plans)
    workspace = max(plan['estimated_peak_bytes'] - plan['retained_bytes'] for plan in plans)
    budget = retained + workspace
    assert 9 * 128 * np.dtype(np.complex128).itemsize > workspace
    monkeypatch.setattr(result_storage, '_AUTO_RAM_BUDGET', 1024**3)
    original_load = loaders.load_dataset
    observed = []
    def load(path, **options):
        result = original_load(path, **options)
        observed.append((options['storage'], array_storage(result._complex)))
        return result
    with mock.patch.object(loaders, 'load_dataset', load):
        combined = loaders.load_folder(tmp_path, pattern='part_*.grim', storage='auto',
                                         ram_budget_bytes=budget, cache_dir=tmp_path)
    assert observed == [('memory', 'memory')] * 9
    assert array_storage(combined._complex) == 'disk'
    np.testing.assert_array_equal(combined.rcs_slice((slice(None), 0, 0, 0)),
                                  np.arange(1, 10) + 1j)


@pytest.mark.parametrize('storage,expected', [('auto', 'disk'), ('memory', 'memory'), ('disk', 'disk')])
def test_folder_auto_honors_shared_pressure_without_overriding_explicit_storage(tmp_path, monkeypatch, storage, expected):
    from GRIM_Backend.datasets import result_storage
    for index in range(2):
        RcsGrid([index], [0], [1, 2], ['VV'], rcs=np.full((1, 1, 2, 1), index + 1j)).save(
            tmp_path / f'part_{index}.grim')
    monkeypatch.setattr(result_storage, '_AUTO_RAM_BUDGET', 0)
    original_load = loaders.load_dataset
    observed = []
    def load(path, **options):
        observed.append(options['storage'])
        return original_load(path, **options)
    with mock.patch.object(loaders, 'load_dataset', load):
        result = loaders.load_folder(tmp_path, pattern='part_*.grim', storage=storage,
                                       ram_budget_bytes=1024**2, cache_dir=tmp_path)
    assert observed == [expected, expected]
    assert array_storage(result._complex) == expected
