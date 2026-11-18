"""Shared driver input checks, geometry loading, and durable submission journals."""
from ghost_backend.execution.provenance import (
    describe_source_mismatch, verify_runtime_environment, unit_solve_spec_fingerprint,
)

import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple


def publish_submission_journal(path, document):
    # type: (Path, Dict[str, Any]) -> None
    """Atomically publish a submission journal after its bytes reach disk."""

    temporary_path = path.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(document, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary_path), str(path))


    if os.name == "posix":
        try:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            parent_fd = os.open(str(path.parent), flags)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        except OSError:
            pass


def verify_local_unit_input(
    unit: 'Dict[str, Any]',
    context: 'Dict[str, Any]',
) -> 'None':
    from ghost_backend.assembly.fields import geometry_input_fingerprint
    current = geometry_input_fingerprint(
        str(unit["geometry"]), str(context["geometry_units"])
    )
    if current != unit.get("geometry_input_sha256"):
        raise RuntimeError(
            f"Geometry/material input changed during the local run: "
            f"{unit['geometry']}"
        )


def load_geometry_snapshot(geometry_path: 'str', cache: 'Dict[str, Any]') -> 'Tuple[Dict[str, Any], str]':
    """Parsed snapshot for one geometry, built at most once per process.

    ``cache`` belongs to the caller (one per driver module).  The drivers'
    pools use the spawn start method, so every worker parses its own copy of a
    geometry on its first unit; nothing is inherited from the parent.
    """

    cached = cache.get(geometry_path)
    if cached is not None:
        return cached
    from ghost_backend.geometry.io import parse_geometry, build_geometry_snapshot

    path = Path(geometry_path)
    title, segments, ibcs, dielectrics = parse_geometry(path.read_text())
    snapshot = build_geometry_snapshot(title, segments, ibcs, dielectrics)
    snapshot["source_path"] = str(path)
    entry = (snapshot, str(path.parent))
    cache[geometry_path] = entry
    return entry


def verify_local_run_provenance(context, source_fingerprint, source_inventory):
    """Re-check that the solver source and numerical runtime still match the run.

    Called around every unit. The file hashes underneath come from
    `hpc_scheduler.install_fingerprint_cache`, so a repeat check is a stat per
    backend file rather than a full re-read, and the cache expires on a timer
    so full re-reads keep happening inside long-lived workers.
    """

    if source_fingerprint() != context.get("solver_source_sha256"):
        detail = describe_source_mismatch(
            context.get("solver_source_inventory") or {},
            source_inventory(),
        )
        raise RuntimeError(
            "Local-run solver source/native artifacts changed; no mixed-state "
            f"field will be written or reused. ({detail})"
        )
    verify_runtime_environment(
        str(context.get("runtime_environment_sha256", "")),
        context.get("submission_runtime_environment"), origin="the local run manifest",
    )


def unit_attestation_fields(context, unit, angular_grid_kind, polarizations=None):
    """Bind a normalized local/2D context to one published unit."""
    fields = {
        "run_id": str(context["run_id"]),
        "solver_source_sha256": str(context["solver_source_sha256"]),
        "runtime_environment_sha256":
            str(context["runtime_environment_sha256"]),
        "geometry_input_sha256": str(unit["geometry_input_sha256"]),
        "run_solve_spec_sha256": str(context["run_solve_spec_sha256"]),
        "unit_solve_spec_sha256": unit_solve_spec_fingerprint(unit),
        "solver_config_sha256": str(context["solver_config_sha256"]),
        "angular_grid_kind": angular_grid_kind,
        # The grid is a run-level property, so it is bound by hash here and
        # stored once in the manifest instead of being repeated in every unit
        # record and every attestation.
        "angular_grid_sha256": str(context["angular_grid_sha256"]),
        "frequency_ghz": float(unit["frequency_ghz"]),
    }
    if polarizations is None:
        fields["polarization"] = str(unit["polarization"])
    else:
        fields["polarizations"] = list(polarizations)
    return fields
