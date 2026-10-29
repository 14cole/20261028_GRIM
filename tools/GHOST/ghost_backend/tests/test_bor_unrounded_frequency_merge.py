"""A BoR frequency not exact to 3 decimals in GHz still produces the combined file.

Unit filenames carry the frequency rounded to 3 decimals; the merge used that
rounded value against the exact attested frequency and refused to combine.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

GHOST = Path(__file__).resolve().parents[2]
REPO = GHOST.parent.parent


def _sphere_geo(path: Path, arcs: int = 16, radius: float = 0.1) -> None:
    angles = np.linspace(0.0, np.pi, arcs + 1)
    points = [(radius * np.sin(t), radius * np.cos(t)) for t in angles]
    lines = ["Title: PEC sphere", "Segment: sphere", "properties: 2 0 0 0 0"]
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        lines.append(f"{x0:.15f} {y0:.15f} {x1:.15f} {y1:.15f}")
    lines += ["IBCS_Resistances:", "Dielectrics:"]
    path.write_text("\n".join(lines) + "\n")


def test_unrounded_frequency_writes_combined_result(tmp_path):
    geometry = tmp_path / "geo"
    geometry.mkdir()
    _sphere_geo(geometry / "sphere.geo")
    output = tmp_path / "out"
    config = tmp_path / "run.config.json"
    config.write_text(json.dumps({
        "schema": "ghost.driver-config", "version": 1, "driver": "bor",
        "settings": {
            "GEOMETRY_DIRS": [str(geometry)], "FREQUENCIES_GHZ": [1.0004],
            "AZIMUTHS_DEG": [0.0], "ELEVATIONS_DEG": [0.0], "OUTPUT_DIR": str(output),
            "GEOMETRY_UNITS": "meters", "MESH_CERTIFICATION": False, "WORKERS": 1,
        },
    }))
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(REPO), str(GHOST)]))
    completed = subprocess.run(
        [sys.executable, str(GHOST / "ghost_backend" / "run_local_bor.py"), "--config", str(config)],
        cwd=str(GHOST), env=env, capture_output=True, text=True, timeout=600,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    combined = list(output.glob("run_*/results/sphere.grim"))
    assert len(combined) == 1, completed.stdout
    with np.load(combined[0]) as data:
        np.testing.assert_array_equal(data["frequencies"], [1.0004])
