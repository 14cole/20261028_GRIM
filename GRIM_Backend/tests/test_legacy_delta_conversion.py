"""The retired GHOST "delta" concept: conversion on load, no gates, migration.

Legacy GHOST deltas were tagged ``power_domain='delta_amp_sq'`` and
``rcs_domain='delta'``; their stored amplitude ``A`` already was physical
(physical power ``|A|**2``). GRIM converts them once, in the native loader,
into ordinary physical datasets, and nothing else special-cases them.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from GRIM_Backend.datasets import transforms
from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.io.native import LEGACY_DELTA_HISTORY_NOTE

REPO_ROOT = Path(__file__).resolve().parents[2]
AZ, EL, FR, POL = np.array([0.0, 10.0, 20.0]), np.array([0.0]), np.array([1.0, 3.0]), ["VV", "HH"]
SHAPE = (3, 1, 2, 2)
UNITS = {
    "sigma_3d": {"azimuth": "deg", "elevation": "deg", "frequency": "GHz",
                 "rcs_linear_quantity": "sigma_3d", "rcs_log_unit": "dBsm"},
    "sigma_2d": {"azimuth": "deg", "elevation": "deg", "frequency": "GHz",
                 "rcs_linear_quantity": "sigma_2d", "rcs_log_unit": "dBke"},
}


def _amplitude(seed=3):
    rng = np.random.default_rng(seed)
    return (rng.normal(size=SHAPE) + 1j * rng.normal(size=SHAPE)) * 0.25


def legacy_payload(layout, quantity, amplitude):
    data = dict(azimuths=AZ, elevations=EL, frequencies=FR, polarizations=np.asarray(POL),
                units=json.dumps(UNITS[quantity]), power_domain="delta_amp_sq",
                rcs_domain="delta", history="ghost delta", source_path="")
    if layout == "c":
        data.update(grim_format_version=np.int16(2), storage_kind="complex",
                    storage_domain="raw_field", rcs_complex=amplitude)
    else:
        data.update(rcs_power=np.abs(amplitude) ** 2, rcs_phase=np.angle(amplitude))
        if layout == "b":
            data.update(rcs_amp_real=amplitude.real, rcs_amp_imag=amplitude.imag,
                        raw_complex_amplitude_preserved=True)
    return data


def write(path, data):
    with open(path, "wb") as stream:
        np.savez(stream, **data)
    return path


LAYOUTS = ["a", "b", "c"]
QUANTITIES = ["sigma_3d", "sigma_2d"]


@pytest.mark.parametrize("quantity", QUANTITIES)
@pytest.mark.parametrize("layout", LAYOUTS)
def test_legacy_delta_is_converted_to_physical_on_load(tmp_path, layout, quantity):
    amplitude = _amplitude()
    path = write(tmp_path / f"{layout}.grim", legacy_payload(layout, quantity, amplitude))
    grid = RcsGrid.load(path)
    np.testing.assert_allclose(np.asarray(grid.power), np.abs(amplitude) ** 2, rtol=1e-12)
    np.testing.assert_allclose(np.angle(np.exp(1j * (np.asarray(grid.phase) - np.angle(amplitude)))),
                               0.0, atol=1e-12)
    assert "power_domain" not in grid.extra and "rcs_domain" not in grid.extra
    assert "rcs_amp_real" not in grid.extra and "rcs_amp_imag" not in grid.extra
    assert grid.storage_domain == "physical"
    # Power/phase-only data keep their samples (GRIM may canonicalize them
    # to complex storage exactly as for any power/phase file).
    assert grid.storage_kind in ({"power_phase", "complex"} if layout == "a" else {"complex"})
    assert LEGACY_DELTA_HISTORY_NOTE in str(grid.history)
    if layout != "a":
        np.testing.assert_allclose(np.asarray(grid.rcs), amplitude, rtol=1e-12)

    saved = grid.save(tmp_path / f"saved_{layout}.grim")
    with np.load(saved) as archive:
        assert str(archive["power_domain"]) == "linear_rcs"
        assert str(archive["rcs_domain"]) in {"complex_amplitude", "power_phase", "linear_rcs"}
        assert int(archive["grim_format_version"]) == 2
    reloaded = RcsGrid.load(saved)
    np.testing.assert_allclose(np.asarray(reloaded.power), np.abs(amplitude) ** 2, rtol=1e-12)
    assert str(reloaded.history).count(LEGACY_DELTA_HISTORY_NOTE) == 1


@pytest.mark.parametrize("layout", LAYOUTS)
def test_disk_and_region_loads_convert_the_same_way(tmp_path, layout):
    amplitude = _amplitude()
    path = write(tmp_path / "d.grim", legacy_payload(layout, "sigma_2d", amplitude))
    disk = RcsGrid.load(path, storage="disk", cache_dir=tmp_path)
    np.testing.assert_allclose(np.asarray(disk.power), np.abs(amplitude) ** 2, rtol=1e-12)
    region = RcsGrid.load(path, selection={"frequency": (3.0, 3.0), "polarization": ["HH"]})
    np.testing.assert_allclose(np.asarray(region.power)[..., 0, 0], np.abs(amplitude[..., 1, 1]) ** 2,
                               rtol=1e-12)


def test_embedded_payload_decoder_converts_legacy_arrays():
    amplitude = _amplitude()
    grid = RcsGrid._from_native_arrays(legacy_payload("c", "sigma_3d", amplitude), path="embedded")
    np.testing.assert_allclose(np.asarray(grid.power), np.abs(amplitude) ** 2, rtol=1e-12)


def test_converted_legacy_delta_behaves_as_ordinary_data_in_operations(tmp_path):
    amplitude = _amplitude()
    path = write(tmp_path / "c.grim", legacy_payload("c", "sigma_2d", amplitude))
    grid = RcsGrid.load(path)
    shifted = transforms.shift_dataset(grid, phase_degrees=30.0)
    np.testing.assert_allclose(np.asarray(shifted.power), np.abs(amplitude) ** 2, rtol=1e-12)
    ordinary = RcsGrid(AZ, EL, FR, POL, rcs=amplitude, units=dict(UNITS["sigma_2d"]))
    difference = grid.coherent_subtract(ordinary)
    np.testing.assert_allclose(np.asarray(difference.power), 0.0, atol=1e-24)


def test_in_memory_tags_have_no_special_scaling():
    """Only the loader recognizes the legacy tags; a constructed grid is ordinary."""
    raw = _amplitude()
    grid = RcsGrid(AZ, EL, FR, POL, rcs=raw, rcs_storage_domain="raw_field",
                   units=dict(UNITS["sigma_3d"]),
                   extra={"power_domain": "delta_amp_sq", "rcs_domain": "delta"})
    np.testing.assert_allclose(np.asarray(grid.power), 4.0 * np.pi * np.abs(raw) ** 2, rtol=1e-12)


def test_bare_delta_rcs_domain_tag_is_dropped_on_load(tmp_path):
    amplitude = _amplitude()
    data = legacy_payload("a", "sigma_3d", amplitude)
    data["power_domain"] = "linear_rcs"
    grid = RcsGrid.load(write(tmp_path / "tag.grim", data))
    assert "rcs_domain" not in grid.extra
    np.testing.assert_allclose(np.asarray(grid.power), np.abs(amplitude) ** 2, rtol=1e-12)
    with np.load(grid.save(tmp_path / "tag_saved.grim")) as archive:
        assert str(archive["rcs_domain"]) != "delta"


def test_response_comparison_reads_a_legacy_delta_through_the_loader(tmp_path):
    from GRIM_Backend.assembly.response_comparison import read_response_cut
    amplitude = _amplitude()
    path = write(tmp_path / "cmp.grim", legacy_payload("c", "sigma_3d", amplitude))
    az, db = read_response_cut(path, frequency=3.0, elevation=0.0, polarization="HH")
    np.testing.assert_array_equal(az, AZ)
    np.testing.assert_allclose(db, 10.0 * np.log10(np.abs(amplitude[:, 0, 1, 1]) ** 2), rtol=1e-12)


# --- No gate depends on delta tags or feature-delta roles ----------------------

def _assembly_pair(delta_base_response_hash):
    metadata = {"phase_reference": "fixed origin, exp(+jwt)",
                "amplitude_convention": "F raw solver amplitude",
                "complex_field_domain": "coherent radar frame far field amplitude"}
    values = np.array([1 + 2j, 3 - 4j, 5 + 6j, 7 + 8j, 9 + 10j, 11 - 12j]).reshape(1, 1, 2, 3)
    body = RcsGrid([0.], [0.], [8., 9.], ["VV", "HH", "VH"], rcs=values,
                   units={"rcs_linear_quantity": "sigma_3d"}, extra=dict(metadata))
    delta = RcsGrid([0.], [0.], [8., 9.], ["VV", "HH", "VH"], rcs=values * .1,
                    units=body.units,
                    extra={**metadata, "assembly_response_role": "features_only_delta",
                           "assembly_base_sha256": "a" * 64,
                           "assembly_base_response_sha256": delta_base_response_hash})
    return body, delta


def test_features_only_delta_without_its_matching_body_is_not_blocked():
    from GRIM_Backend.assembly.tree import _assert_no_shared_body_totals
    body, delta = _assembly_pair("b" * 64)
    _assert_no_shared_body_totals([body, delta])
    other_body, other_delta = _assembly_pair("c" * 64)
    _assert_no_shared_body_totals([body, delta, other_delta])


def test_feature_delta_with_incomplete_provenance_is_not_blocked():
    from GRIM_Backend.assembly.tree import _assert_no_shared_body_totals, _feature_delta_context
    body, delta = _assembly_pair("b" * 64)
    delta.extra.pop("assembly_base_sha256")
    delta.extra.pop("assembly_base_response_sha256")
    _feature_delta_context(delta)
    _assert_no_shared_body_totals([body, delta])


def test_coherent_tree_sum_of_delta_and_unrelated_body_runs():
    from GRIM_Backend.assembly.tree import _combined_semantic_extra
    body, delta = _assembly_pair("b" * 64)
    extra = _combined_semantic_extra([body, delta], [body, delta], has_coh=True, has_incoh=False,
                                     coherent_metadata_attested=True)
    assert extra["combine_role"] == "coherent"


def test_join_of_different_response_roles_is_not_blocked():
    left = RcsGrid([0.], [0.], [8.], ["VV"], rcs=np.full((1, 1, 1, 1), 1 + 1j),
                   units={"rcs_linear_quantity": "sigma_3d"},
                   extra={"assembly_response_role": "features_only_delta"})
    right = RcsGrid([10.], [0.], [8.], ["VV"], rcs=np.full((1, 1, 1, 1), 2 + 1j),
                    units={"rcs_linear_quantity": "sigma_3d"},
                    extra={"assembly_response_role": "body_plus_features"})
    joined = RcsGrid.join_many(left, right)
    np.testing.assert_allclose(np.asarray(joined.power)[:, 0, 0, 0], [2.0, 5.0])


# --- Migration tool --------------------------------------------------------------

def _scanner():
    spec = importlib.util.spec_from_file_location("scan_legacy_delta", REPO_ROOT / "scan_legacy_delta.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scanner_without_convert_is_read_only(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    path = write(source / "c.grim", legacy_payload("c", "sigma_3d", _amplitude()))
    before = path.read_bytes()
    records = _scanner().main([str(source)])
    assert records[path.resolve()][0] == "AT-RISK SOURCE"
    assert path.read_bytes() == before
    assert sorted(p.name for p in source.iterdir()) == ["c.grim"]


def test_scanner_convert_writes_standard_copies_and_report(tmp_path):
    source = tmp_path / "data"
    (source / "sub").mkdir(parents=True)
    amplitude = _amplitude()
    originals = {}
    for layout, quantity in (("a", "sigma_3d"), ("b", "sigma_2d"), ("c", "sigma_2d")):
        path = write(source / "sub" / f"{layout}.grim", legacy_payload(layout, quantity, amplitude))
        originals[path] = path.read_bytes()
    ordinary = RcsGrid(AZ, EL, FR, POL, rcs=amplitude, units=dict(UNITS["sigma_3d"]))
    ordinary.save(source / "ordinary.grim")
    out = tmp_path / "converted"
    result = _scanner().main([str(source), "--convert", str(out)])

    for path, data in originals.items():
        assert path.read_bytes() == data
    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    converted = {Path(entry["source"]).name: entry for entry in report["files"]}
    assert set(converted) == {"a.grim", "b.grim", "c.grim"}
    for name, entry in converted.items():
        assert entry["status"] == "converted", entry
        assert entry["max_relative_power_error"] < 1e-12
        assert entry["output_tags"]["power_domain"] == "linear_rcs"
        assert entry["output_tags"]["rcs_domain"] != "delta"
        assert entry["output_tags"]["grim_format_version"] == "2"
        target = Path(entry["output"])
        assert target == (out / "data" / "sub" / name).resolve()
        grid = RcsGrid.load(target)
        np.testing.assert_allclose(np.asarray(grid.power), np.abs(amplitude) ** 2, rtol=1e-12)

    # A second run never overwrites the converted copies.
    stamp = {Path(entry["output"]): Path(entry["output"]).stat().st_mtime_ns
             for entry in report["files"]}
    again = _scanner().main([str(source), "--convert", str(out)])
    assert all(entry["status"].startswith("skipped") for entry in again["files"])
    assert all(path.stat().st_mtime_ns == mtime for path, mtime in stamp.items())
    assert Path(again["report_path"]) != Path(result["report_path"])


def test_scanner_convert_never_targets_an_original(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    path = write(source / "c.grim", legacy_payload("c", "sigma_3d", _amplitude()))
    before = path.read_bytes()
    result = _scanner().main([str(source), "--convert", str(tmp_path)])
    assert result["files"][0]["status"].startswith("skipped")
    assert path.read_bytes() == before
