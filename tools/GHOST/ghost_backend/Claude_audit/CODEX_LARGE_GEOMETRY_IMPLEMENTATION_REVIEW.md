# Codex implementation ready for Claude review

See the [implementation report](../Codex_audit/large_geometry_implementation_20261029/README.md), [patch](../Codex_audit/large_geometry_implementation_20261029/implementation.patch), [source hashes](../Codex_audit/large_geometry_implementation_20261029/changed_files.json), [validation summary](../Codex_audit/large_geometry_implementation_20261029/validation_summary.json), and [matched measurements](../Codex_audit/large_geometry_implementation_20261029/measurements.json).

Implemented: explicit GMRES memory accounting, full tile-fallback admission after hierarchical rejection, automatic angle-batch reduction, memory-admitted optional inverse upgrade, and idle tile-worker release. The matched high-contrast inlet improved from 57.12 to 44.60 seconds; automatic 128-column batches reduced sampled peak RSS from 1.508 to 1.329 GiB with all angles and gates retained.

Please focus review on fallback admission before allocation, failed-upgrade preservation of the working inverse, cancellation, retained-worker accounting and common-batch propagation. Existing deliberately degraded-inverse tests now deny upgrade headroom to continue testing GMRES itself. Full source snapshots and raw test failures/reruns are included.

The [audit comparison](../Codex_audit/large_geometry_comparison_with_claude.md) still governs disagreements: no cavity condition-gate relaxation, blanket forecast reduction or universal 6,000-unknown crossover. Active operator/factor disk streaming, iterative capacity methods, H-matrix reciprocity and polynomial reuse are explicitly pending, not claimed by this implementation. Dense remains available; no public mode is added.
