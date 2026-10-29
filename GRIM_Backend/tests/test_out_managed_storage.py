"""OUT tables plan from discovered axes and decode into managed, bounded storage."""
import gc
import tracemalloc

import numpy as np
import pytest

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.datasets.work_control import work_control
from GRIM_Backend.execution import dataset_jobs
from GRIM_Backend.io import text_storage
from GRIM_Backend.io.loaders import load_dataset


def _write_out(path, azimuths, frequencies, *, header="# polarization: VV\n"):
    lines = [header]
    for frequency in frequencies:
        for azimuth in azimuths:
            lines.append(f"{frequency:.6g} {azimuth:.6g} {-20.0 + azimuth / 100.0:.6g} {azimuth:.6g}\n")
    path.write_text("".join(lines), encoding="utf-8")


def test_out_estimate_uses_discovered_axes_and_disk_keeps_samples_mapped(tmp_path):
    path = tmp_path / "sweep.out"
    _write_out(path, np.linspace(-45.0, 45.0, 300), np.linspace(9.0, 11.0, 600))
    estimate = text_storage.estimate_text_import(path, storage="disk")
    assert estimate["source_format"] == "OUT"
    assert tuple(estimate["shape"]) == (300, 1, 600, 1)
    assert estimate["estimated_peak_bytes"] < estimate["retained_bytes"] + 300 * 600 * 16 * 2
    retained, peak = dataset_jobs._dataset_load_memory_estimate(str(path), storage="memory")
    assert retained == text_storage.estimate_text_import(path)["retained_bytes"] > 0
    with pytest.raises(MemoryError, match="exceeding"):
        load_dataset(path, max_output_bytes=peak - 1)

    cache = tmp_path / "cache"
    cache.mkdir()
    gc.collect()
    tracemalloc.start()
    resident = load_dataset(path)
    _, resident_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert resident.sample_storage == "memory"
    gc.collect()
    tracemalloc.start()
    mapped = load_dataset(path, storage="disk", cache_dir=cache,
                          discovery_plan=estimate["discovery_plan"])
    _, mapped_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert mapped.sample_storage == "disk" and mapped.load_storage == "disk"
    # Parsed power, phase and duplicate-tracking arrays are mapped, not resident.
    assert mapped_peak < resident_peak * 0.5
    for name in ("azimuths", "elevations", "frequencies", "polarizations", "power", "phase"):
        np.testing.assert_array_equal(getattr(mapped, name), getattr(resident, name))
    assert mapped.extra["source_format"] == "OUT"
    assert mapped.extra["dense_import_peak_bytes"] == estimate["estimated_peak_bytes"]
    assert list(cache.iterdir())
    del mapped
    gc.collect()
    assert not list(cache.iterdir())


def test_out_rows_report_progress_and_keep_former_error_order(tmp_path):
    path = tmp_path / "sample_HH.out"
    _write_out(path, [0.0, 1.0], [10.0], header="")
    details = set()
    with work_control(progress=lambda done, total, detail: details.add(detail)):
        grid = RcsGrid.load_out(path)
    assert grid.polarizations.tolist() == ["HH"]
    # Progress checkpoints only fire for larger tables; this one just loads.
    bad = tmp_path / "bad.out"
    bad.write_text("# polarization: VV\n10 0 20 0\n10 0 999999 0\nnot a row\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 4: expected exactly 4 columns"):
        RcsGrid.load_out(bad)
    conflicting = tmp_path / "conflict.out"
    conflicting.write_text("10 0 20 0\n10 0 21 0\n10 1 999999 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="conflicting duplicate"):
        RcsGrid.load_out(conflicting)
