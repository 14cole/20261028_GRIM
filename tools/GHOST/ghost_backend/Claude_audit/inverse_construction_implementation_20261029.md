# Handoff: inverse construction checks and shadow calibration

Please review the current implementation against `Codex_audit/inverse_construction_20261029/README.md` and its saved validation and benchmark artifacts.

## Changes

- New `compressed/construction.py`: weak ownership of unfinished inverse trees, backing-buffer accounting, incremental allocation checks, bounded diagnostic summaries.
- `execution/memory_budget.py`: short-lived pending construction holds, atomic admission across requests, no residency credit for pending bytes, covered-reload deduplication, and ownership of the previous inverse during upgrades.
- `compressed/inverse.py`, `compressed/hmatrix_factor.py`, `linalg/hierarchical.py`: checks around ACA/range growth, QR/SVD, coefficient reads, LU, child products and corrections; earlier retained-cap checks; count each off-diagonal block before building its partner.
- `compressed/hmatrix.py`: remove coefficient-sized conjugation copies from adjoint range products; estimate product workspace by selected level.
- `compressed/factor.py`: retain ownership accounting for the old inverse during replacement builds.
- `compressed/preconditioner_hints.py`: bounded, single-request shadow storage observations after validated solves. Hypothetical next-mesh corrections are metadata only, with underprediction flags. They never alter admission or solver tolerances.

## Evidence and caveats

Two isolated baseline/current benchmarks produced identical arrays. Inverse construction medians changed from 0.080 to 0.262 seconds at 1,536 unknowns, and 0.241 to 0.632 seconds at 4,096. Total sampled private-memory peaks were effectively unchanged. Do not describe this as an end-to-end speedup or proven large-model RAM reduction.

The new pending holds deliberately separate planned capacity from resident credit. Review nested tile reload handling, shared-request ownership, exception cleanup and old/new inverse overlap closely. Product and LAPACK workspaces remain modeled bounds; they are not a universal native-allocator guarantee. Process checkpoint samples are not exact construction peaks and can include unrelated concurrent work.

The first broad run caught a helper-to-owner reference cycle; weak ownership fixed it, and the immediate-release rebuild regression passed afterward. An older analytic-cylinder test still expected automatic-picker metadata; its assertion now matches the established compressed-default policy while retaining the solve/accuracy/cap checks. Final validation passed **260 tests and 39 subtests across 19 files in 193.28 seconds**. Results are in `validation_summary.json`; raw attempts remain available. The five previously validated diagnostic implementation files remain unchanged.

## Decisions preserved

Dense is a manual override. Impedance is a separate explicit approximation. No persistent solve history, pilot admission discount, tolerance relaxation, or new GUI control was added. No blanket retry suppression was implemented: current retries already check the actual forecast before assembly, and the previously claimed 57-second saving was unsupported. The later-refusal overhead was under 2.17 seconds.

No new 2 GHz capacity claim is made. Forecasts were not reduced, so that conditional experiment remains pending independent shadow qualification. The full 12-foot, 15 GHz, 32 GB target remains unproven. Nothing was pushed in this turn.
