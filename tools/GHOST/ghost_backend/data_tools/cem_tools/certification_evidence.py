"""Optional inspection of legacy mesh-certification evidence.

Normal joins and subtraction do not load this module. These checks inspect
stored provenance; they do not authorize a numerical dataset operation.
"""
import json
import math
from typing import Any
import numpy as np
from .errors import CemToolError
from .grim_native import (
    MESH_CERTIFICATION_KEY, MESH_CERTIFICATION_SCHEMA, DUAL_OUTPUT_POLARIZATIONS,
    EMBEDDED_ATTESTATION_SCHEMA, _ATTESTATION_SHA256_FIELDS, _POLARIZATION_2D,
    _scalar_text,
)


def _canonical_output_polarization(value: 'Any') -> 'str':
    key = str(value).strip().upper()
    internal = _POLARIZATION_2D.get(key)
    if internal == "TE":
        return "VV"
    if internal == "TM":
        return "HH"
    raise CemToolError(f"unsupported 2-D polarization in certification: {value!r}")


def _require_passed_quality_gate(gate: 'Any', label: 'str') -> 'dict[str, Any]':
    if not isinstance(gate, dict) or gate.get("passed") is not True:
        raise CemToolError(f"{label}: solver quality gate did not pass")
    return gate


def _require_passed_mesh_gate(gate: 'Any', label: 'str') -> 'dict[str, Any]':
    if (
        not isinstance(gate, dict)
        or gate.get("passed") is not True
        or gate.get("published_mesh") != "fine"
    ):
        raise CemToolError(
            f"{label}: mesh-convergence gate did not publish a passing fine mesh"
        )
    _require_passed_quality_gate(
        gate.get("base_quality_gate"), f"{label} base mesh"
    )
    _require_passed_quality_gate(
        gate.get("fine_quality_gate"), f"{label} fine mesh"
    )
    return gate


def _attestation_frequency(attestation: 'dict[str, Any]', label: 'str') -> 'float':
    try:
        value = float(attestation["frequency_ghz"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise CemToolError(
            f"{label}: embedded output attestation has no finite frequency_ghz"
        ) from exc
    if not math.isfinite(value) or value <= 0.0:
        raise CemToolError(
            f"{label}: embedded output attestation has no finite frequency_ghz"
        )
    return value


def _require_embedded_attestation(
    attestation: 'Any',
    label: 'str',
    *,
    frequency_ghz: 'float',
    polarizations: 'tuple[str, ...]',
) -> 'dict[str, Any]':
    """Validate the exact local/HPC embedded output-attestation contract."""

    if (
        not isinstance(attestation, dict)
        or attestation.get("schema") != EMBEDDED_ATTESTATION_SCHEMA
    ):
        raise CemToolError(
            f"{label}: missing current embedded output attestation"
        )
    if not str(attestation.get("run_id", "")).strip():
        raise CemToolError(f"{label}: embedded output attestation has no run_id")
    for field in _ATTESTATION_SHA256_FIELDS:
        digest = str(attestation.get(field, "")).strip()
        if len(digest) != 64 or any(
            character not in "0123456789abcdefABCDEF" for character in digest
        ):
            raise CemToolError(
                f"{label}: embedded output attestation has invalid {field}"
            )
    if attestation.get("angular_grid_kind") != "azimuths_deg":
        raise CemToolError(
            f"{label}: embedded output attestation has the wrong angular grid kind"
        )
    recorded_frequency = _attestation_frequency(attestation, label)
    if not math.isclose(
        recorded_frequency, float(frequency_ghz), rel_tol=0.0, abs_tol=1.0e-12
    ):
        raise CemToolError(
            f"{label}: embedded output attestation frequency does not match "
            "the GRIM frequency axis"
        )

    if polarizations == DUAL_OUTPUT_POLARIZATIONS:
        recorded = attestation.get("polarizations")
        if not isinstance(recorded, list) or tuple(recorded) != polarizations:
            raise CemToolError(
                f"{label}: embedded output attestation must declare exactly "
                "polarizations=['VV','HH']"
            )
        if "polarization" in attestation:
            raise CemToolError(
                f"{label}: dual-channel output attestation must not select one "
                "polarization"
            )
    elif len(polarizations) == 1:
        if "polarizations" in attestation:
            raise CemToolError(
                f"{label}: legacy single-channel output attestation must not "
                "declare a channel collection"
            )
        try:
            recorded = _canonical_output_polarization(
                attestation.get("polarization")
            )
        except CemToolError as exc:
            raise CemToolError(
                f"{label}: embedded output attestation has no valid polarization"
            ) from exc
        if recorded != polarizations[0]:
            raise CemToolError(
                f"{label}: embedded output attestation polarization does not "
                "match the GRIM channel"
            )
    else:
        raise CemToolError(f"{label}: unsupported attested polarization contract")
    return attestation


def _require_channel_dictionary(
    value: 'Any', label: 'str'
) -> 'dict[str, Any]':
    if not isinstance(value, dict) or set(value) != set(DUAL_OUTPUT_POLARIZATIONS):
        raise CemToolError(
            f"{label}: certification must contain exactly VV and HH channels"
        )
    return value


def _validate_dual_channel_evidence(
    *,
    mesh: 'Any',
    quality: 'Any',
    channels: 'Any',
    label: 'str',
) -> 'None':
    """Require independent mesh and algebraic evidence for VV and HH."""

    aggregate_mesh = _require_passed_mesh_gate(mesh, f"{label} aggregate")
    aggregate_quality = _require_passed_quality_gate(
        quality, f"{label} aggregate"
    )
    channel_meshes = _require_channel_dictionary(
        aggregate_mesh.get("channels"), f"{label} aggregate mesh"
    )
    quality_channels = _require_channel_dictionary(
        aggregate_quality.get("channels"), f"{label} aggregate quality"
    )
    channel_records = _require_channel_dictionary(channels, label)

    for phase in ("base_quality_gate", "fine_quality_gate"):
        phase_gate = _require_passed_quality_gate(
            aggregate_mesh.get(phase), f"{label} aggregate {phase}"
        )
        phase_channels = _require_channel_dictionary(
            phase_gate.get("channels"), f"{label} aggregate {phase}"
        )
        for polarization in DUAL_OUTPUT_POLARIZATIONS:
            _require_passed_quality_gate(
                phase_channels[polarization],
                f"{label} {polarization} aggregate {phase}",
            )

    for polarization in DUAL_OUTPUT_POLARIZATIONS:
        channel_label = f"{label} {polarization}"
        _require_passed_quality_gate(
            quality_channels[polarization], channel_label
        )
        _require_passed_mesh_gate(
            channel_meshes[polarization], channel_label
        )
        record = channel_records[polarization]
        if not isinstance(record, dict):
            raise CemToolError(f"{channel_label}: malformed channel metadata")
        _require_passed_quality_gate(record.get("quality_gate"), channel_label)
        _require_passed_mesh_gate(
            record.get("mesh_convergence"), channel_label
        )


def _validate_propagated_source(source: 'Any', label: 'str') -> 'None':
    if not isinstance(source, dict):
        raise CemToolError(f"{label}: malformed source-chain record")
    contract = source.get("contract")
    if contract == "embedded-dual-output-attestation.v1":
        polarizations = tuple(source.get("polarizations", ()))
        if polarizations != DUAL_OUTPUT_POLARIZATIONS:
            raise CemToolError(
                f"{label}: dual source-chain record does not contain VV and HH"
            )
        try:
            frequency_value = float(source.get("frequency_ghz"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise CemToolError(
                f"{label}: dual source-chain record has invalid frequency"
            ) from exc
        _require_embedded_attestation(
            source.get("output_attestation"),
            label,
            frequency_ghz=frequency_value,
            polarizations=DUAL_OUTPUT_POLARIZATIONS,
        )
        _validate_dual_channel_evidence(
            mesh=source.get("mesh_convergence"),
            quality=source.get("quality_gate"),
            channels=source.get("channels"),
            label=label,
        )
        return
    if contract == "embedded-single-output-attestation.v1":
        polarization = _canonical_output_polarization(
            source.get("polarization")
        )
        try:
            frequency_value = float(source.get("frequency_ghz"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise CemToolError(
                f"{label}: single-channel source-chain record has invalid frequency"
            ) from exc
        _require_embedded_attestation(
            source.get("output_attestation"),
            label,
            frequency_ghz=frequency_value,
            polarizations=(polarization,),
        )
        _require_passed_mesh_gate(source.get("mesh_convergence"), label)
        _require_passed_quality_gate(source.get("quality_gate"), label)
        return

    # Records emitted by the original workflow-unit contract did not carry a
    # contract discriminator or a top-level quality gate. Its base/fine gates
    # are nevertheless preserved and still validated here.
    if contract not in (None, "legacy-workflow-unit.v1"):
        raise CemToolError(f"{label}: unsupported source-chain contract")
    _require_passed_mesh_gate(source.get("mesh_convergence"), label)


def mesh_certification_sources(
    payload: 'dict[str, np.ndarray]',
    label: 'str',
) -> 'list[dict[str, Any]] | None':
    """Explicitly audit optional source evidence, including legacy CEM chains.

    Normal joins and subtraction deliberately do not call this helper; mesh
    certification is advisory and never authorizes a numerical operation.
    """

    if MESH_CERTIFICATION_KEY in payload:
        try:
            decoded = json.loads(
                _scalar_text(payload[MESH_CERTIFICATION_KEY])
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CemToolError(
                f"{label}: malformed production mesh certification"
            ) from exc
        sources = decoded.get("sources") if isinstance(decoded, dict) else None
        if (
            not isinstance(decoded, dict)
            or decoded.get("schema") != MESH_CERTIFICATION_SCHEMA
            or decoded.get("passed") is not True
            or decoded.get("published_mesh") != "fine"
            or not isinstance(sources, list)
            or not sources
            or (
                "source_count" in decoded
                and decoded.get("source_count") != len(sources)
            )
        ):
            raise CemToolError(
                f"{label}: unsupported production mesh certification"
            )
        if decoded.get("certifies_coherent_delta_convergence") is True:
            raise CemToolError(
                f"{label}: invalid source-chain certificate claims coherent "
                "delta convergence"
            )
        for index, source in enumerate(sources):
            _validate_propagated_source(
                source, f"{label} source-chain item {index + 1}"
            )
        return sources

    if "solver_metadata_json" not in payload:
        return None
    try:
        audit = json.loads(_scalar_text(payload["solver_metadata_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CemToolError(
            f"{label}: malformed solver metadata"
        ) from exc
    metadata = audit.get("metadata") if isinstance(audit, dict) else None
    mesh = (
        metadata.get("mesh_convergence")
        if isinstance(metadata, dict)
        else None
    )
    if mesh is None:
        return None
    output_attestation = metadata.get("output_attestation")
    payload_polarizations = tuple(
        str(value).strip().upper()
        for value in np.asarray(payload["polarizations"]).ravel()
    )
    frequencies = np.asarray(payload["frequencies"], dtype=float).ravel()

    if output_attestation is not None and "polarizations" in output_attestation:
        if payload_polarizations != DUAL_OUTPUT_POLARIZATIONS:
            raise CemToolError(
                f"{label}: an attested dual-channel artifact must store exactly "
                "polarizations ['VV', 'HH'] in that order"
            )
        if frequencies.size != 1:
            raise CemToolError(
                f"{label}: an attested solver unit must contain one frequency"
            )
        if tuple(audit.get("polarizations", ())) != DUAL_OUTPUT_POLARIZATIONS:
            raise CemToolError(
                f"{label}: solver audit does not declare exactly VV and HH"
            )
        if tuple(metadata.get("polarizations", ())) != DUAL_OUTPUT_POLARIZATIONS:
            raise CemToolError(
                f"{label}: solver metadata does not declare exactly VV and HH"
            )
        if metadata.get("polarization_mapping") != {"VV": "TE", "HH": "TM"}:
            raise CemToolError(
                f"{label}: solver metadata has the wrong VV/HH scalar mapping"
            )
        _require_embedded_attestation(
            output_attestation,
            label,
            frequency_ghz=float(frequencies[0]),
            polarizations=DUAL_OUTPUT_POLARIZATIONS,
        )
        if (
            metadata.get("mesh_convergence_certified") is not True
            or metadata.get("certified_entry_point") is not True
            or metadata.get("published_mesh") != "fine"
        ):
            raise CemToolError(
                f"{label}: dual-channel solver result was not published by the "
                "certified fine-mesh entry point"
            )
        quality = metadata.get("quality_gate")
        channel_metadata = _require_channel_dictionary(
            metadata.get("channel_metadata"), label
        )
        _validate_dual_channel_evidence(
            mesh=mesh,
            quality=quality,
            channels=channel_metadata,
            label=label,
        )
        for polarization in DUAL_OUTPUT_POLARIZATIONS:
            channel = channel_metadata[polarization]
            if (
                channel.get("mesh_convergence_certified") is not True
                or channel.get("certified_entry_point") is not True
                or channel.get("published_mesh") != "fine"
            ):
                raise CemToolError(
                    f"{label} {polarization}: channel was not published by the "
                    "certified fine-mesh entry point"
                )
        return [{
            "contract": "embedded-dual-output-attestation.v1",
            "label": str(label),
            "frequency_ghz": float(frequencies[0]),
            "polarizations": list(DUAL_OUTPUT_POLARIZATIONS),
            "output_attestation": output_attestation,
            "mesh_convergence": mesh,
            "quality_gate": quality,
            "channels": {
                polarization: {
                    "mesh_convergence": channel_metadata[polarization][
                        "mesh_convergence"
                    ],
                    "quality_gate": channel_metadata[polarization][
                        "quality_gate"
                    ],
                }
                for polarization in DUAL_OUTPUT_POLARIZATIONS
            },
        }]

    if output_attestation is not None:
        if len(payload_polarizations) != 1 or frequencies.size != 1:
            raise CemToolError(
                f"{label}: legacy attested solver unit must contain one channel "
                "and one frequency"
            )
        polarization = _canonical_output_polarization(payload_polarizations[0])
        _require_embedded_attestation(
            output_attestation,
            label,
            frequency_ghz=float(frequencies[0]),
            polarizations=(polarization,),
        )
        _require_passed_mesh_gate(mesh, label)
        quality = _require_passed_quality_gate(
            metadata.get("quality_gate"), label
        )
        return [{
            "contract": "embedded-single-output-attestation.v1",
            "label": str(label),
            "frequency_ghz": float(frequencies[0]),
            "polarization": polarization,
            "output_attestation": output_attestation,
            "mesh_convergence": mesh,
            "quality_gate": quality,
        }]

    # Backward compatibility for artifacts produced before embedded output
    # attestations. These carried a workflow_unit beside a scalar mesh gate.
    workflow = metadata.get("workflow_unit")
    try:
        _require_passed_mesh_gate(mesh, label)
    except CemToolError as exc:
        raise CemToolError(
            f"{label}: solver mesh certification did not pass the strict "
            "base/fine production policy"
        ) from exc
    if (
        not isinstance(workflow, dict)
        or workflow.get("published_mesh") != "fine"
        or not isinstance(workflow.get("mesh_convergence_policy"), dict)
    ):
        raise CemToolError(
            f"{label}: solver mesh certification did not pass the strict "
            "base/fine production policy"
        )
    return [{
        "contract": "legacy-workflow-unit.v1",
        "label": str(label),
        "workflow_unit_sha256": str(workflow.get("unit_sha256", "")),
        "frequency_ghz": workflow.get("frequency_ghz"),
        "polarization": workflow.get("polarization"),
        "mesh_convergence": mesh,
    }]
