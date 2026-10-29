# Memory-accounting implementation for Claude review

The implementation report and reproducible evidence are in [Codex_audit/memory_implementation_20261029](../Codex_audit/memory_implementation_20261029/README.md). This delivery includes the earlier compressed-default/recovery changes as well as the memory-accounting fixes reviewed in `review_of_codex_recovery_and_memory_audit.md`.

Please focus the next audit on:

1. `execution/memory_budget.py`: stable request reservation, explicit/parent caps, weak operator/factor ownership, RSS/commit credit bounds, overlapping request reservations, teardown and metadata. Existing resident hints still have their caller-defined semantics; do not treat all such hints as independently measured owned bytes.
2. `compressed/runtime.py`, `factor.py`, `operator.py`, `hmatrix.py`: stable storage cap, phase re-admission, constructor ownership and unchanged numerical acceptance.
3. `compressed/polarization_cache.py` and `retained_storage.py`: logical versus resident payload, paired allowances, reload capacity, partial-load accounting, checksum/cancellation cleanup, and the retained-storage limit when disk payload is restored.
4. `compressed/worker_pool.py`: sample completeness, unique resident credit, separate private commitment, continued allowance for future worker growth, and no persistence outside the run.
5. `twod/solver.py`, `execution/options.py`, `execution/memory.py`, `hpc/scheduler.py`, `runs/local_twod_driver.py`: zero/unknown separation, Windows commit headroom, 90% local available-RAM policy, per-frequency batch reset and saved diagnostics.

Evidence: 467 unique final test/phase results pass. Three fresh certified 15 GHz runs (ordinary inlet, narrow inlet, moderate dielectric inlet) matched all earlier reference fields exactly. Peak RAM was 2.270 / 2.581 / 3.986 GiB within 6 / 6 / 8 GiB reservations. Automatic payload caps stayed constant throughout each run. Historical numerical evidence was preserved. A final metadata-only change bounds histories to 64 checks / 16 worker samples on the outer result; 43 focused tests passed afterward. The large-run exports preserve the earlier verbose telemetry.

The current implementation does not replace worker capacity allowances with instantaneous RSS, remove the 60% retained-payload share, increase the automatic frequency-worker count, add a machine-wide cross-application reservation service, or claim a real 90%-physical-RAM stress certification. Component calibration and physical near-capacity trials remain studies, as detailed in the report.

The review correction still applies: the old 2.352 GiB process/geometry forecast already contains the 1.894 GiB worker allowance. The independent remainder is 0.458 GiB; those two original fields are not additive savings.
