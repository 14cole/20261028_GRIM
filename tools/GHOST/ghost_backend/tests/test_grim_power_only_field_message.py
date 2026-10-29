"""A power-only GRIM file must be rejected as phase-unknown, not as corrupt."""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from GRIM_Backend.datasets.grid import RcsGrid  # noqa: E402
from ghost_backend.assembly import fields  # noqa: E402


def _save(path, **samples):
    shape = (4, 1, 2, 3)
    RcsGrid(np.arange(4.0), [0.0], [8.0, 10.0], ["VV", "HH", "VH"],
            units={"frequency": "GHz", "rcs_linear_quantity": "sigma_3d"},
            **samples).save(path)
    return shape


def test_power_only_grim_reports_unknown_phase():
    with tempfile.TemporaryDirectory() as folder:
        _check_power_only(Path(folder) / "power_only.grim")


def _check_power_only(path):
    _save(path, rcs_power=np.ones((4, 1, 2, 3)))
    with pytest.raises(ValueError) as caught:
        fields._load_grim(path)
    message = str(caught.value)
    assert "phase is unknown" in message and "power-only" in message
    assert "coherent complex field" in message
    assert "NaN or infinity" not in message


def test_complex_grim_still_loads():
    with tempfile.TemporaryDirectory() as folder:
        _check_complex(Path(folder) / "field.grim")


def _check_complex(path):
    field = np.exp(1j * np.linspace(0, 3, 24)).reshape(4, 1, 2, 3)
    _save(path, rcs=field)
    out = fields._load_grim(path)
    assert np.isfinite(out["_amp"]).all()
