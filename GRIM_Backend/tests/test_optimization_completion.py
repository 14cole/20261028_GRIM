"""Accuracy, allocation, lifetime, and cancellation for optimized core paths."""
import gc
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import numpy as np
import pytest

from GRIM_Backend.datasets import axes, transforms, result_storage as storage
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.work_control import WorkCancelled, checkpoint, work_control


def source(shape=(64, 1, 512, 1)):
    values = np.arange(np.prod(shape)).reshape(shape)
    return RcsGrid(np.arange(shape[0]), np.arange(shape[1]),
                   8. + np.arange(shape[2]) * .01, ['HH'][:shape[3]],
                   rcs=(1 + values % 7) * np.exp(1j * values * .01))


@pytest.mark.parametrize('axis', [0, 1, 2])
def test_interpolation_gathers_bounded_samples_without_source_materialization(axis):
    class Lazy:
        shape = (70, 80, 90, 1)
        dtype = np.dtype('float64')
        def __array__(self, *args, **kwargs):
            raise AssertionError('must not materialize lazy source')
        def __getitem__(self, selection):
            result = sum(selection)
            assert result.size <= axes._RESULT_BLOCK_CELLS
            return result.astype(float)
    old = np.arange(Lazy.shape[axis], dtype=float)
    new = old[::3] + .25
    new = new[new <= old[-1]]
    actual = RcsGrid._interp_linear_axis(Lazy(), old, new, axis)
    coordinates = [np.arange(n) for n in Lazy.shape]
    coordinates[axis] = new
    np.testing.assert_allclose(actual, sum(np.ix_(*coordinates)), rtol=0, atol=1e-12)


def test_regrid_does_not_allocate_full_source_field():
    grid = source()
    sizes = []
    allocate = axes.allocate_result
    def capture(shape, dtype, **kwargs):
        sizes.append((tuple(shape), np.dtype(dtype)))
        return allocate(shape, dtype, **kwargs)
    with mock.patch.object(axes, 'allocate_result', capture):
        result = grid.interpolate_axis('frequency', grid.frequencies[::8])
    assert not any(shape == grid.shape and dtype.kind == 'c' for shape, dtype in sizes)
    np.testing.assert_allclose(result.rcs, grid.rcs[:, :, ::8, :], rtol=0, atol=0)


def test_time_gate_adopts_finished_field_and_cleans_missing_values():
    grid = source((8, 1, 32, 1))
    values = np.array(grid.rcs)
    values[0, 0, 0, 0] = np.nan + 1j * np.nan
    grid = RcsGrid(grid.azimuths, grid.elevations, grid.frequencies, grid.polarizations, rcs=values)
    buffers = []
    allocate = transforms.allocate_result
    def capture(shape, dtype, **kwargs):
        result = allocate(shape, dtype, **kwargs)
        buffers.append(result)
        return result
    with mock.patch.object(transforms, 'allocate_result', capture):
        result = transforms.time_gate(grid, start_m=-1, stop_m=1)
    field = next(buffer for buffer in buffers if buffer.shape == grid.shape and buffer.dtype.kind == 'c')
    assert np.shares_memory(result.native_sample_payload()['rcs_complex'], field)
    assert np.all(np.isnan(result.rcs[0].real))
    assert np.all(np.isnan(result.rcs[0].imag))
    assert np.all(np.isfinite(result.rcs[1:]))


def test_median_reuses_source_samples_and_keeps_exact_windows():
    grid = source((3600, 1, 16, 1))
    grid = RcsGrid(np.arange(3600) * .1, grid.elevations, grid.frequencies,
                   grid.polarizations, rcs=grid.rcs)
    read = grid.power_slice
    count = 0
    def capture(selection):
        nonlocal count
        result = read(selection)
        count += result.size
        return result
    with mock.patch.object(grid, 'power_slice', capture):
        result = transforms.medianize_azimuth(grid, window_degrees=5, slide_degrees=.1, periodic=True)
    assert count <= grid.size * 2
    power = np.asarray(grid.power)
    for i in (0, 1, 537, 1799, 3599):
        delta = (grid.azimuths - result.azimuths[i] + 180) % 360 - 180
        selected = np.abs(delta) <= 2.5 + 1e-10
        np.testing.assert_allclose(result.power[i], np.nanmedian(power[selected], axis=0), rtol=0, atol=0)


def test_application_allowance_spans_operations_and_plain_aliases(tmp_path):
    gc.collect()
    before = storage.application_result_storage_info()['reserved_ram_bytes']
    try:
        storage.configure_auto_ram_budget(before + 16)
        with storage.operation_result_storage('auto', ram_budget_bytes=1000, cache_dir=tmp_path):
            first = storage.allocate_result(2, np.float64)
            alias = np.asarray(first)[1:]
        del first
        gc.collect()
        with storage.operation_result_storage('auto', ram_budget_bytes=1000, cache_dir=tmp_path):
            second = storage.allocate_result(1, np.float64)
        assert storage.array_storage(second) == 'disk'
        del alias
        gc.collect()
        with storage.operation_result_storage('auto', ram_budget_bytes=1000, cache_dir=tmp_path):
            third = storage.allocate_result(2, np.float64)
        assert storage.array_storage(third) == 'memory'
    finally:
        storage.configure_auto_ram_budget()


def test_application_allowance_is_atomic_across_workers(tmp_path):
    gc.collect()
    before = storage.application_result_storage_info()['reserved_ram_bytes']
    try:
        storage.configure_auto_ram_budget(before + 8)
        def allocate(_):
            with storage.operation_result_storage('auto', ram_budget_bytes=1000, cache_dir=tmp_path):
                return storage.allocate_result(1, np.float64)
        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(allocate, range(16)))
        assert sum(storage.array_storage(value) == 'memory' for value in values) == 1
        with storage.operation_result_storage('memory'):
            explicit = storage.allocate_result(32, np.float64)
        assert storage.array_storage(explicit) == 'memory'
    finally:
        storage.configure_auto_ram_budget()


def test_cancel_mid_tile_releases_managed_destination(tmp_path):
    checks = 0
    def canceled():
        nonlocal checks
        checks += 1
        return checks > 3
    with pytest.raises(WorkCancelled):
        with storage.operation_result_storage('disk', cache_dir=tmp_path), work_control(cancelled=canceled):
            storage.allocate_result((500_000,), np.float64, fill=0)
    gc.collect()
    assert not list(tmp_path.glob('grim-result-*'))


def test_nested_work_control_inherits_callbacks_and_reports_completion():
    reports = []
    with work_control(progress=lambda *args: reports.append(args)):
        with work_control():
            checkpoint(1, 1, 'Complete')
    assert reports == [(1, 1, 'Complete')]
    checkpoint()


def test_large_native_progress_fits_qt_signal_integer_range():
    from GRIM_Backend.execution import dataset_jobs as jobs
    worker = jobs._DatasetLoadWorker([])
    values = []
    worker.progress.connect(lambda *args: values.append(args))
    jobs._emit_stage_progress(worker, 3 * 1024**3, 6 * 1024**3, 'Decoding native samples')
    assert values == [(5000, 10000, 'Decoding native samples')]


def test_background_callable_cancels_inside_bounded_loop():
    from GRIM_Backend.execution import dataset_jobs as jobs
    thread = mock.Mock()
    thread.isInterruptionRequested.side_effect = [False, False, False, True]
    worker = jobs._BackgroundCallableWorker(lambda: storage.allocate_result(200_000, float, fill=1))
    results = []
    worker.finished.connect(results.append)
    with mock.patch.object(jobs.QThread, 'currentThread', return_value=thread):
        worker.run()
    assert results == [{'ok': False, 'cancelled': True}]


def test_workers_canceled_before_start_emit_one_terminal_result(tmp_path):
    from GRIM_Backend.execution import dataset_jobs as jobs
    grid = source((2, 1, 4, 1))
    path = tmp_path / 'export.csv'
    workers = [jobs._DatasetLoadWorker([(0, 'not-needed.grim')]),
               jobs._CsvExportWorker([(grid, str(path))], scale='linear', include_phase=True),
               jobs._JoinDatasetsWorker([grid, grid])]
    thread = mock.Mock()
    thread.isInterruptionRequested.return_value = True
    for worker in workers:
        results = []
        worker.finished.connect(results.append)
        with mock.patch.object(jobs.QThread, 'currentThread', return_value=thread):
            worker.run()
        assert len(results) == 1 and results[0]['cancelled']
    assert not path.exists()


@pytest.mark.parametrize('compressed', [False, True])
def test_native_stream_cancellation_preserves_existing_target(tmp_path, compressed):
    from GRIM_Backend.io.native import _CheckpointStream
    grid = source((16, 1, 64, 1))
    target = tmp_path / 'existing.grim'
    target.write_bytes(b'original')
    canceled = False
    write = _CheckpointStream.write
    def stop_after_write(stream, value):
        nonlocal canceled
        result = write(stream, value)
        canceled = True
        return result
    with mock.patch.object(_CheckpointStream, 'write', stop_after_write):
        with work_control(cancelled=lambda: canceled), pytest.raises(WorkCancelled):
            grid.save(target, compressed=compressed)
    assert target.read_bytes() == b'original'
    assert not list(tmp_path.glob('.grim-write-*'))


def test_native_mapped_decode_cancellation_releases_private_cache(tmp_path):
    grid = source((16, 1, 64, 1))
    path = grid.save(tmp_path / 'source')
    canceled = False
    def progress(done, total, detail):
        nonlocal canceled
        if detail == 'Decoding native samples':
            canceled = True
    with work_control(cancelled=lambda: canceled, progress=progress), pytest.raises(WorkCancelled):
        RcsGrid.load(path, storage='disk', cache_dir=tmp_path)
    gc.collect()
    assert not list(tmp_path.glob('grim-native-*'))
