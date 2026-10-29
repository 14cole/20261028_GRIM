"""Regression tests for the 2026-10-17 file reader/writer audit repairs."""
from __future__ import annotations

import os
import warnings

import numpy as np
import pytest

from GRIM_Backend.datasets.grid import RcsGrid
from GRIM_Backend.io.csv import TextEncodingError, has_flat_csv_signature
from GRIM_Backend.io.loaders import load_dataset


V1_HEADER = (
    "grim_csv_schema,azimuth,azimuth_unit,elevation,elevation_unit,frequency,"
    "frequency_unit,polarization,rcs_linear_quantity,rcs_log_unit,"
    "angular_coordinate_system,great_circle_coordinate_convention,"
    "angular_roll_deg,angular_tilt_deg,polarization_basis,time_convention,"
    "phase_reference,phase_wrap,magnitude_power_linear,phase_deg"
)
TXT_HEADER = (
    "theta(deg) phi(deg) abs(rcs)(dbm^2) abs(theta)(dbm^2) phase(theta)(deg) "
    "abs(phi)(dbm^2) phase(phi)(deg) ax.ratio(db)"
)
CST_FLAT_HEADER = (
    "Elevation(deg),Azimuth(deg),Frequency(GHz),Polarity,Magnitude(dBsm),Phase(deg)"
)
UNITS = {"azimuth": "deg", "elevation": "deg", "frequency": "GHz",
         "rcs_log_unit": "dBsm", "rcs_linear_quantity": "sigma_3d"}


def _v1_row(az, *, frequency=10, power=1.0, phase=30.0):
    return (f"grim.flat-rcs.v1,{az},deg,0,deg,{frequency},GHz,HH,sigma_3d,dBsm,"
            f"conic,,0,0,,,,-180_180,{power},{phase}")


def _write(path, text, encoding="utf-8"):
    path.write_bytes(text.encode(encoding))
    return str(path)


def _ptm_grid(amplitude=1.0, **unit_overrides):
    azimuths = np.arange(0.0, 20.0, 5.0)
    frequencies = np.linspace(8.0, 12.0, 37)
    rcs = np.full((azimuths.size, 1, frequencies.size, 1),
                  amplitude * np.exp(1j * np.deg2rad(30.0)), dtype=complex)
    return RcsGrid(azimuths, [0.0], frequencies, ["HH"], rcs=rcs,
                   units=dict(UNITS, **unit_overrides))


# --- PTM writer ----------------------------------------------------------------

def test_ptm_conjugates_declared_negative_time_convention_with_warning(tmp_path):
    grid = _ptm_grid(time_convention="exp(-jwt)")
    with pytest.warns(UserWarning, match="conjugated to exp\\(\\+jwt\\)"):
        path = grid.save_ptm(str(tmp_path / "minus.ptm"))
    loaded = load_dataset(path)
    np.testing.assert_allclose(np.angle(loaded.rcs[0, 0, 0, 0], deg=True), -30.0, atol=1e-4)


def test_ptm_keeps_positive_or_undeclared_time_convention(tmp_path):
    for name, overrides in (("plus", {"time_convention": "exp(+jwt)"}), ("none", {})):
        grid = _ptm_grid(**overrides)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            path = grid.save_ptm(str(tmp_path / f"{name}.ptm"))
        loaded = load_dataset(path)
        np.testing.assert_allclose(np.angle(loaded.rcs[0, 0, 0, 0], deg=True), 30.0, atol=1e-4)


def test_ptm_refuses_unrecognized_time_convention(tmp_path):
    grid = _ptm_grid(time_convention="engineering")
    with pytest.raises(ValueError, match="unrecognized time_convention"):
        grid.save_ptm(str(tmp_path / "bad.ptm"))


def test_ptm_refuses_float32_overflow_instead_of_writing_inf(tmp_path):
    grid = _ptm_grid(amplitude=1.0e40)
    target = tmp_path / "huge.ptm"
    with pytest.raises(ValueError, match="float32 maximum"):
        grid.save_ptm(str(target))
    assert not target.exists()
    assert not [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]


# --- CST theta/phi TXT ---------------------------------------------------------

def test_theta_phi_txt_uses_cst_wide_angle_mapping(tmp_path):
    wide = _write(tmp_path / "w.csv",
                  "Frequency(GHz),Theta(deg),Phi(deg),RCS Theta-Theta(dBsm),"
                  "Phase Theta-Theta(deg)\n10,80,30,0,45\n")
    txt = _write(tmp_path / "f=10GHz_w.txt", f"{TXT_HEADER}\n80 30 0.41 0 45 -10 90 0\n")
    wide_grid = load_dataset(wide)
    txt_grid = load_dataset(txt)
    np.testing.assert_allclose(txt_grid.azimuths, wide_grid.azimuths)
    np.testing.assert_allclose(txt_grid.elevations, wide_grid.elevations)
    np.testing.assert_allclose(txt_grid.azimuths, [30.0])
    np.testing.assert_allclose(txt_grid.elevations, [10.0])
    assert txt_grid.extra["cst_angle_mapping"] == wide_grid.extra["cst_angle_mapping"]


def test_theta_phi_txt_wraps_phi_and_rejects_out_of_range_theta(tmp_path):
    wrapped = _write(tmp_path / "f=1GHz_a.txt", f"{TXT_HEADER}\n90 270 0 0 0 0 0 0\n")
    np.testing.assert_allclose(load_dataset(wrapped).azimuths, [-90.0])
    bad = _write(tmp_path / "f=1GHz_b.txt", f"{TXT_HEADER}\n190 0 0 0 0 0 0 0\n")
    with pytest.raises(ValueError, match="line 2: standard CST theta"):
        RcsGrid.load_theta_phi_txt(bad)


def test_theta_phi_txt_labels_receive_components_without_declared_excitation(tmp_path):
    path = _write(tmp_path / "f=10GHz_p.txt",
                  f"{TXT_HEADER}\n90 0 0.41 0 45 -10 90 0\n")
    grid = RcsGrid.load_theta_phi_txt(path)
    assert list(map(str, grid.polarizations)) == ["THETA", "PHI", "TOTAL"]
    assert "not declared" in grid.extra["cst_polarization_mapping"]
    assert grid.power_slice().dtype == np.float64
    np.testing.assert_allclose(grid.power_slice()[0, 0, 0, :2], [1.0, 0.1], rtol=1e-15)

    vertical = RcsGrid.load_theta_phi_txt(path, incident_polarization="V")
    assert list(map(str, vertical.polarizations)) == ["VV", "HV", "TOTAL"]
    horizontal = RcsGrid.load_theta_phi_txt(path, incident_polarization="phi")
    assert list(map(str, horizontal.polarizations)) == ["VH", "HH", "TOTAL"]
    with pytest.raises(ValueError, match="incident_polarization"):
        RcsGrid.load_theta_phi_txt(path, incident_polarization="X")


# --- Truncated rows --------------------------------------------------------------

def test_flat_csv_rejects_truncated_rows_with_line_number(tmp_path):
    short = _write(tmp_path / "s.csv",
                   "\n".join([V1_HEADER, _v1_row(0), _v1_row(10)[: -len(",30.0")]]) + "\n")
    with pytest.raises(ValueError, match="line 3: 1 fewer value"):
        load_dataset(short)
    # A missing final newline is not a truncated row.
    no_newline = _write(tmp_path / "n.csv", "\n".join([V1_HEADER, _v1_row(0), _v1_row(10)]))
    assert load_dataset(no_newline).rcs.shape == (2, 1, 1, 1)


def test_cst_wide_rejects_truncated_rows_with_line_number(tmp_path):
    path = _write(tmp_path / "s.csv",
                  "Frequency(GHz),Theta(deg),Phi(deg),RCS Theta-Theta(dBsm),"
                  "RCS Phi-Phi(dBsm),Phase Theta-Theta(deg),Phase Phi-Phi(deg)\n"
                  "10,90,0,0,-3,45,90\n10,90,10,0,-3,45\n")
    with pytest.raises(ValueError, match="line 3: 6 value\\(s\\) but the header has 7"):
        RcsGrid.read_CST(path)
    complete = _write(tmp_path / "c.csv",
                      "Frequency(GHz),Theta(deg),Phi(deg),RCS Theta-Theta(dBsm),"
                      "Phase Theta-Theta(deg)\n10,90,0,0,45\n10,90,10,0,45")
    assert RcsGrid.read_CST(complete).rcs.shape == (2, 1, 1, 1)


def test_cst_flat_rejects_truncated_rows_with_line_number(tmp_path):
    path = _write(tmp_path / "s.cst_data", f"{CST_FLAT_HEADER}\n0,0,10,HH,0,45\n0,10,10,HH,0\n")
    with pytest.raises(ValueError, match="line 3: 5 value\\(s\\) but the header has 6"):
        load_dataset(path)
    # Trailing empty header cells and an empty trailing IQ cell are still fine.
    ok = _write(tmp_path / "ok.cst_data",
                f"{CST_FLAT_HEADER},IQ,\n0,0,10,HH,0,45,\n0,10,10,HH,0,45,")
    assert load_dataset(ok).rcs.shape == (2, 1, 1, 1)


# --- .cst_data unsupported physics headers --------------------------------------

@pytest.mark.parametrize("header", ["Phase(rad)", "Phase", "Magnitude(m^2)"])
def test_cst_flat_refuses_unrecognized_phase_or_magnitude_header(tmp_path, header):
    text = (f"Elevation(deg),Azimuth(deg),Frequency(GHz),Polarity,Magnitude(dBsm),{header}\n"
            "0,0,10,HH,0,1.0\n")
    path = _write(tmp_path / "p.cst_data", text)
    with pytest.raises(ValueError, match="unsupported CST flat-table column header"):
        load_dataset(path)


# --- Flat CSV frequency ------------------------------------------------------------

@pytest.mark.parametrize("frequency", [0, -10])
def test_flat_csv_requires_positive_frequency(tmp_path, frequency):
    path = _write(tmp_path / "f.csv", f"{V1_HEADER}\n{_v1_row(0, frequency=frequency)}\n")
    with pytest.raises(ValueError, match="line 2: frequency must be positive"):
        load_dataset(path)


def test_legacy_frequency_heuristic_emits_python_warning(tmp_path):
    path = _write(tmp_path / "legacy.csv",
                  "azimuth,elevation,frequency,polarization,magnitude_dbsm,phase_deg\n"
                  "0,0,450,HH,0,0\n10,0,900,HH,0,0\n")
    with pytest.warns(UserWarning, match="legacy.csv: legacy magnitude heuristic selected GHz"):
        grid = load_dataset(path)
    assert grid.extra["frequency_unit_inferred"] is True
    assert "WARNING: legacy magnitude heuristic" in grid.history


# --- Text encodings ----------------------------------------------------------------

@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
def test_utf16_with_bom_loads(tmp_path, encoding):
    bom = {"utf-16-le": "﻿", "utf-16-be": "﻿"}.get(encoding, "")
    csv_path = _write(tmp_path / "u.csv", bom + f"{V1_HEADER}\n{_v1_row(0)}\n", encoding)
    assert has_flat_csv_signature(csv_path)
    np.testing.assert_allclose(abs(load_dataset(csv_path).rcs[0, 0, 0, 0]) ** 2, 1.0)
    cst_path = _write(tmp_path / "u.cst_data", bom + f"{CST_FLAT_HEADER}\n0,0,10,HH,0,45\n",
                      encoding)
    assert load_dataset(cst_path).rcs.shape == (1, 1, 1, 1)
    out_path = _write(tmp_path / "u_VV.out", bom + "10 0 0 0\n", encoding)
    assert load_dataset(out_path).rcs.shape == (1, 1, 1, 1)
    txt_path = _write(tmp_path / "f=10GHz_u.txt", bom + f"{TXT_HEADER}\n90 0 0 0 0 0 0 0\n",
                      encoding)
    assert load_dataset(txt_path).rcs.shape == (1, 1, 1, 3)


@pytest.mark.parametrize("name, text", [
    ("cp.csv", f"{V1_HEADER}\n" + _v1_row(0).replace(",,,,-180", ",,,caf\xe9,-180") + "\n"),
    ("cp.txt", f"{V1_HEADER}\n" + _v1_row(0).replace(",,,,-180", ",,,caf\xe9,-180") + "\n"),
    ("cp.cst_data", CST_FLAT_HEADER.replace("Elevation(deg)", "Elevation(\xb0)")
     + "\n0,0,10,HH,0,0\n"),
    ("cp_VV.out", "# caf\xe9\n10 0 0 0\n"),
])
def test_non_utf8_text_raises_named_value_error(tmp_path, name, text):
    path = _write(tmp_path / name, text, "cp1252")
    with pytest.raises(TextEncodingError, match=f"{name}: file is not valid UTF-8.*save it as UTF-8"):
        load_dataset(path)


def test_signature_sniffers_return_false_for_undecodable_text(tmp_path):
    path = _write(tmp_path / "x.csv", "freq_MHz,theta_deg,caf\xe9\n1,2,3\n", "cp1252")
    assert RcsGrid.has_SENTRi_signature(path) is False
    assert has_flat_csv_signature(path) is False


# --- OUT filename polarization ---------------------------------------------------

@pytest.mark.parametrize("token", ["HH", "VV", "HV", "VH"])
def test_out_filename_polarization_tokens(tmp_path, token):
    path = _write(tmp_path / f"target_{token}.out", "10 0 0 0\n")
    assert list(map(str, load_dataset(path).polarizations)) == [token]


def test_out_filename_with_several_channels_is_not_guessed(tmp_path):
    path = _write(tmp_path / "target_HV_VH.out", "10 0 0 0\n")
    with pytest.raises(ValueError, match="ambiguously declares HV and VH"):
        load_dataset(path)
    declared = _write(tmp_path / "both_HV_VH.out", "# polarization: HV\n10 0 0 0\n")
    assert list(map(str, load_dataset(declared).polarizations)) == ["HV"]
