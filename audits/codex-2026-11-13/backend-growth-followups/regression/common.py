"""Shared helpers for the audit regression scripts.

Run any script from anywhere:  python audits/claude-2026-11-10/regression/<script>.py
Each script prints one line per check and exits non-zero on the first failure
count; `run_all.py` runs them all.  Build the Linux native kernels first
(twod/assembly/native/build.py, bor/native/build_kernel.py) for speed.
"""
import math
import os
import sys

# GHOST_AUDIT_ROOT points the scripts at another checkout (for example the unmodified solver).
ROOT = os.environ.get("GHOST_AUDIT_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "GHOST"))

import numpy as np  # noqa: E402
from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot  # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (" | " + str(detail) if detail != "" else ""), flush=True)
    if not ok:
        FAILURES.append(name)


def finish():
    print("{} failure(s)".format(len(FAILURES)))
    sys.exit(1 if FAILURES else 0)


def raises(fn, exc, text=None):
    try:
        fn()
    except exc as error:
        return text is None or text in str(error), str(error)[:160]
    except Exception as error:  # wrong type
        return False, type(error).__name__ + ": " + str(error)[:160]
    return False, "no exception"


def snap(text):
    return build_geometry_snapshot(*parse_geometry(text))


def scene(segments, ibc="", diel=""):
    """segments: [(name, type, 'properties', rows_text)]"""
    text = "Title: t\n"
    for name, kind, props, rows in segments:
        text += "Segment: {} {}\nproperties: {}\n{}\n".format(name, kind, props, rows)
    return snap(text + "IBCS_Resistances:\n{}\nDielectrics:\n{}\n".format(ibc, diel))


def rows(points):
    return "\n".join("{:.15g} {:.15g} {:.15g} {:.15g}".format(*points[i], *points[i + 1])
                     for i in range(len(points) - 1))


def rect(x0, y0, x1, y1):
    """Clockwise rectangle (left-hand normal into the exterior)."""
    return rows([(x0, y0), (x0, y1), (x1, y1), (x1, y0), (x0, y0)])


def arc(radius, start, stop, count, x0=0.0, y0=0.0):
    theta = np.linspace(start, stop, count + 1)
    return rows([(x0 + radius * math.cos(t), y0 + radius * math.sin(t)) for t in theta])


def circle(radius, count, x0=0.0, y0=0.0, area_preserving=True):
    """Clockwise polygon circle."""
    r = radius * math.sqrt((2 * math.pi / count) / math.sin(2 * math.pi / count)) if area_preserving else radius
    theta = -np.linspace(0, 2 * np.pi, count + 1)
    pts = [(x0 + r * math.cos(t), y0 + r * math.sin(t)) for t in theta]
    pts[-1] = pts[0]
    return rows(pts)


def bor_sphere(radius, count):
    theta = np.linspace(0, np.pi, count + 1)
    pts = [(radius * math.sin(t), radius * math.cos(t)) for t in theta]
    pts[0] = (0.0, radius)
    pts[-1] = (0.0, -radius)
    return rows(pts)


def db(samples, pol):
    return np.array([s["rcs_db"] for s in samples if pol is None or s.get("polarization") == pol])


def amp(samples, pol):
    return np.array([complex(s["rcs_amp_real"], s["rcs_amp_imag"]) for s in samples if pol is None or s.get("polarization") == pol])
