"""Solve/export pipelines shared by local and HPC scheduling adapters.

Adapters own paths, source/input verification and snapshot loading. The shared
pipeline preserves verification before reuse and again before publication.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import ghost_backend.hpc.scheduler as hpc_scheduler
from ghost_backend.execution.provenance import embed_output_attestation, verify_embedded_attestation


@dataclass(frozen=True)
class WorkerAdapter:
    output_path: Callable
    verify_run: Callable
    verify_input: Callable
    attestation: Callable
    load_snapshot: Callable
    history_script: str
    record_memory: Optional[Callable] = None
    verify_channels: Optional[Callable] = None

    def check_inputs(self, units, context):
        if self.verify_channels is not None:
            self.verify_channels(units, context)
        else:
            for unit in units:
                self.verify_input(unit, context)


def run_twod_unit(unit, context, destination, adapter):
    """Solve or reuse one paired-polarization 2D output."""
    results_dir = Path(destination)
    out_path = adapter.output_path(results_dir, unit)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.verify_run(context)
    adapter.check_inputs([unit], context)
    attestation = adapter.attestation(context, unit)
    if out_path.exists():
        verify_embedded_attestation(str(out_path), attestation)
        return ("skipped", str(out_path))

    snapshot, material_base = adapter.load_snapshot(str(unit["geometry"]))

    solve_kwargs = dict(
        geometry_snapshot=snapshot,
        frequencies_ghz=[float(unit["frequency_ghz"])],
        elevations_deg=[float(a) for a in context["azimuths_deg"]],
        geometry_units=context["geometry_units"],
        material_base_dir=material_base,
        max_panels=context["max_panels"],
        solver_method=context.get("solver_method", "direct"),
    )
    # Select precision inside each worker; context variables are process-local.
    from ghost_backend.linalg.refined_lu import linear_precision
    from ghost_backend.twod.samples import compact_samples
    peak_reset = hpc_scheduler.reset_peak_rss()
    with compact_samples(), linear_precision(context.get("lu_precision", "double")):
        if context["mesh_certification"]:
            from ghost_backend.twod.solver import solve_monostatic_rcs_2d_certified
            result = solve_monostatic_rcs_2d_certified(
                mesh_convergence_policy=context["mesh_convergence_policy"],
                **solve_kwargs
            )
        else:
            from ghost_backend.twod.solver import solve_monostatic_rcs_2d_survey
            result = solve_monostatic_rcs_2d_survey(**solve_kwargs)
    adapter.verify_run(context)
    adapter.check_inputs([unit], context)
    adapter.record_memory(result, context, unit, peak_reset)

    # Bind the result to its run state inside the artifact, before export, so
    # results/ holds one file per unit instead of a .grim and a sidecar.
    embed_output_attestation(result, attestation)

    from ghost_backend.io.grim import export_result_to_grim
    written = export_result_to_grim(
        result, str(out_path),
        source_path=str(snapshot.get("source_path", "") or ""),
        history=(f"{adapter.history_script} pols=VV,HH "
                 f"freq={unit['frequency_ghz']}GHz"),
    )
    actual_path = str(written[0]) if written else str(out_path)
    # The run state was verified before the solve and again before the
    # export; a third check after the artifact is published could only
    # report a change it can no longer prevent (October 2026 audit, R-D-1).
    return ("written", actual_path)


def record_memory_evidence(result, context, unit, peak_reset, unit_name):
    """Measured peak resident size of this worker against the planner's
    forecast, in the artifact metadata and the run log."""
    measured = hpc_scheduler.peak_rss_gib()
    forecast = context.get("forecast_peak_gib")
    evidence = {
        "forecast_peak_gib": (float(forecast) if forecast is not None else None),
        "measured_peak_gib": measured,
        "scope": ("worker_process_since_unit_start" if peak_reset
                  else "worker_process_lifetime"),
        "note": "Compressed tile processes are children of the worker and are not "
                "included; the forecast covers the whole unit.",
    }
    metadata = result.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["execution_memory"] = evidence
    if measured is not None:
        ratio = ("" if not forecast else f", {measured / float(forecast):.2f} of forecast")
        print(f"      memory {unit_name(unit)}: forecast "
              f"{(float(forecast) if forecast else 0.0):.2f} GiB, measured peak "
              f"{measured:.2f} GiB ({evidence['scope']}{ratio})", flush=True)


def channel_result(
    result: 'Dict[str, Any]', polarization: 'str'
) -> 'Dict[str, Any]':
    samples = (result.get("co_solved_samples", {}) or {}).get(polarization, [])
    if not samples:
        raise RuntimeError(
            f"BoR solve did not return its co-solved {polarization} channel."
        )
    channel = dict(result)
    channel["samples"] = samples
    channel["polarization"] = polarization
    channel["polarization_export"] = polarization
    channel.pop("polarizations", None)
    channel.pop("polarization_mapping", None)
    channel.pop("co_solved_samples", None)
    channel["metadata"] = dict(result.get("metadata", {}) or {})
    return channel


def run_bor_pair(pair, context, destination, adapter, solve):
    """Co-solve a BoR pair and publish only its missing channel artifacts."""
    results_dir = Path(destination)
    channel_units = list(pair["channel_units"])
    adapter.verify_run(context)
    adapter.check_inputs(channel_units, context)
    missing = []
    paths = []
    for unit in channel_units:
        out_path = adapter.output_path(results_dir, unit)
        paths.append(out_path)
        if out_path.exists():
            verify_embedded_attestation(
                str(out_path), adapter.attestation(context, unit)
            )
        else:
            missing.append(unit)
    if not missing:
        return ("skipped", ", ".join(str(path) for path in paths))

    snapshot, material_base = adapter.load_snapshot(str(pair["geometry"]))

    result = solve(snapshot, material_base)
    for warning in result.get("metadata", {}).get("warnings", []) or []:
        print(f"      [warn] {pair['geometry_stem']}: {warning}", flush=True)
    adapter.verify_run(context)
    adapter.check_inputs(channel_units, context)

    from ghost_backend.io.grim import export_result_to_grim
    actual_paths = []
    for unit in missing:
        out_path = adapter.output_path(results_dir, unit)
        channel = channel_result(result, str(unit["polarization"]))
        embed_output_attestation(
            channel, adapter.attestation(context, unit)
        )
        written = export_result_to_grim(
            channel, str(out_path),
            source_path=str(snapshot.get("source_path", "") or ""),
            history=(f"{adapter.history_script} pol={unit['polarization']} "
                     f"freq={unit['frequency_ghz']}GHz"),
        )
        actual_paths.append(str(written[0]) if written else str(out_path))
    # The run state was verified before the solve and again before the
    # export; a third check after the artifact is published could only
    # report a change it can no longer prevent (October 2026 audit, R-D-1).
    return ("written", ", ".join(actual_paths))


def solve_bor_result(solve_kwargs, certified, mesh_policy):
    """Choose the existing BoR solve entry and compact result representation."""
    from ghost_backend.bor.dispatch import (
        solve_monostatic_rcs_bor_certified, solve_monostatic_rcs_bor_survey,
    )
    from ghost_backend.runs.quality import validate_mesh_convergence_policy
    from ghost_backend.twod.samples import compact_samples
    solve = solve_monostatic_rcs_bor_certified if certified else solve_monostatic_rcs_bor_survey
    quality = ({"mesh_convergence_policy": validate_mesh_convergence_policy(mesh_policy)}
               if certified else {})
    return compact_samples()(solve)(**solve_kwargs, **quality)
