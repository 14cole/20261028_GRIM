"""Shared fixture helpers for the independent Line Expansion checks.

Run with GRIM_ROOT pointing at a checkout of ed90b65 (default: four levels up).
Everything uses the real certified 2-D section solver; nothing is patched.
"""
import os, sys, time
from pathlib import Path
import numpy as np

GRIM_ROOT = Path(os.environ.get("GRIM_ROOT", Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(GRIM_ROOT / "tools" / "GHOST"))

from ghost_backend.assembly import expand_wing_sections as wing  # noqa: E402
from ghost_backend.data_tools.cem_tools.native_samples import (  # noqa: E402
    decode_native_samples, raw_amplitude)
from ghost_backend.io.grim import _save_grim_npz  # noqa: E402

# Closed, asymmetric PEC quadrilateral (meters). Asymmetric on purpose so the
# response depends on every attitude angle and has no accidental symmetry.
SECTION_GEO = """Title: asymmetric closed PEC wedge
Segment: skin
properties: 2 -24 0 0 0
-0.060 0.000 0.040 0.025
0.040 0.025 0.060 0.000
0.060 0.000 0.020 -0.012
0.020 -0.012 -0.060 0.000
IBCS_Resistances:
Dielectrics:
"""
# Tilted and twisted against every axis so the radar-frame field has real
# cross-polarisation.
SECTION = dict(root=(0.02, -0.05, 0.01), tip=(0.31, 0.09, 0.12), normal=(-0.2, 0.1, 1.0))
SETTINGS = dict(coordinate_units="meters", geometry_units="meters",
                section_angle_step_deg=2.0, shadow=False)


def write_section(folder):
    path = Path(folder) / "wedge.geo"
    path.write_text(SECTION_GEO)
    span = np.subtract(SECTION["tip"], SECTION["root"])
    normal = np.asarray(SECTION["normal"], float)
    normal = normal - span * (normal @ span) / (span @ span)   # make it perpendicular
    return dict(SECTION, geometry=str(path), normal=tuple(normal / np.linalg.norm(normal)))


def reopen(path):
    """Read a written .grim back from disk: (payload dict, complex field)."""
    with np.load(path, allow_pickle=False) as stored:
        payload = decode_native_samples({k: stored[k] for k in stored.files})
    return payload, np.asarray(raw_amplitude(payload))


def scalar(payload, key):
    return str(np.asarray(payload[key]).reshape(()).item()) if key in payload else None


def rel(a, b):
    """max|a-b| / max|b| (b is the expected field)."""
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))) / np.max(np.abs(b)))


def expand(sections, **kw):
    t = time.time()
    out = wing.expand_wing_sections(sections, **{**SETTINGS, **kw})
    out["seconds"] = round(time.time() - t, 2)
    return out
