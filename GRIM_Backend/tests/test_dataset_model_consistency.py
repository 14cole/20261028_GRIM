"""One file, one representation; grids that cannot be saved cannot be built."""
import json

import numpy as np
import pytest

from GRIM_Backend.datasets.grid import RcsGrid

UNITS = {"azimuth": "deg", "elevation": "deg", "frequency": "GHz",
         "rcs_log_unit": "dBsm", "rcs_linear_quantity": "sigma_3d"}


def _write_v1(path, power, phase):
    with open(path, "wb") as stream:
        np.savez(stream, azimuths=np.arange(float(power.shape[0])), elevations=np.array([0.0]),
                 frequencies=np.array([10.0]), polarizations=np.array(["VV"]),
                 rcs_power=power, rcs_phase=phase, units=np.array(json.dumps(UNITS)),
                 grim_format_version=np.array(1))
    return path


def _loads(path, tmp_path):
    memory = RcsGrid.load(path)
    disk = RcsGrid.load(path, storage="disk", cache_dir=tmp_path)
    region = RcsGrid.load(path, selection={"azimuth": (0, 1)})
    return memory, disk, region


def test_ram_and_disk_loads_choose_the_same_representation(tmp_path):
    power = np.array([1.0, 2.0, 4.0]).reshape(3, 1, 1, 1)
    phase = np.array([0.0, 0.5, -1.0]).reshape(3, 1, 1, 1)
    path = _write_v1(tmp_path / "recoverable.grim", power, phase)
    memory, disk, region = _loads(path, tmp_path)
    assert memory.storage_kind == disk.storage_kind == "complex"
    np.testing.assert_allclose(disk.rcs, memory.rcs, rtol=0, atol=0)
    # A region keeps the stored samples exactly (see test_native_load_options).
    np.testing.assert_array_equal(region.power[...], power[:2])


def test_exceptional_phase_stays_polar_on_every_route(tmp_path):
    power = np.array([1.0, 0.0, 4.0]).reshape(3, 1, 1, 1)
    phase = np.array([0.0, 1.0, -1.0]).reshape(3, 1, 1, 1)      # zero power, nonzero phase
    path = _write_v1(tmp_path / "exceptional.grim", power, phase)
    memory, disk, region = _loads(path, tmp_path)
    assert memory.storage_kind == disk.storage_kind == region.storage_kind == "power_phase"
    np.testing.assert_array_equal(disk.phase[...], memory.phase[...])


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_axis_coordinates_are_rejected_at_construction(bad):
    with pytest.raises(ValueError, match="azimuth axis contains a nonfinite coordinate"):
        RcsGrid([0.0, bad], [0.0], [10.0], ["VV"], rcs_power=np.ones((2, 1, 1, 1)))
    with pytest.raises(ValueError, match="frequency axis contains a nonfinite coordinate"):
        RcsGrid([0.0], [0.0], [bad], ["VV"], rcs_power=np.ones((1, 1, 1, 1)))


def test_rcs_domain_follows_the_stored_samples(tmp_path):
    power_only = RcsGrid([0.0], [0.0], [10.0], ["VV"], rcs_power=np.ones((1, 1, 1, 1)),
                         rcs_domain="power_phase", units=UNITS)
    assert power_only.storage_kind == "power" and power_only.rcs_domain == "linear_rcs"
    field = RcsGrid([0.0], [0.0], [10.0], ["VV"], rcs=np.ones((1, 1, 1, 1), complex),
                    rcs_domain="power_phase", units=UNITS)
    assert field.rcs_domain == "complex_amplitude"
    polar = RcsGrid([0.0, 1.0], [0.0], [10.0], ["VV"],
                    rcs_power=np.array([1.0, 0.0]).reshape(2, 1, 1, 1),
                    rcs_phase=np.array([0.0, 1.0]).reshape(2, 1, 1, 1), units=UNITS)
    assert polar.rcs_domain == "power_phase"
    field.rcs_domain = "linear_rcs"            # accepted, but cannot contradict the data
    assert field.rcs_domain == "complex_amplitude"
    saved = field.save(tmp_path / "field.grim")
    with np.load(saved) as archive:
        assert str(archive["rcs_domain"]) == field.rcs_domain
