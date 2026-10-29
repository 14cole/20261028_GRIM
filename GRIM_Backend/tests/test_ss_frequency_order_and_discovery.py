"""Descending SS sweeps load ascending; estimates hand their record scan to the load."""
import struct
from unittest import mock

import numpy as np
import pytest

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.work_control import WorkCancelled, work_control
from GRIM_Backend.execution import dataset_jobs
from GRIM_Backend.io import xpatch
from GRIM_Backend.io.binary_storage import BinaryDiscoveryPlan, estimate_binary_import
from GRIM_Backend.io.loaders import load_dataset, load_folder
from GRIM_Backend.tests.test_ss import build_ss


def _write_sweep(path, fields, coordinates, *, freq1, freq2, ifreq):
    """Write SS records whose frequency axis runs from freq1 to freq2."""
    fields = np.asarray(fields, dtype=np.complex64)
    n_signals, n_frequencies, _ = fields.shape
    metadata = build_ss(
        path, n_signals, n_frequencies, ifreq, freq1, freq2,
        dict(edge_diff=True, iqmatrix=True, ibspsave=3), "incident",
        sweep_values=[azimuth for azimuth, _ in coordinates], pre_frequency_padding=37)
    record_size = metadata["nbytesb"] + metadata["nbytesd"]
    with open(path, "r+b") as stream:
        for signal, (azimuth, elevation) in enumerate(coordinates):
            header_d = signal * record_size + metadata["nbytesb"]
            stream.seek(header_d + 280)
            stream.write(struct.pack(">ff", azimuth, elevation))
            stream.seek(header_d + 408)
            components = np.empty((n_frequencies, 4, 2), dtype=">f4")
            components[..., 0] = fields[signal].real
            components[..., 1] = fields[signal].imag
            stream.write(components.tobytes())


@pytest.mark.parametrize("ifreq", [1, 2])
@pytest.mark.parametrize("storage", ["memory", "disk"])
def test_descending_sweep_is_reordered_with_its_samples(tmp_path, ifreq, storage):
    samples = (np.arange(2 * 5 * 4, dtype=np.float32).reshape(2, 5, 4)
               + 1j * np.float32(0.5)).astype(np.complex64)
    samples[1, 2, 3] = np.nan + 1j * np.nan
    path = tmp_path / "descending.ss"
    _write_sweep(path, samples, [(0., 0.), (10., 0.)], freq1=12., freq2=8., ifreq=ifreq)
    grid = load_dataset(path, storage=storage, cache_dir=tmp_path)
    np.testing.assert_allclose(grid.frequencies, [8., 9., 10., 11., 12.])
    np.testing.assert_array_equal(grid.rcs[:, 0, :, :], samples[:, ::-1, :])
    assert grid.extra["ss_frequency_reordered"] is True
    assert "frequencies reordered ascending" in grid.history

    ascending = tmp_path / "ascending.ss"
    _write_sweep(ascending, samples, [(0., 0.), (10., 0.)], freq1=8., freq2=12., ifreq=ifreq)
    plain = load_dataset(ascending)
    np.testing.assert_array_equal(plain.rcs[:, 0, :, :], samples)
    assert plain.extra["ss_frequency_reordered"] is False
    assert "reordered" not in plain.history


def test_estimate_plan_skips_the_record_rescan_until_the_file_changes(tmp_path):
    samples = np.ones((3, 4, 4), dtype=np.complex64) * (1 + 2j)
    coordinates = [(0., 0.), (1., 0.), (2., 0.)]
    path = tmp_path / "scan.ss"
    _write_sweep(path, samples, coordinates, freq1=9., freq2=12., ifreq=2)
    report = estimate_binary_import(path, storage="disk")
    plan = report["discovery_plan"]
    assert isinstance(plan, BinaryDiscoveryPlan) and plan.source_format == "SS"
    assert "vv" not in plan.layout and plan.layout["sample_offsets"].size == 3
    with mock.patch.object(xpatch, "read_ss", side_effect=AssertionError("records were rescanned")):
        grid = load_dataset(path, storage="disk", cache_dir=tmp_path, discovery_plan=plan)
        again = estimate_binary_import(path, storage="memory", discovery_plan=plan)
    np.testing.assert_array_equal(grid.rcs[:, 0, :, :], samples)
    assert again["discovery_plan"].layout is plan.layout
    # A folder load plans every file, then loads it from that plan: one scan each.
    with mock.patch.object(xpatch, "read_ss", wraps=xpatch.read_ss) as scans:
        combined = load_folder(tmp_path, pattern="scan.ss", storage="auto")
    assert scans.call_count == 1
    np.testing.assert_array_equal(combined.rcs[:, 0, :, :], samples)
    del grid, combined

    plans = {}
    dataset_jobs._dataset_load_memory_estimate(str(path), discovery_plans=plans)
    assert isinstance(plans[str(path)], BinaryDiscoveryPlan)

    # A rewritten file has a new signature: the stale layout is not trusted.
    _write_sweep(path, samples * 2, coordinates, freq1=9., freq2=12., ifreq=2)
    rescanned = load_dataset(path, discovery_plan=plan)
    np.testing.assert_array_equal(rescanned.rcs[:, 0, :, :], samples * 2)


@pytest.mark.parametrize("extension", ["pio", "ss"])
def test_binary_decoding_reports_progress_and_observes_cancellation(tmp_path, extension):
    path = tmp_path / f"cancel.{extension}"
    if extension == "ss":
        _write_sweep(path, np.ones((3, 4, 4), np.complex64), [(0., 0.), (1., 0.), (2., 0.)],
                     freq1=9., freq2=12., ifreq=1)
        stages = {"Scanning SS records", "Reading SS samples"}
    else:
        grid = RcsGrid(np.arange(3) * 1., [0.], np.arange(4) * .1 + 8., ["VV"],
                       rcs=np.ones((3, 1, 4, 1), np.complex64))
        grid.save_pio(path)
        stages = {"Reading PIO samples"}
    details = set()
    with work_control(progress=lambda done, total, detail: details.add(detail)):
        load_dataset(path)
    assert stages <= details
    with work_control(cancelled=lambda: True):
        with pytest.raises(WorkCancelled):
            load_dataset(path)
