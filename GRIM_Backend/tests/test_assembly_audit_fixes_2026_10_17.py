"""Regressions for the 2026-10-17 assembly-tree audit (modes, interp, metadata)."""

import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from GRIM_Backend.assembly import tree as T
from GRIM_Backend.datasets.grid import RcsGrid

C0 = 299792458.0
AZ = np.arange(0.0, 360.0, 5.0)


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


class _Node:
    def __init__(self, name, ntype, mode=None, grid=None, children=()):
        self._name = name
        self._d = {T._ROLE_TYPE: ntype, T._ROLE_MODE: mode, T._ROLE_GRID: grid,
                   T._ROLE_PURPOSE: T._PURPOSE_RESPONSE}
        self._children = list(children)

    def text(self, column):
        return self._name

    def data(self, column, role):
        return self._d.get(role)

    def childCount(self):
        return len(self._children)

    def child(self, index):
        return self._children[index]

    def parent(self):
        return None

    def checkState(self, column):
        return Qt.Checked


def _leaf(name, grid, mode):
    return _Node(name, T._TYPE_LEAF, mode, grid)


def _root(*children):
    return _Node("root", T._TYPE_ROOT, None, None, children)


def _point(r, az=AZ, pols=("VV", "HH", "VH"), amp=1.0, extra=None):
    az = np.asarray(az, float)
    a = np.deg2rad(az)[:, None, None]
    k = 2 * np.pi * 10.0e9 / C0
    field = amp * np.exp(2j * k * (np.cos(a) * r[0] + np.sin(a) * r[1]))
    data = np.repeat(field[..., None], len(pols), -1).astype(complex)
    for i in range(len(pols)):
        data[..., i] *= 1.0 + 0.1 * i
    units = {"azimuth": "deg", "elevation": "deg", "frequency": "GHz"}
    return RcsGrid(az, [0.0], [10.0], list(pols), rcs=data, units=units,
                   extra=dict(extra or {})), data


def _clean_and_delta():
    clean, dc = _point([0.0, 0.0])
    _f, df = _point([0.2, 0.1], amp=0.3)
    featured = RcsGrid(AZ, [0.0], [10.0], ["VV", "HH", "VH"], rcs=dc + df,
                       units=dict(clean.units))
    return clean, dc, featured.coherent_subtract(clean), df


# 1a. coherent_subtract deltas declare a coherent combine role ---------------

def test_coherent_subtract_delta_defaults_to_field_add_and_survives_save():
    _clean, _dc, delta, _df = _clean_and_delta()
    assert delta.extra["combine_role"] == "coherent"
    assert T._mode_for_grid(delta) == T._MODE_COH
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "delta.grim")
        delta.save(path)
        loaded = RcsGrid.load(path)
    assert T._mode_for_grid(loaded) == T._MODE_COH
    # A later power operation must not keep claiming a coherent role.
    assert delta.incoherent_add(_clean).extra["combine_role"] == "power"


def test_body_plus_delta_built_coherently_is_exact():
    clean, dc, delta, df = _clean_and_delta()
    grid, _history = T.build_assembly_grid(
        _root(_leaf("clean", clean, T._MODE_COH),
              _leaf("delta", delta, T._mode_for_grid(delta)))
    )
    np.testing.assert_allclose(grid.power, np.abs(dc + df) ** 2, rtol=1e-12)


# 1b. Power + leaf with complete phase is flagged in the build report ---------

def test_power_add_leaf_with_phase_is_reported():
    clean, _dc, delta, _df = _clean_and_delta()
    report = []
    _grid, history = T.build_assembly_grid(
        _root(_leaf("clean", clean, T._MODE_INCOH),
              _leaf("delta", delta, T._MODE_COH)),
        report=report,
    )
    assert any("'clean' carries complete phase" in line for line in report)
    assert "'clean' carries complete phase" in history
    assert not any("'delta' carries" in line for line in report)


def test_power_only_leaf_is_not_flagged():
    a, _ = _point([0.0, 0.0])
    p = RcsGrid(AZ, [0.0], [10.0], ["VV", "HH", "VH"], rcs_power=a.power,
                units=dict(a.units))
    report = []
    T.build_assembly_grid(
        _root(_leaf("a", p, T._MODE_INCOH), _leaf("b", p, T._MODE_INCOH)),
        report=report,
    )
    assert not any("carries complete phase" in line for line in report)


# 2. Interpolate resamples power of Power + children, never their I/Q --------

def test_interp_resamples_incoherent_power_not_iq():
    a, _ = _point([0.0, 0.0], az=np.arange(0, 360, 1.0))
    b, _ = _point([0.3, 0.0], az=np.arange(0, 360, 5.0), amp=0.5)
    grid, _ = T.build_assembly_grid(
        _root(_leaf("a", a, T._MODE_INCOH), _leaf("b", b, T._MODE_INCOH)),
        axis_mode="interp",
    )
    np.testing.assert_allclose(grid.power[:, 0, 0, 0] - 1.0, 0.25, rtol=1e-9)


# 3. Metadata conflicts ------------------------------------------------------

def test_time_convention_conflict_refuses_field_add():
    a, _ = _point([0.0, 0.0], extra={"time_convention": "exp(+jwt)"})
    b, _ = _point([0.1, 0.0], amp=0.5, extra={"time_convention": "exp(-jwt)"})
    with pytest.raises(ValueError, match="different time conventions.*'a'.*'b'"):
        T.build_assembly_grid(
            _root(_leaf("a", a, T._MODE_COH), _leaf("b", b, T._MODE_COH))
        )


def test_time_convention_conflict_refuses_coherent_subtract():
    a, _ = _point([0.0, 0.0], extra={"time_convention": "exp(+jwt)"})
    b, _ = _point([0.1, 0.0], extra={"time_convention": "exp(-j*omega*t)"})
    with pytest.raises(ValueError, match="different time conventions"):
        a.coherent_subtract(b)
    # One undeclared side is not a conflict.
    c, _ = _point([0.1, 0.0])
    a.coherent_subtract(c)


def test_agreeing_time_convention_is_kept():
    a, _ = _point([0.0, 0.0], extra={"time_convention": "exp(+jwt)"})
    b, _ = _point([0.1, 0.0], extra={"time_convention": "exp(+j omega t)"})
    grid, _ = T.build_assembly_grid(
        _root(_leaf("a", a, T._MODE_COH), _leaf("b", b, T._MODE_COH))
    )
    assert grid.extra["time_convention"] == "exp(+jwt)"
    assert a.coherent_subtract(b).extra["time_convention"] == "exp(+jwt)"


def test_phase_reference_and_basis_conflicts_are_reported():
    a, _ = _point([0.0, 0.0], extra={"phase_reference": "vehicle origin",
                                     "polarization_basis": "earth V/H"})
    b, _ = _point([0.1, 0.0], extra={"phase_reference": "feature centroid",
                                     "polarization_basis": "body V/H"})
    report = []
    grid, history = T.build_assembly_grid(
        _root(_leaf("a", a, T._MODE_COH), _leaf("b", b, T._MODE_COH)),
        report=report,
    )
    assert any("phase_reference" in line for line in report)
    assert any("polarization_basis" in line for line in report)
    assert "phase_reference" in history
    assert "phase_reference" in grid.extra["metadata_advisories_json"]


# 4. HV/VH reciprocal alias in Intersect --------------------------------------

def test_intersect_aliases_lone_hv_to_vh():
    a, da = _point([0.0, 0.0], pols=("VV", "HH", "VH"))
    b, db = _point([0.1, 0.0], pols=("VV", "HH", "HV"))
    report = []
    grid, history = T.build_assembly_grid(
        _root(_leaf("a", a, T._MODE_COH), _leaf("b", b, T._MODE_COH)),
        axis_mode="intersect", report=report,
    )
    assert [str(p) for p in grid.polarizations] == ["VV", "HH", "VH"]
    np.testing.assert_allclose(grid.rcs, da + db, atol=1e-12)
    assert "reciprocal cross-pol alias" in history
    assert any("'b' HV matched to VH" in line for line in report)


def test_intersect_keeps_exact_cross_pol_matching_when_ambiguous():
    a, _ = _point([0.0, 0.0], pols=("VV", "HH", "VH"))
    b, _ = _point([0.1, 0.0], pols=("VV", "HH", "HV", "VH"))
    grid, history = T.build_assembly_grid(
        _root(_leaf("a", a, T._MODE_COH), _leaf("b", b, T._MODE_COH)),
        axis_mode="intersect",
    )
    assert [str(p) for p in grid.polarizations] == ["VV", "HH", "VH"]
    assert "holds both HV and VH" in history


# 5. Intersect states how many samples each input kept ------------------------

def test_intersect_reports_samples_kept_per_input():
    a, _ = _point([0.0, 0.0], az=np.arange(0, 360, 5.0))
    b, _ = _point([0.1, 0.0], az=np.arange(0, 90, 1.0))
    report = []
    grid, history = T.build_assembly_grid(
        _root(_leaf("a", a, T._MODE_COH), _leaf("b", b, T._MODE_COH)),
        axis_mode="intersect", report=report,
    )
    assert len(grid.azimuths) == 18
    assert any("'a' 54 of 216 samples kept" in line
               and "'b' 54 of 270 samples kept" in line for line in report)
    assert "'a' 54 of 216" in history


def test_build_summary_dialog_lists_report():
    panel = T.AssemblyTreePanel()
    try:
        panel._build_title = "platform"
        panel._show_build_summary(["root: Intersect cropped: 'a' 1 of 2 samples kept"])
        assert "1 of 2 samples kept" in panel._last_build_summary
        panel._show_build_summary([])
    finally:
        for box in panel.findChildren(T.QMessageBox):
            box.close()
        panel.deleteLater()


# 7. Field + contributor with phase identically 0 ----------------------------

def test_all_zero_phase_coherent_contributor_is_reported():
    a, _ = _point([0.1, 0.0])
    z = RcsGrid(AZ, [0.0], [10.0], ["VV", "HH", "VH"], rcs_power=a.power,
                rcs_phase=np.zeros(a.power.shape), units=dict(a.units))
    report = []
    T.build_assembly_grid(
        _root(_leaf("a", a, T._MODE_COH), _leaf("z", z, T._MODE_COH)),
        report=report,
    )
    assert any("'z'" in line and "exactly 0" in line for line in report)
    assert not any("'a'" in line and "exactly 0" in line for line in report)
